#!/usr/bin/env python3
"""
Generate Feb 2026 WHT batch for CRU + Cocoa XO DJs.
All DJs receive today's date except Tohmo (paid in advance 6 Apr 2026).
Eskay uses the Nobu template folder since CRU templates don't include him.
"""

import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent))
from fill_wht_form import fill_wht_form

OUT_DIR = Path('/home/brightears/cru/payments/2026-02/wht')
CRU_TEMPLATES = Path('/home/brightears/cru/payments/templates')
NOBU_TEMPLATES = Path('/home/brightears/nobu/payments/templates')

TODAY = date(2026, 4, 21)
TOHMO_DATE = date(2026, 4, 6)

# (template_name, dj_display, amount_gross, tax, venue_short, template_dir, date_override)
BATCH = [
    # CRU-only DJs (5)
    ('april',    'april',    3_200.00,  160.00, 'cru',         CRU_TEMPLATES,  TODAY),
    ('pound',    'pound',    6_400.00,  320.00, 'cru',         CRU_TEMPLATES,  TODAY),
    ('izaar',    'izaar',   12_800.00,  640.00, 'cru',         CRU_TEMPLATES,  TODAY),
    ('ufo',      'ufo',     12_800.00,  640.00, 'cru',         CRU_TEMPLATES,  TODAY),
    ('eskay',    'eskay',    9_600.00,  480.00, 'cru',         NOBU_TEMPLATES, TODAY),

    # Cocoa-only DJs (5)
    ('scotty',   'scotty',   3_200.00,  160.00, 'cocoaxo',     CRU_TEMPLATES,  TODAY),
    ('krit',     'krit',    12_800.00,  640.00, 'cocoaxo',     CRU_TEMPLATES,  TODAY),
    ('benji',    'benji',   12_800.00,  640.00, 'cocoaxo',     CRU_TEMPLATES,  TODAY),
    ('camilo',   'camilo',  12_800.00,  640.00, 'cocoaxo',     CRU_TEMPLATES,  TODAY),
    ('tohmo',    'tohmo',   25_600.00, 1280.00, 'cocoaxo',     CRU_TEMPLATES,  TOHMO_DATE),  # Paid in advance Apr 6

    # CRU + Cocoa XO DJs (3)
    ('jj',       'jj',      16_000.00,  800.00, 'cru-cocoaxo', CRU_TEMPLATES,  TODAY),
    ('manymaur', 'manymaur',14_400.00,  720.00, 'cru-cocoaxo', CRU_TEMPLATES,  TODAY),
    ('linze',    'linze',   22_400.00, 1120.00, 'cru-cocoaxo', CRU_TEMPLATES,  TODAY),
]

print(f"Output: {OUT_DIR}")
print(f"Default date: {TODAY}")
print(f"Tohmo date (advance payment): {TOHMO_DATE}")
print()

total_gross = 0
total_tax = 0

for template_name, dj, amount, tax, venue_short, template_dir, d in BATCH:
    template_path = template_dir / f'wht-{template_name}.pdf'
    if not template_path.exists():
        print(f"❌ MISSING TEMPLATE: {template_path}")
        sys.exit(1)

    output_filename = f"{dj}-feb2026-{venue_short}-wht.pdf"
    output_path = OUT_DIR / output_filename

    tax_words = fill_wht_form(
        str(template_path),
        str(output_path),
        amount,
        tax,
        d.day,
        d.month,
        d.year,
    )

    print(f"✅ {dj:10s} ฿{amount:>10,.2f}  WHT ฿{tax:>7,.2f}  date={d}  → {output_filename}")
    total_gross += amount
    total_tax += tax

print()
print(f"TOTALS: {len(BATCH)} DJs  gross=฿{total_gross:,.2f}  WHT=฿{total_tax:,.2f}  net=฿{total_gross - total_tax:,.2f}")
