#!/usr/bin/env python3
"""
Generate April 2026 CRU + Cocoa XO invoice.
Custom line items for Songkran extras + Camilo percussion.
"""

import sys
import subprocess
from pathlib import Path
from string import Template
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0, str(Path(__file__).parent))
from generate_invoice import (
    HOURLY_INVOICE_RATE, HOURS_PER_EVENING, VAT_RATE, WHT_RATE,
    CUSTOMER, TAX_NO, MONTH_NAMES, MONTH_FULL,
    amount_to_words, ordinal, fmt,
    build_line_items_html, save_invoice_no,
)

YEAR = 2026
MONTH = 4
DAYS_IN_MONTH = 30
TOTAL_SHIFTS = DAYS_IN_MONTH * 2  # 60
INVOICE_NO = 3180  # 3179 was Uno Mas (manual by Norbert)
INVOICE_DATE = '30.04.2026'

PER_EVENING = (HOURLY_INVOICE_RATE * HOURS_PER_EVENING).quantize(
    Decimal('0.01'), rounding=ROUND_HALF_UP
)

def base_amount():
    return (HOURLY_INVOICE_RATE * HOURS_PER_EVENING * TOTAL_SHIFTS).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )

def songkran_dj_amount():
    """4-hour extra DJ shift at same rate as a regular evening."""
    return (HOURLY_INVOICE_RATE * 4).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# ---------------------------------------------------------------------------
# Line items
# ---------------------------------------------------------------------------

items = []

# 1. Base combined DJ service
items.append({
    'no': 1,
    'description': 'Cocoa XO &amp; CRU DJ Service',
    'date': f'01.{MONTH:02d}.{str(YEAR)[-2:]} - {DAYS_IN_MONTH}.{MONTH:02d}.{str(YEAR)[-2:]}',
    'time': '21:00 - 01:00',
    'price': base_amount(),
    'amount': base_amount(),
})

# 2. CRU Apr 12 Guest DJ (deduct)
items.append({
    'no': 2,
    'description': f'No DJ at CRU on Apr 12<sup>{ordinal(12)}</sup>',
    'date': '12.04.2026',
    'time': '-',
    'price': -PER_EVENING,
    'amount': -PER_EVENING,
})

# 3-8. Songkran extra early DJ shifts at CRU (Apr 11-16), 17:00-21:00
songkran_days = [11, 12, 13, 14, 15, 16]
line_no = 3
for day in songkran_days:
    items.append({
        'no': line_no,
        'description': f'Songkran extra DJ at CRU on Apr {day}<sup>{ordinal(day)}</sup>',
        'date': f'{day:02d}.04.2026',
        'time': '17:00 - 21:00',
        'price': songkran_dj_amount(),
        'amount': songkran_dj_amount(),
    })
    line_no += 1

# 9-12. Camilo percussion (Apr 13, 14, 15, 16) — 2hr × ฿2,000/hr = ฿4,000 each
percussion_days = [13, 14, 15, 16]
for day in percussion_days:
    items.append({
        'no': line_no,
        'description': f'Percussion performance at CRU on Apr {day}<sup>{ordinal(day)}</sup>',
        'date': f'{day:02d}.04.2026',
        'time': '21:00 - 23:00',
        'price': Decimal('4000.00'),
        'amount': Decimal('4000.00'),
    })
    line_no += 1

# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------

sub_total = sum(item['amount'] for item in items)
vat = (sub_total * VAT_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
grand_total = sub_total + vat
wht = (sub_total * WHT_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
net_amount = grand_total - wht

# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------

print(f"\n{'='*60}")
print(f"Invoice #{INVOICE_NO} — April {YEAR}")
print(f"{'='*60}")
print(f"\nLine items:")
for item in items:
    import re as _re
    desc = _re.sub(r'<[^>]+>', '', item['description'])
    print(f"  {item['no']:>2}. {desc:<46} {item['amount']:>12,.2f}")
print(f"\n  {'Sub Total:':<48} {sub_total:>12,.2f} THB")
print(f"  {'VAT 7%:':<48} {vat:>12,.2f} THB")
print(f"  {'Grand Total:':<48} {grand_total:>12,.2f} THB")
print(f"  {'WHT 3%:':<48} {-wht:>12,.2f} THB")
print(f"  {'Net Amount:':<48} {net_amount:>12,.2f} THB")
print(f"\n  Written: {amount_to_words(net_amount)}")

# ---------------------------------------------------------------------------
# Render HTML
# ---------------------------------------------------------------------------

template_path = Path(__file__).parent.parent / 'templates' / 'invoice-template.html'
template_text = template_path.read_text()

# The template is a Feb-2026 static file, not a Template. Check if it has $placeholders.
# Feb-2026 template we saw is the static Feb HTML. Let's check what's in templates/invoice-template.html.
if '$INVOICE_NO' in template_text:
    # Proper template
    template = Template(template_text)
    html = template.safe_substitute(
        INVOICE_NO=f'# {INVOICE_NO}',
        INVOICE_DATE=INVOICE_DATE,
        TAX_NO=TAX_NO,
        CUSTOMER_NAME=CUSTOMER['name'],
        CUSTOMER_ADDRESS=CUSTOMER['address'],
        CUSTOMER_CITY=CUSTOMER['city'],
        CUSTOMER_TAX_ID=CUSTOMER['tax_id'],
        LINE_ITEMS_HTML=build_line_items_html(items),
        SUB_TOTAL=fmt(sub_total),
        VAT_AMOUNT=fmt(vat),
        GRAND_TOTAL=fmt(grand_total),
        WHT_AMOUNT=fmt(-wht),
        NET_AMOUNT=fmt(net_amount),
        WRITTEN_AMOUNT=amount_to_words(net_amount),
    )
else:
    print("Error: template is not using placeholders. Cannot substitute.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Write HTML + PDF
# ---------------------------------------------------------------------------

out_dir = Path(__file__).parent.parent / f'{YEAR}-{MONTH:02d}'
out_dir.mkdir(exist_ok=True)

month_abbr = MONTH_NAMES[MONTH].lower()
basename = f'invoice-{INVOICE_NO}-{month_abbr}{YEAR}'
html_path = out_dir / f'{basename}.html'
pdf_path = out_dir / f'{basename}.pdf'

html_path.write_text(html)
print(f"\nHTML: {html_path}")

# Generate PDF with chromium
cmd = [
    'chromium-browser',
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    f'--print-to-pdf={pdf_path}',
    '--print-to-pdf-no-header',
    f'file://{html_path.resolve()}',
]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
if result.returncode != 0:
    print(f"PDF gen stderr: {result.stderr[:300]}")
print(f"PDF:  {pdf_path}")

# Update invoice counter
save_invoice_no(INVOICE_NO, f'{YEAR}-{MONTH:02d}')
print(f"\nInvoice #{INVOICE_NO} generated.")
