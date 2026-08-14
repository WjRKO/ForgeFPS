"""setup_stripe.py — Provisiona catalog di prodotti/prezzi Stripe.
Da eseguire una tantum (idempotente). Ri-lancialo se cambi prezzi in CATALOG."""
import os
from pathlib import Path

import stripe
from dotenv import load_dotenv

# Il percorso del .env era fissato a /app/backend/.env (layout del container
# Emergent). Ora si ricava dalla posizione di questo file, con override via
# BACKEND_ENV_FILE, cosi' lo script funziona ovunque.
load_dotenv(os.environ.get("BACKEND_ENV_FILE") or Path(__file__).resolve().parent / ".env")
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

#: Chiave metadata con cui ritroviamo i prodotti gia' creati su Stripe.
PRODUCT_KEY = "forgefps_product_id"
#: Chiave storica, scritta quando il catalogo era gestito da Emergent. Serve
#: solo in lettura: senza questo fallback un rilancio dello script non
#: riconoscerebbe i prodotti live e ne creerebbe di duplicati.
LEGACY_PRODUCT_KEY = "emergent_product_id"

CATALOG = [
    {
        "product_id": "framforge_pro",
        "name": "FrameForge Pro",
        "tax_code": "txcd_10103001",  # SaaS
        "prices": [
            {"lookup_key": "pro_monthly", "amount": 700, "currency": "eur", "interval": "month"},
            {"lookup_key": "pro_yearly",  "amount": 6900, "currency": "eur", "interval": "year"},
        ],
    },
    {
        "product_id": "framforge_streamer",
        "name": "FrameForge Streamer",
        "tax_code": "txcd_10103001",
        "prices": [
            {"lookup_key": "streamer_monthly", "amount": 1600, "currency": "eur", "interval": "month"},
            {"lookup_key": "streamer_yearly",  "amount": 15900, "currency": "eur", "interval": "year"},
        ],
    },
]


def get_or_create_product(entry):
    wanted = entry["product_id"]
    for p in stripe.Product.list(active=True).auto_paging_iter():
        meta = p.to_dict().get("metadata", {})
        if wanted in (meta.get(PRODUCT_KEY), meta.get(LEGACY_PRODUCT_KEY)):
            return p
    return stripe.Product.create(
        name=entry["name"], tax_code=entry.get("tax_code"),
        metadata={"managed_by": "forgefps", PRODUCT_KEY: wanted},
    )


for entry in CATALOG:
    product = get_or_create_product(entry)
    print(f"Product: {product.id} — {entry['name']}")
    for p in entry["prices"]:
        existing = stripe.Price.list(lookup_keys=[p["lookup_key"]], active=True, limit=1).data
        if existing and (existing[0].unit_amount != p["amount"] or existing[0].currency != p["currency"]):
            stripe.Price.modify(existing[0].id, active=False)
            existing = []
        if not existing:
            kwargs = dict(product=product.id, unit_amount=p["amount"], currency=p["currency"],
                          lookup_key=p["lookup_key"], transfer_lookup_key=True)
            if p.get("interval"):
                kwargs["recurring"] = {"interval": p["interval"]}
            price = stripe.Price.create(**kwargs)
            print(f"  Created price {p['lookup_key']}: €{p['amount']/100} / {p.get('interval','one-time')}")
        else:
            print(f"  Price {p['lookup_key']} exists: {existing[0].id}")

print("\nDone. Catalog synced.")
