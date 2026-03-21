from django.db import migrations


def seed_market_categories(apps, schema_editor):
    MarketCategory = apps.get_model("buyhive", "MarketCategory")
    Item = apps.get_model("buyhive", "Item")

    categories = [
        {
            "name": "Fruits",
            "slug": "fruits",
            "icon": "bi-brightness-high",
            "description": "Sweet, fresh, and colorful produce for quick discovery.",
            "theme": "citrus",
        },
        {
            "name": "Vegetables",
            "slug": "vegetables",
            "icon": "bi-flower1",
            "description": "Leafy greens, roots, and cooking staples from local sellers.",
            "theme": "garden",
        },
        {
            "name": "Dairy & Eggs",
            "slug": "dairy-eggs",
            "icon": "bi-cup-hot",
            "description": "Everyday essentials for breakfast, tea, and baking.",
            "theme": "dairy",
        },
        {
            "name": "Grains & Legumes",
            "slug": "grains-legumes",
            "icon": "bi-grid-3x3-gap",
            "description": "Filling pantry basics that anchor practical baskets.",
            "theme": "grain",
        },
        {
            "name": "Herbs & Spices",
            "slug": "herbs-spices",
            "icon": "bi-stars",
            "description": "Flavor boosters that make the marketplace feel curated.",
            "theme": "spice",
        },
        {
            "name": "Pantry Essentials",
            "slug": "pantry-essentials",
            "icon": "bi-basket3",
            "description": "Stock-up items for cooking, storage, and repeat orders.",
            "theme": "pantry",
        },
    ]

    category_by_slug = {}
    for payload in categories:
        category, _ = MarketCategory.objects.update_or_create(
            slug=payload["slug"],
            defaults=payload,
        )
        category_by_slug[payload["slug"]] = category

    keyword_map = {
        "fruits": [
            "apple", "banana", "orange", "mango", "fruit", "pineapple",
            "pawpaw", "avocado", "berry", "grape", "watermelon", "lemon", "lime",
        ],
        "vegetables": [
            "vegetable", "spinach", "kale", "cabbage", "tomato", "onion",
            "pepper", "carrot", "broccoli", "lettuce", "greens", "cucumber",
            "potato", "sukuma", "capsicum",
        ],
        "dairy-eggs": [
            "milk", "cheese", "yogurt", "butter", "cream", "egg", "eggs",
        ],
        "grains-legumes": [
            "rice", "flour", "maize", "beans", "bean", "peas", "grain", "oats",
            "bread", "pasta", "cereal", "lentil", "ndengu",
        ],
        "herbs-spices": [
            "herb", "spice", "ginger", "garlic", "coriander", "dhania",
            "rosemary", "thyme", "chili", "turmeric", "masala",
        ],
        "pantry-essentials": [
            "oil", "sugar", "salt", "honey", "tea", "coffee", "sauce",
            "jam", "vinegar", "stock", "water", "juice",
        ],
    }

    for item in Item.objects.filter(category__isnull=True):
        haystack = f"{item.name} {item.description}".lower()
        for slug, keywords in keyword_map.items():
            if any(keyword in haystack for keyword in keywords):
                item.category = category_by_slug[slug]
                item.save(update_fields=["category"])
                break


class Migration(migrations.Migration):

    dependencies = [
        ("buyhive", "0006_marketcategory_item_category"),
    ]

    operations = [
        migrations.RunPython(seed_market_categories, migrations.RunPython.noop),
    ]
