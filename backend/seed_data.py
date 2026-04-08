# backend/seed_data.py
"""Static seed data for products, workstreams, and objectives."""

import os

PRODUCTS = [
    {"id": "retainerops", "name": "RetainerOps",        "icon_label": "RO", "color": "#2563eb"},
    {"id": "ignitara",    "name": "Ignitara",            "icon_label": "IG", "color": "#ea580c"},
    {"id": "bullsi",      "name": "Bullsi",              "icon_label": "BU", "color": "#7c3aed"},
    {"id": "eligibility", "name": "Eligibility Console", "icon_label": "EC", "color": "#059669"},
]

WORKSTREAMS = {
    "retainerops": [
        {"name": "Marketing", "status": "running", "display_order": 0},
        {"name": "Growth",    "status": "running", "display_order": 1},
        {"name": "Outreach",  "status": "warn",    "display_order": 2},
        {"name": "Content",   "status": "paused",  "display_order": 3},
        {"name": "Product",   "status": "paused",  "display_order": 4},
    ],
    "ignitara": [
        {"name": "Onboarding",   "status": "running", "display_order": 0},
        {"name": "Support",      "status": "warn",    "display_order": 1},
        {"name": "Sub-accounts", "status": "paused",  "display_order": 2},
        {"name": "Billing",      "status": "paused",  "display_order": 3},
    ],
    "bullsi": [
        {"name": "Product",   "status": "running", "display_order": 0},
        {"name": "Marketing", "status": "paused",  "display_order": 1},
        {"name": "Outreach",  "status": "paused",  "display_order": 2},
    ],
    "eligibility": [
        {"name": "Integrations", "status": "paused", "display_order": 0},
        {"name": "Research",     "status": "paused", "display_order": 1},
        {"name": "Outreach",     "status": "paused", "display_order": 2},
    ],
}

OBJECTIVES = {
    "retainerops": [
        {"text": "Drive 50 trial signups by May 1",          "progress_current": 23, "progress_target": 50,  "display_order": 0},
        {"text": "Publish 4 SEO posts in April",             "progress_current": 1,  "progress_target": 4,   "display_order": 1},
        {"text": "Build cold outreach list: 200 fractional CXOs", "progress_current": 87, "progress_target": 200, "display_order": 2},
    ],
    "ignitara": [
        {"text": "Onboard 3 new agency clients in April", "progress_current": 1,  "progress_target": 3,  "display_order": 0},
        {"text": "Reduce support ticket backlog to <5",   "progress_current": 12, "progress_target": 5,  "display_order": 1},
    ],
    "bullsi": [
        {"text": "Ship KPI template library v1", "progress_current": 0, "progress_target": None, "display_order": 0},
        {"text": "Reach 50 beta coaches",        "progress_current": 18, "progress_target": 50, "display_order": 1},
    ],
    "eligibility": [
        {"text": "Identify 3 clearinghouse API partners", "progress_current": 0, "progress_target": 3,  "display_order": 0},
        {"text": "First pilot clinic signed",              "progress_current": 0, "progress_target": 1,  "display_order": 1},
    ],
}


def get_seed_products():
    """Return products for initial DB seed. Uses installer env vars if present."""
    product_id   = os.environ.get("ADJUTANT_SEED_PRODUCT_ID")
    product_name = os.environ.get("ADJUTANT_SEED_PRODUCT_NAME")
    if product_id and product_name:
        icon_label = "".join(w[0].upper() for w in product_name.split()[:2]) or "XX"
        return [{"id": product_id, "name": product_name, "icon_label": icon_label, "color": "#2563eb"}]
    return PRODUCTS


def get_seed_workstreams():
    """Return workstreams for initial DB seed. Empty for new user installs."""
    if os.environ.get("ADJUTANT_SEED_PRODUCT_ID"):
        return {}
    return WORKSTREAMS


def get_seed_objectives():
    """Return objectives for initial DB seed. Empty for new user installs."""
    if os.environ.get("ADJUTANT_SEED_PRODUCT_ID"):
        return {}
    return OBJECTIVES
