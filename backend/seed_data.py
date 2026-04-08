# backend/seed_data.py
"""Seed data helpers for initial DB population."""

import os


def get_seed_products() -> list[dict]:
    """Return the product to seed on first install, from installer env vars.
    Returns an empty list if not running in an installer context."""
    product_id = os.environ.get("ADJUTANT_SEED_PRODUCT_ID")
    product_name = os.environ.get("ADJUTANT_SEED_PRODUCT_NAME")
    if not product_id or not product_name:
        return []
    words = product_name.split()
    if len(words) >= 2:
        icon_label = words[0][0].upper() + words[1][0].upper()
    else:
        icon_label = words[0][:2].upper() if words else "XX"
    return [{"id": product_id, "name": product_name, "icon_label": icon_label, "color": "#2563eb"}]
