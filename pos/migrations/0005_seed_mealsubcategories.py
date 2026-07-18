from django.db import migrations


def seed_subcategories(apps, schema_editor):
    MealSubcategory = apps.get_model("pos", "MealSubcategory")
    defaults = [
        ("Chicken", "chicken", "🍗"),
        ("Pork", "pork", "🥩"),
        ("Beef", "beef", "🥩"),
        ("Vegetables", "vegetables", "🥦"),
        ("Rice", "rice", "🍚"),
        ("Drinks", "drinks", "🥤"),
        ("Seafood", "seafood", "🦐"),
        ("Noodles", "noodles", "🍜"),
        ("Desserts", "desserts", "🍰"),
    ]
    for name, slug, emoji in defaults:
        MealSubcategory.objects.get_or_create(
            name=name,
            defaults={"slug": slug, "emoji": emoji},
        )


def reverse_seed(apps, schema_editor):
    MealSubcategory = apps.get_model("pos", "MealSubcategory")
    MealSubcategory.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0004_mealsubcategory_item_meal_subcategory"),
    ]

    operations = [
        migrations.RunPython(seed_subcategories, reverse_seed),
    ]
