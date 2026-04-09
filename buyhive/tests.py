import uuid
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    ContactSubmission,
    Item,
    MarketCategory,
    Order,
    OrderItem,
    Payment,
    Profile,
    SellerFulfillment,
    Wishlist,
)


class MarketplaceViewTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()

    def _make_user(self, username, email, account_type):
        user = self.user_model.objects.create_user(
            username=username,
            email=email,
            password="password123",
        )
        Profile.objects.create(user=user, account_type=account_type)
        return user

    def _category(self, slug):
        return MarketCategory.objects.get(slug=slug)

    def test_index_includes_discovery_context(self):
        seller = self._make_user("sellerone", "seller@example.com", Profile.ACCOUNT_SELLER)
        for index in range(3):
            Item.objects.create(
                owner=seller,
                category=self._category("vegetables"),
                name=f"Item {index}",
                description="Fresh listing",
                price=10 + index,
            )

        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.context["popular_cards"]), 1)
        self.assertGreaterEqual(len(response.context["category_hubs"]), 1)
        self.assertEqual(len(response.context["founders"]), 5)

    def test_buyer_dashboard_receives_marketplace_sections(self):
        buyer = self._make_user("buyerone", "buyer@example.com", Profile.ACCOUNT_BUYER)
        seller = self._make_user("sellertwo", "seller2@example.com", Profile.ACCOUNT_SELLER)
        for price in (6, 12, 18):
            Item.objects.create(
                owner=seller,
                category=self._category("fruits"),
                name=f"Produce {price}",
                description="Seasonal produce",
                price=price,
            )

        self.client.login(username="buyerone", password="password123")
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "buyer/dashboard.html")
        self.assertIn("marketplace_snapshot", response.context)
        self.assertEqual(len(response.context["recommended_cards"]), 3)
        self.assertEqual(len(response.context["budget_cards"]), 3)
        self.assertEqual(len(response.context["spotlight_sellers"]), 1)
        self.assertGreaterEqual(len(response.context["market_radar"]), 1)
        self.assertGreaterEqual(len(response.context["category_hubs"]), 1)

    def test_items_public_budget_filter_uses_market_average(self):
        seller = self._make_user("sellerthree", "seller3@example.com", Profile.ACCOUNT_SELLER)
        cheap_item = Item.objects.create(
            owner=seller,
            category=self._category("fruits"),
            name="Budget Apples",
            description="Affordable option",
            price=3,
        )
        mid_item = Item.objects.create(
            owner=seller,
            category=self._category("vegetables"),
            name="Daily Greens",
            description="Mid-range option",
            price=9,
        )
        Item.objects.create(
            owner=seller,
            category=self._category("pantry-essentials"),
            name="Premium Basket",
            description="Higher-end option",
            price=30,
        )

        response = self.client.get(reverse("items_public"), {"quick": "budget"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["quick_filter"], "budget")
        self.assertEqual(
            list(response.context["items"].values_list("id", flat=True)),
            [cheap_item.id, mid_item.id],
        )

    def test_items_public_category_filter_uses_category_slug(self):
        seller = self._make_user("sellerfour", "seller4@example.com", Profile.ACCOUNT_SELLER)
        fruits = self._category("fruits")
        grains = self._category("grains-legumes")
        fruit_item = Item.objects.create(
            owner=seller,
            category=fruits,
            name="Sweet Mangoes",
            description="Fresh fruit",
            price=15,
        )
        Item.objects.create(
            owner=seller,
            category=grains,
            name="Brown Rice",
            description="Staple grain",
            price=20,
        )

        response = self.client.get(reverse("items_public"), {"category": "fruits"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_category"], fruits)
        self.assertEqual(
            list(response.context["items"].values_list("id", flat=True)),
            [fruit_item.id],
        )

    def test_seller_dashboard_surfaces_category_hubs_and_performance(self):
        seller = self._make_user("sellerdash", "sellerdash@example.com", Profile.ACCOUNT_SELLER)
        buyer = self._make_user("buyerdash", "buyerdash@example.com", Profile.ACCOUNT_BUYER)
        item = Item.objects.create(
            owner=seller,
            category=self._category("vegetables"),
            name="Spinach Bundle",
            description="Leafy greens",
            price=14,
        )
        Wishlist.objects.create(user=buyer, item=item)
        order = Order.objects.create(
            order_id=f"ORD-{uuid.uuid4().hex[:10].upper()}",
            buyer=buyer,
            status="paid",
            total_amount=item.price,
            phone_number="254712345678",
            buyer_name="Buyer Dash",
            buyer_email=buyer.email,
            delivery_address="Nairobi",
        )
        OrderItem.objects.create(
            order=order,
            item=item,
            seller=seller,
            quantity=2,
            price=item.price,
            subtotal=item.price * 2,
        )

        self.client.login(username=seller.username, password="password123")
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "seller/dashboard.html")
        self.assertEqual(len(response.context["category_hubs"]), 1)
        self.assertEqual(response.context["seller_performance"]["orders_count"], 1)

    def test_shared_layout_contains_contact_link(self):
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("contact"), count=2)


class ContactViewTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()

    def _make_user(self, username, email):
        user = self.user_model.objects.create_user(
            username=username,
            email=email,
            password="password123",
        )
        Profile.objects.create(
            user=user,
            account_type=Profile.ACCOUNT_BUYER,
            phone_number="0712345678",
        )
        return user

    def test_contact_page_renders(self):
        response = self.client.get(reverse("contact"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "contact.html")

    def test_contact_page_prefills_authenticated_user_details(self):
        user = self._make_user("contact_user", "contact@example.com")
        self.client.login(username=user.username, password="password123")

        response = self.client.get(reverse("contact"))
        form = response.context["form"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(form["name"].value(), user.username)
        self.assertEqual(form["email"].value(), user.email)
        self.assertEqual(form["phone_number"].value(), "0712345678")

    def test_contact_post_creates_submission_and_shows_success_message(self):
        response = self.client.post(
            reverse("contact"),
            {
                "name": "Jamie Seller",
                "email": "jamie@example.com",
                "phone_number": "+254 712 345 678",
                "subject": "Issue with an order",
                "message": "I need help tracing a recent order.",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("contact"))
        self.assertEqual(ContactSubmission.objects.count(), 1)
        submission = ContactSubmission.objects.get()
        self.assertEqual(submission.subject, "Issue with an order")
        self.assertContains(response, "Thanks for reaching out.")

    def test_contact_post_with_invalid_data_shows_errors(self):
        response = self.client.post(
            reverse("contact"),
            {
                "name": "",
                "email": "not-an-email",
                "subject": "",
                "message": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactSubmission.objects.count(), 0)
        self.assertContains(response, "This field is required.")


class CheckoutFlowTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.buyer = self._make_user("buyer_checkout", "buyer-checkout@example.com", Profile.ACCOUNT_BUYER)
        self.seller = self._make_user("seller_checkout", "seller-checkout@example.com", Profile.ACCOUNT_SELLER)
        self.item = Item.objects.create(
            owner=self.seller,
            name="Fresh Tomatoes",
            description="Juicy tomatoes",
            price=25,
            is_available=True,
        )
        self.client.login(username=self.buyer.username, password="password123")

    def _make_user(self, username, email, account_type):
        user = self.user_model.objects.create_user(
            username=username,
            email=email,
            password="password123",
        )
        Profile.objects.create(user=user, account_type=account_type)
        return user

    def _set_checkout_cart(self, cart):
        session = self.client.session
        session["checkout_cart"] = cart
        session.save()

    def _create_order(self, status="pending", payment_status="pending"):
        order = Order.objects.create(
            order_id=f"ORD-{uuid.uuid4().hex[:10].upper()}",
            buyer=self.buyer,
            status=status,
            total_amount=self.item.price,
            phone_number="254712345678",
            buyer_name="Checkout Buyer",
            buyer_email=self.buyer.email,
            delivery_address="Nairobi",
        )
        OrderItem.objects.create(
            order=order,
            item=self.item,
            seller=self.seller,
            quantity=1,
            price=self.item.price,
            subtotal=self.item.price,
        )
        Payment.objects.create(
            order=order,
            amount=self.item.price,
            phone_number="254712345678",
            status=payment_status,
        )
        return order

    def test_checkout_review_stores_session_snapshot_and_redirects(self):
        response = self.client.post(
            reverse("checkout"),
            {
                "checkout_action": "review",
                f"cart_{self.item.id}": "2",
            },
        )

        self.assertRedirects(response, reverse("checkout"))
        self.assertEqual(self.client.session["checkout_cart"], {str(self.item.id): 2})

    def test_checkout_get_renders_from_session_snapshot(self):
        self._set_checkout_cart({str(self.item.id): 2})

        response = self.client.get(reverse("checkout"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fresh Tomatoes")
        self.assertEqual(response.context["total_amount"], self.item.price * 2)

    def test_checkout_submit_creates_order_and_clears_session_snapshot(self):
        self._set_checkout_cart({str(self.item.id): 3})

        response = self.client.post(
            reverse("checkout"),
            {
                "checkout_action": "submit",
                "buyer_name": "Checkout Buyer",
                "buyer_email": self.buyer.email,
                "phone_number": "254712345678",
                "delivery_address": "Westlands, Nairobi",
                "delivery_location_label": "Westlands gate",
                "delivery_latitude": "-1.267000",
                "delivery_longitude": "36.810000",
            },
        )

        order = Order.objects.get(buyer=self.buyer)
        payment = Payment.objects.get(order=order)
        fulfillment = SellerFulfillment.objects.get(order=order, seller=self.seller)

        self.assertRedirects(response, reverse("initiate_payment", args=[order.order_id]), fetch_redirect_response=False)
        self.assertEqual(order.total_amount, self.item.price * 3)
        self.assertEqual(order.items.first().quantity, 3)
        self.assertEqual(payment.amount, self.item.price * 3)
        self.assertEqual(order.delivery_location_label, "Westlands gate")
        self.assertIsNotNone(order.delivery_latitude)
        self.assertEqual(fulfillment.status, SellerFulfillment.STATUS_PENDING)
        self.assertNotIn("checkout_cart", self.client.session)
        self.assertTrue(self.client.session["clear_browser_cart_on_next_page"])

    def test_checkout_review_ignores_invalid_cart_inputs(self):
        response = self.client.post(
            reverse("checkout"),
            {
                "checkout_action": "review",
                "cart_invalid": "2",
                f"cart_{self.item.id}": "2",
                "cart_999999": "not-a-number",
            },
        )

        self.assertRedirects(response, reverse("checkout"))
        self.assertEqual(self.client.session["checkout_cart"], {str(self.item.id): 2})

    def test_checkout_review_removes_unavailable_items(self):
        unavailable_item = Item.objects.create(
            owner=self.seller,
            name="Sold Out Kale",
            description="Unavailable now",
            price=18,
            is_available=False,
        )

        response = self.client.post(
            reverse("checkout"),
            {
                "checkout_action": "review",
                f"cart_{self.item.id}": "1",
                f"cart_{unavailable_item.id}": "2",
            },
        )

        self.assertRedirects(response, reverse("checkout"))
        self.assertEqual(self.client.session["checkout_cart"], {str(self.item.id): 1})

    def test_initiate_payment_success_updates_payment_and_order(self):
        order = self._create_order()
        mock_mpesa = MagicMock()
        mock_mpesa.get_callback_url.return_value = "https://checkout.shopora.example/api/mpesa/callback/"
        mock_mpesa.initiate_stk_push.return_value = {"CheckoutRequestID": "ws_CO_12345"}

        with patch("buyhive.views.create_mpesa_client", return_value=mock_mpesa):
            response = self.client.get(reverse("initiate_payment", args=[order.order_id]))

        order.refresh_from_db()
        payment = order.payment

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payment_pending.html")
        self.assertEqual(order.status, "payment_initiated")
        self.assertEqual(payment.status, "initiated")
        self.assertEqual(payment.checkout_request_id, "ws_CO_12345")

    def test_initiate_payment_failure_marks_order_and_payment_failed(self):
        order = self._create_order()
        mock_mpesa = MagicMock()
        mock_mpesa.get_callback_url.return_value = "https://checkout.shopora.example/api/mpesa/callback/"
        mock_mpesa.initiate_stk_push.side_effect = Exception("MPESA service unavailable")

        with patch("buyhive.views.create_mpesa_client", return_value=mock_mpesa):
            response = self.client.get(reverse("initiate_payment", args=[order.order_id]))

        order.refresh_from_db()
        payment = order.payment

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payment_failed.html")
        self.assertEqual(order.status, "failed")
        self.assertEqual(payment.status, "failed")
        self.assertEqual(payment.result_description, "MPESA service unavailable")

    def test_failed_order_can_retry_payment(self):
        order = self._create_order(status="failed", payment_status="failed")
        mock_mpesa = MagicMock()
        mock_mpesa.get_callback_url.return_value = "https://checkout.shopora.example/api/mpesa/callback/"
        mock_mpesa.initiate_stk_push.return_value = {"CheckoutRequestID": "ws_CO_retry"}

        with patch("buyhive.views.create_mpesa_client", return_value=mock_mpesa):
            response = self.client.get(reverse("initiate_payment", args=[order.order_id]))

        order.refresh_from_db()
        payment = order.payment

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payment_pending.html")
        self.assertEqual(order.status, "payment_initiated")
        self.assertEqual(payment.status, "initiated")

    @override_settings(MPESA_CALLBACK_URL="https://your-domain.com/api/mpesa/callback/")
    def test_initiate_payment_rejects_invalid_callback_before_network_call(self):
        order = self._create_order()

        with patch("buyhive.mpesa_utils.requests.get") as mock_get, patch("buyhive.mpesa_utils.requests.post") as mock_post:
            response = self.client.get(reverse("initiate_payment", args=[order.order_id]))

        order.refresh_from_db()
        payment = order.payment

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payment_failed.html")
        self.assertEqual(order.status, "failed")
        self.assertEqual(payment.status, "failed")
        self.assertIn("public HTTPS domain", payment.result_description)
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    def test_payment_status_returns_json_for_ajax_requests(self):
        order = self._create_order(status="payment_initiated", payment_status="initiated")

        response = self.client.get(
            reverse("payment_status", args=[order.order_id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["order_status"], "payment_initiated")
        self.assertEqual(response.json()["payment_status"], "initiated")


class ProfileLocationAndVisibilityTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()

    def _make_user(self, username, email, account_type, **profile_kwargs):
        user = self.user_model.objects.create_user(
            username=username,
            email=email,
            password="password123",
        )
        Profile.objects.create(user=user, account_type=account_type, **profile_kwargs)
        return user

    def test_register_saves_location_fields(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "mappedbuyer",
                "email": "mappedbuyer@example.com",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
                "account_type": Profile.ACCOUNT_BUYER,
                "phone_number": "0712345678",
                "delivery_address": "Westlands apartment",
                "location_label": "Westlands home",
                "location_address": "Near Sarit Centre",
                "latitude": "-1.267000",
                "longitude": "36.810000",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        profile = Profile.objects.get(user__username="mappedbuyer")
        self.assertEqual(profile.location_label, "Westlands home")
        self.assertIsNotNone(profile.latitude)

    def test_register_rejects_partial_location(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "partialbuyer",
                "email": "partialbuyer@example.com",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
                "account_type": Profile.ACCOUNT_BUYER,
                "location_label": "Missing pin",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pick the location on the map")

    def test_seller_public_profile_shows_location_but_buyer_search_hides_buyer_location(self):
        seller = self._make_user(
            "mappedseller",
            "mappedseller@example.com",
            Profile.ACCOUNT_SELLER,
            location_label="Limuru farm",
            location_address="Near Limuru market",
            latitude="-1.114000",
            longitude="36.642000",
        )
        self._make_user(
            "mappedbuyer",
            "mappedbuyer@example.com",
            Profile.ACCOUNT_BUYER,
            location_label="Private estate",
            latitude="-1.267000",
            longitude="36.810000",
        )

        response = self.client.get(reverse("profile_public", args=[seller.username]))
        self.assertContains(response, "Limuru farm")

        search_response = self.client.get(reverse("profiles_search"), {"account_type": "buyer"})
        self.assertNotContains(search_response, "Private estate")


class SellerFulfillmentTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.buyer = self._make_user("dispatch_buyer", "dispatch_buyer@example.com", Profile.ACCOUNT_BUYER)
        self.seller = self._make_user("dispatch_seller", "dispatch_seller@example.com", Profile.ACCOUNT_SELLER)
        self.other_seller = self._make_user("other_seller", "other_seller@example.com", Profile.ACCOUNT_SELLER)
        self.order = Order.objects.create(
            order_id=f"ORD-{uuid.uuid4().hex[:10].upper()}",
            buyer=self.buyer,
            status="paid",
            total_amount=500,
            phone_number="254712345678",
            buyer_name="Dispatch Buyer",
            buyer_email=self.buyer.email,
            delivery_address="Warehouse lane",
            delivery_location_label="Warehouse gate",
            delivery_latitude="-1.267000",
            delivery_longitude="36.810000",
        )
        self.item = Item.objects.create(
            owner=self.seller,
            name="Dispatch Tomatoes",
            description="Ready to ship",
            condition_summary="Harvested this morning",
            price=50,
        )
        OrderItem.objects.create(
            order=self.order,
            item=self.item,
            seller=self.seller,
            quantity=2,
            price=self.item.price,
            subtotal=self.item.price * 2,
        )
        self.fulfillment = SellerFulfillment.objects.create(order=self.order, seller=self.seller)

    def _make_user(self, username, email, account_type):
        user = self.user_model.objects.create_user(
            username=username,
            email=email,
            password="password123",
        )
        Profile.objects.create(user=user, account_type=account_type)
        return user

    def test_seller_can_view_only_own_fulfillment(self):
        self.client.login(username=self.seller.username, password="password123")
        response = self.client.get(reverse("seller_fulfillment_detail", args=[self.fulfillment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.delivery_location_label)

        self.client.logout()
        self.client.login(username=self.other_seller.username, password="password123")
        denied = self.client.get(reverse("seller_fulfillment_detail", args=[self.fulfillment.id]))
        self.assertEqual(denied.status_code, 404)

    def test_fulfillment_status_update_advances_and_sets_timestamp(self):
        self.client.login(username=self.seller.username, password="password123")
        response = self.client.post(
            reverse("seller_fulfillment_detail", args=[self.fulfillment.id]),
            {
                "status": SellerFulfillment.STATUS_PACKED,
                "dispatch_notes": "Packed in crates",
            },
            follow=True,
        )

        self.fulfillment.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fulfillment.status, SellerFulfillment.STATUS_PACKED)
        self.assertEqual(self.fulfillment.dispatch_notes, "Packed in crates")
        self.assertIsNotNone(self.fulfillment.packed_at)

    def test_fulfillment_status_update_is_blocked_before_payment(self):
        self.order.status = "payment_initiated"
        self.order.save(update_fields=["status"])

        self.client.login(username=self.seller.username, password="password123")
        response = self.client.post(
            reverse("seller_fulfillment_detail", args=[self.fulfillment.id]),
            {
                "status": SellerFulfillment.STATUS_PACKED,
                "dispatch_notes": "Should not save yet",
            },
            follow=True,
        )

        self.fulfillment.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "dispatch status changes are locked")
        self.assertEqual(self.fulfillment.status, SellerFulfillment.STATUS_PENDING)
        self.assertEqual(self.fulfillment.dispatch_notes, "")
