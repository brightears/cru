#!/usr/bin/env python3
"""
Generate May 2026 CRU + Cocoa XO invoice.
Adds 3 CRU early extras (May 21/22/23 17-21, champagne promo).
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
MONTH = 5
DAYS_IN_MONTH = 31
TOTAL_SHIFTS = DAYS_IN_MONTH * 2  # 62 (Cocoa + CRU each night)
INVOICE_NO = 3182  # 3181 was Uno Mas (manual by Norbert); 3180 was April
INVOICE_DATE = '31.05.2026'

PER_EVENING = (HOURLY_INVOICE_RATE * HOURS_PER_EVENING).quantize(
    Decimal('0.01'), rounding=ROUND_HALF_UP
)


def base_amount():
    return (HOURLY_INVOICE_RATE * HOURS_PER_EVENING * TOTAL_SHIFTS).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )


def extra_dj_amount():
    """4-hour extra DJ shift at same rate as a regular evening."""
    return (HOURLY_INVOICE_RATE * 4).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Line items
# ---------------------------------------------------------------------------

items = []

# 1. Base combined DJ service (Cocoa XO + CRU, all 31 nights, 21:00-01:00)
items.append({
    'no': 1,
    'description': 'Cocoa XO &amp; CRU DJ Service',
    'date': f'01.{MONTH:02d}.{str(YEAR)[-2:]} - {DAYS_IN_MONTH}.{MONTH:02d}.{str(YEAR)[-2:]}',
    'time': '21:00 - 01:00',
    'price': base_amount(),
    'amount': base_amount(),
})

# 2-4. Champagne promo extra early DJ shifts at CRU (May 21/22/23), 17:00-21:00
extra_days = [21, 22, 23]
line_no = 2
for day in extra_days:
    items.append({
        'no': line_no,
        'description': f'Bubble party extra DJ at CRU on May {day}<sup>{ordinal(day)}</sup>',
        'date': f'{day:02d}.05.2026',
        'time': '17:00 - 21:00',
        'price': extra_dj_amount(),
        'amount': extra_dj_amount(),
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
print(f"Invoice #{INVOICE_NO} — May {YEAR}")
print(f"{'='*60}")
print(f"\nLine items:")
for item in items:
    import re as _re
    desc = _re.sub(r'<[^>]+>', '', item['description'])
    print(f"  {item['no']:>2}. {desc:<48} {item['amount']:>12,.2f}")
print(f"\n  {'Sub Total:':<50} {sub_total:>12,.2f} THB")
print(f"  {'VAT 7%:':<50} {vat:>12,.2f} THB")
print(f"  {'Grand Total:':<50} {grand_total:>12,.2f} THB")
print(f"  {'WHT 3%:':<50} {-wht:>12,.2f} THB")
print(f"  {'Net Amount:':<50} {net_amount:>12,.2f} THB")
print(f"\n  Written: {amount_to_words(net_amount)}")

# ---------------------------------------------------------------------------
# Render HTML
# ---------------------------------------------------------------------------

template_path = Path(__file__).parent.parent / 'templates' / 'invoice-template.html'
template_text = template_path.read_text()

if '$INVOICE_NO' in template_text:
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

save_invoice_no(INVOICE_NO, f'{YEAR}-{MONTH:02d}')
print(f"\nInvoice #{INVOICE_NO} generated.")
