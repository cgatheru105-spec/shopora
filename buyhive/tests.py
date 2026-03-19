import uuid
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Item, Order, OrderItem, Payment, Profile


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

    def test_index_includes_discovery_context(self):
        seller = self._make_user("sellerone", "seller@example.com", Profile.ACCOUNT_SELLER)
        for index in range(3):
            Item.objects.create(
                owner=seller,
                name=f"Item {index}",
                description="Fresh listing",
                price=10 + index,
            )

        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("marketplace_snapshot", response.context)
        self.assertGreaterEqual(len(response.context["popular_cards"]), 1)
        self.assertGreaterEqual(len(response.context["fresh_cards"]), 1)
        self.assertGreaterEqual(len(response.context["budget_cards"]), 1)
        self.assertGreaterEqual(len(response.context["spotlight_sellers"]), 1)

    def test_buyer_dashboard_receives_marketplace_sections(self):
        buyer = self._make_user("buyerone", "buyer@example.com", Profile.ACCOUNT_BUYER)
        seller = self._make_user("sellertwo", "seller2@example.com", Profile.ACCOUNT_SELLER)
        for price in (6, 12, 18):
            Item.objects.create(
                owner=seller,
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

    def test_items_public_budget_filter_uses_market_average(self):
        seller = self._make_user("sellerthree", "seller3@example.com", Profile.ACCOUNT_SELLER)
        cheap_item = Item.objects.create(
            owner=seller,
            name="Budget Apples",
            description="Affordable option",
            price=3,
        )
        mid_item = Item.objects.create(
            owner=seller,
            name="Daily Greens",
            description="Mid-range option",
            price=9,
        )
        Item.objects.create(
            owner=seller,
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
            },
        )

        order = Order.objects.get(buyer=self.buyer)
        payment = Payment.objects.get(order=order)

        self.assertRedirects(response, reverse("initiate_payment", args=[order.order_id]), fetch_redirect_response=False)
        self.assertEqual(order.total_amount, self.item.price * 3)
        self.assertEqual(order.items.first().quantity, 3)
        self.assertEqual(payment.amount, self.item.price * 3)
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
