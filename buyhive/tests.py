from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Item, Profile


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
