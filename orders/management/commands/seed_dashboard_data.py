import random
from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from menu.models import Category, MenuItem, MenuItemVariant
from orders.models import Order, OrderItem

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds realistic restaurant data (categories, menu items, orders) for Dashboard analytics'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Grand Plaza Restaurant Data..."))

        # 1. CATEGORIES
        cat_data = [
            ("Biriyani & Rice", None),
            ("Grills & Arabic", None),
            ("Burgers & Fast Food", None),
            ("South Indian", None),
            ("Beverages & Shakes", None),
        ]
        categories = {}
        for name, _ in cat_data:
            c, _ = Category.objects.get_or_create(name=name)
            categories[name] = c

        # 2. MENU ITEMS
        items_specs = [
            {
                "name": "Grand Thalassery Chicken Biriyani",
                "category": categories["Biriyani & Rice"],
                "section": "BEST SELLER",
                "dietary": "NON-VEG",
                "price": Decimal("240.00"),
                "has_variants": False,
                "variants": [],
            },
            {
                "name": "Mutton Dum Biriyani",
                "category": categories["Biriyani & Rice"],
                "section": "BEST SELLER",
                "dietary": "NON-VEG",
                "price": Decimal("350.00"),
                "has_variants": False,
                "variants": [],
            },
            {
                "name": "Al Faham Dajaj (BBQ Grilled)",
                "category": categories["Grills & Arabic"],
                "section": "TODAY'S SPECIAL",
                "dietary": "NON-VEG",
                "price": None,
                "has_variants": True,
                "variants": [
                    ("Quarter", Decimal("140.00")),
                    ("Half", Decimal("260.00")),
                    ("Full", Decimal("490.00")),
                ],
            },
            {
                "name": "Peri Peri Shawarma Roll",
                "category": categories["Grills & Arabic"],
                "section": "BEST SELLER",
                "dietary": "NON-VEG",
                "price": Decimal("130.00"),
                "has_variants": False,
                "variants": [],
            },
            {
                "name": "Crispy Zinger Chicken Burger",
                "category": categories["Burgers & Fast Food"],
                "section": "COMBO MENU",
                "dietary": "NON-VEG",
                "price": Decimal("180.00"),
                "has_variants": False,
                "variants": [],
            },
            {
                "name": "Paneer Butter Masala",
                "category": categories["South Indian"],
                "section": "ALL",
                "dietary": "VEG",
                "price": Decimal("210.00"),
                "has_variants": False,
                "variants": [],
            },
            {
                "name": "Kerala Malabar Porotta (Set of 3)",
                "category": categories["South Indian"],
                "section": "ALL",
                "dietary": "VEG",
                "price": Decimal("60.00"),
                "has_variants": False,
                "variants": [],
            },
            {
                "name": "Blue Ocean Curacao Mojito",
                "category": categories["Beverages & Shakes"],
                "section": "OTHERS",
                "dietary": "VEG",
                "price": Decimal("110.00"),
                "has_variants": False,
                "variants": [],
            },
            {
                "name": "Special Malabar Mango Shake",
                "category": categories["Beverages & Shakes"],
                "section": "OTHERS",
                "dietary": "VEG",
                "price": Decimal("130.00"),
                "has_variants": False,
                "variants": [],
            },
        ]

        menu_items = []
        for spec in items_specs:
            item, created = MenuItem.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "category": spec["category"],
                    "section": spec["section"],
                    "dietary_preference": spec["dietary"],
                    "actual_price": spec["price"],
                    "offer_price": spec["price"],
                    "has_variants": spec["has_variants"],
                    "quantity": 100,
                    "is_available": True,
                },
            )
            if spec["has_variants"]:
                for size_name, v_price in spec["variants"]:
                    MenuItemVariant.objects.get_or_create(
                        menu_item=item,
                        size_name=size_name,
                        defaults={
                            "actual_price": v_price,
                            "offer_price": v_price,
                            "quantity": 50,
                        },
                    )
            menu_items.append(item)

        self.stdout.write(self.style.SUCCESS(f"Created/Verified {len(menu_items)} Menu Items."))

        # 3. CUSTOMER DATA
        customers = [
            ("Rahul Krishnan", "9847123456", "Villa 12, Green Meadows, Calicut Road"),
            ("Anjali Menon", "9745287654", "Flat 4B, Skyview Towers, Down Hill"),
            ("Mohammed Shafi", "9447311223", "Al-Baraka House, Near Town Mosque, Kottakkal"),
            ("Sneha Nair", "9995566778", "House No 88, Heritage Lane, Perinthalmanna"),
            ("Jamsheer Ali", "9562134987", "Room 201, Star Residency, Manjeri"),
            ("Fathima Ziyana", "9846277123", "Baitul Noor, Bypass Junction, Malappuram"),
            ("Arjun Pillai", "9744155667", "Sunrise Enclave, Plot 14, Kondotty"),
            ("Vishnu Das", "9895044332", "Riverdale Apt 502, Civil Station Road"),
        ]

        # 4. ORDER CREATION
        now = timezone.now()
        
        # Order templates
        # (days_ago, hours_ago, status, payment_status, item_indices_with_qty, special_note)
        timeline_orders = [
            # --- TODAY (Active live orders + today's delivered) ---
            (0, 1, "preparing", "pending", [(0, 2), (7, 2)], "Less spicy please, extra onion salad"),
            (0, 2, "ready_for_pickup", "completed", [(2, 1), (6, 2)], "Keep extra mint chutney"),
            (0, 3, "out_for_delivery", "pending", [(3, 3), (8, 2)], "Call when reaching gate"),
            (0, 4, "delivered", "completed", [(0, 1), (1, 1), (7, 1)], ""),
            (0, 5, "delivered", "completed", [(4, 2), (7, 2)], "Pack sauces separately"),
            (0, 6, "delivered", "completed", [(2, 1), (5, 1), (6, 3)], ""),
            (0, 7, "delivered", "completed", [(0, 3)], "Spicy biriyani"),
            
            # --- YESTERDAY ---
            (1, 12, "delivered", "completed", [(0, 2), (3, 2), (8, 1)], ""),
            (1, 14, "delivered", "completed", [(1, 2), (7, 2)], ""),
            (1, 18, "delivered", "completed", [(4, 3), (8, 3)], ""),
            (1, 20, "delivered", "completed", [(2, 1), (6, 2)], ""),
            (1, 21, "cancelled", "refunded", [(0, 1)], "Customer cancelled due to delay"),

            # --- THIS WEEK (2 to 6 days ago) ---
            (2, 13, "delivered", "completed", [(0, 2), (7, 1)], ""),
            (2, 19, "delivered", "completed", [(1, 1), (2, 1), (6, 2)], ""),
            (3, 12, "delivered", "completed", [(3, 4), (8, 2)], ""),
            (3, 20, "delivered", "completed", [(0, 3), (4, 1)], ""),
            (4, 14, "delivered", "completed", [(2, 1), (5, 1), (6, 3)], ""),
            (4, 19, "delivered", "completed", [(1, 2), (7, 2)], ""),
            (5, 13, "delivered", "completed", [(0, 2), (8, 2)], ""),
            (5, 20, "delivered", "completed", [(4, 2), (7, 2)], ""),
            (6, 12, "delivered", "completed", [(0, 4), (7, 4)], ""),
            (6, 19, "delivered", "completed", [(1, 2), (2, 1)], ""),

            # --- THIS MONTH (7 to 28 days ago) ---
            (8, 13, "delivered", "completed", [(0, 2), (3, 2)], ""),
            (10, 19, "delivered", "completed", [(1, 1), (2, 1), (7, 2)], ""),
            (13, 14, "delivered", "completed", [(4, 3), (8, 3)], ""),
            (16, 20, "delivered", "completed", [(0, 3), (6, 2)], ""),
            (20, 13, "delivered", "completed", [(2, 1), (5, 2), (6, 4)], ""),
            (24, 19, "delivered", "completed", [(1, 2), (7, 3)], ""),

            # --- EARLIER MONTHS THIS YEAR (35 to 120 days ago) ---
            (35, 14, "delivered", "completed", [(0, 3), (8, 2)], ""),
            (45, 19, "delivered", "completed", [(1, 2), (2, 1)], ""),
            (60, 13, "delivered", "completed", [(3, 5), (7, 3)], ""),
            (75, 20, "delivered", "completed", [(0, 4), (4, 2)], ""),
            (90, 12, "delivered", "completed", [(2, 1), (5, 1), (6, 4)], ""),
            (110, 18, "delivered", "completed", [(1, 3), (8, 3)], ""),
        ]

        created_count = 0
        for idx, (days_ago, hours_ago, o_status, p_status, item_pairs, note) in enumerate(timeline_orders):
            cust = customers[idx % len(customers)]
            order_time = now - timedelta(days=days_ago, hours=hours_ago, minutes=random.randint(5, 55))

            order = Order(
                customer_name=cust[0],
                customer_phone=cust[1],
                delivery_address=cust[2],
                special_instructions=note,
                status=o_status,
                payment_status=p_status,
                total_price=Decimal("0.00"),
            )
            order.save()

            # Overwrite created_at to simulate historical timeline
            Order.objects.filter(pk=order.pk).update(created_at=order_time)

            total_bill = Decimal("0.00")
            for item_idx, qty in item_pairs:
                menu_item = menu_items[item_idx]
                if menu_item.has_variants:
                    variant = menu_item.variants.first()
                    u_price = variant.actual_price if variant else Decimal("140.00")
                    v_name = variant.size_name if variant else "Standard"
                else:
                    variant = None
                    u_price = menu_item.actual_price or Decimal("150.00")
                    v_name = ""

                line_total = u_price * qty
                total_bill += line_total

                OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    variant=variant,
                    item_name=menu_item.name,
                    variant_name=v_name,
                    quantity=qty,
                    unit_price=u_price,
                    line_total=line_total,
                )

            # Flat ₹30 delivery fee if > 0
            if total_bill > 0:
                total_bill += Decimal("30.00")

            Order.objects.filter(pk=order.pk).update(total_price=total_bill)
            created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {created_count} realistic orders across Today, This Week, This Month, and This Year!"))
