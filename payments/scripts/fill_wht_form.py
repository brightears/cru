#!/usr/bin/env python3
"""
Fill Thai Withholding Tax Form (ภ.ง.ด.3) with DJ payment data.
Usage: python fill_wht_form.py <dj_name> <amount> <tax> <output_path>
"""

import os
import subprocess
import sys
from pathlib import Path
from pypdf import PdfReader, PdfWriter

MONTH_MAP = {
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
    'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
}


def precheck_tracker_open_items(venue_label, month_short, year_str):
    """Refuse to generate WHT if BrightEars-Ops tracker .md files have unresolved
    items for the same venue+month. Born from 2026-05-23 Linze Apr 29 miss — the
    May 18 tracker flagged the discrepancy 5 days early and was ignored.

    Override via env: WHT_ALLOW_OPEN_ITEMS=1 (use only after items are confirmed
    resolved with Norbert).
    """
    m = MONTH_MAP.get((month_short or '').lower())
    if not m or not year_str:
        return
    month_filter = f"{year_str}-{m}"

    v = (venue_label or '').lower()
    if 'cru' in v or 'cocoa' in v:
        venue_filter = 'cru'  # matches cocoa-cru-*-tracker.md filename
    elif 'nobu' in v:
        venue_filter = 'nobu'
    elif 'ldk' in v or 'kaan' in v:
        venue_filter = 'ldk'
    elif 'abar' in v:
        venue_filter = 'abar'
    elif 'horizon' in v:
        venue_filter = 'horizon'
    else:
        venue_filter = None

    scanner = Path('/home/brightears/BrightEars-Ops/scripts/scan-open-tracker-items.py')
    if not scanner.exists():
        return

    cmd = ['python3', str(scanner), '--month', month_filter, '--no-heartbeat']
    if venue_filter:
        cmd.extend(['--venue', venue_filter])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return

    print('=' * 72)
    print('TRACKER OPEN ITEMS DETECTED — refusing to generate WHT.')
    print(f'Scanner filter: venue={venue_filter or "(none)"} month={month_filter}')
    print('-' * 72)
    print(result.stdout.rstrip())
    print('=' * 72)
    if os.environ.get('WHT_ALLOW_OPEN_ITEMS') == '1':
        print('OVERRIDE: WHT_ALLOW_OPEN_ITEMS=1 set; continuing despite open items.')
        return
    print('Resolve each line above with Norbert BEFORE re-running.')
    print('Override (only if items confirmed resolved): WHT_ALLOW_OPEN_ITEMS=1')
    sys.exit(2)

# Number to words conversion for Thai WHT forms (English)
ONES = ['', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE',
        'TEN', 'ELEVEN', 'TWELVE', 'THIRTEEN', 'FOURTEEN', 'FIFTEEN', 'SIXTEEN',
        'SEVENTEEN', 'EIGHTEEN', 'NINETEEN']
TENS = ['', '', 'TWENTY', 'THIRTY', 'FORTY', 'FIFTY', 'SIXTY', 'SEVENTY', 'EIGHTY', 'NINETY']

def number_to_words(n):
    """Convert number to English words (for amounts up to 999,999)."""
    if n == 0:
        return 'ZERO'

    if n < 20:
        return ONES[n]

    if n < 100:
        tens, ones = divmod(n, 10)
        return TENS[tens] + (' ' + ONES[ones] if ones else '')

    if n < 1000:
        hundreds, remainder = divmod(n, 100)
        return ONES[hundreds] + ' HUNDRED' + (' ' + number_to_words(remainder) if remainder else '')

    if n < 1000000:
        thousands, remainder = divmod(n, 1000)
        return number_to_words(thousands) + ' THOUSAND' + (' ' + number_to_words(remainder) if remainder else '')

    return str(n)  # Fallback for very large numbers

def detect_field_names(reader):
    """Detect which field naming convention the template uses."""
    fields = reader.get_fields()

    # Check if template uses pay1.13.1 or pay1.13
    if 'pay1.13.1' in fields:
        return 'pay1.13.1', 'tax1.13.1'
    else:
        return 'pay1.13', 'tax1.13'

def fill_wht_form(template_path, output_path, amount, tax, day, month, year):
    """Fill WHT form with new values."""
    reader = PdfReader(template_path)
    writer = PdfWriter()

    # Add pages from reader
    writer.append(reader)

    # Detect field names for this template
    pay_field, tax_field = detect_field_names(reader)

    # Convert tax to words
    tax_words = number_to_words(int(tax)) + " BAHT"

    # Fields to update
    updates = {
        pay_field: f"{amount:,.2f}",        # Amount in row 6 (e.g., 9,600.00)
        tax_field: f"{tax:,.2f}",           # Tax withheld in row 6 (e.g., 480.00)
        'total': tax_words,                  # Written amount
        'date_pay': str(day),               # Day
        'month_pay': f"      {month}",      # Month (with spacing)
        'year_pay': str(year),              # Year
    }

    # Update fields on page 0 with auto_regenerate to embed appearances
    writer.update_page_form_field_values(writer.pages[0], updates, auto_regenerate=True)

    # Remove NeedAppearances flag to ensure embedded appearances are used
    if '/AcroForm' in writer._root_object:
        acroform = writer._root_object['/AcroForm']
        if '/NeedAppearances' in acroform:
            del acroform['/NeedAppearances']

    # Write output
    with open(output_path, 'wb') as f:
        writer.write(f)

    return tax_words

def main():
    if len(sys.argv) < 5:
        print("Usage: python fill_wht_form.py <dj_name> <amount> <tax> <output_folder> [month] [year] [venue]")
        print("Example: python fill_wht_form.py pound 9600 480 2025-12/wht dec 2025 'CRU & Cocoa XO'")
        print("         python fill_wht_form.py pound 9600 480 2025-12/wht/pound-wht.pdf  (legacy mode)")
        sys.exit(1)

    dj_name = sys.argv[1].lower()
    amount = float(sys.argv[2])
    tax = float(sys.argv[3])
    output_arg = sys.argv[4]

    # Check if using new format (folder) or legacy format (full path)
    if output_arg.endswith('.pdf'):
        # Legacy mode - full path provided
        output_path = output_arg
    else:
        # New mode - folder provided, generate filename with metadata
        month = sys.argv[5] if len(sys.argv) > 5 else None
        year = sys.argv[6] if len(sys.argv) > 6 else None
        venue = sys.argv[7] if len(sys.argv) > 7 else "CRU & Cocoa XO"

        # Create descriptive filename
        # e.g., "pound-dec2025-cru-cocoaxo-wht.pdf"
        venue_short = venue.lower().replace(' & ', '-').replace(' ', '').replace('cocoa', 'cocoa')
        if month and year:
            filename = f"{dj_name}-{month}{year}-{venue_short}-wht.pdf"
        else:
            filename = f"{dj_name}-wht.pdf"

        output_path = f"{output_arg}/{filename}"

        # Pre-check: bail if BrightEars-Ops tracker has unresolved items for this
        # venue+month. See `feedback_scan_tracker_open_items_before_wht.md`.
        precheck_tracker_open_items(venue, month, year)

    # Get template path
    script_dir = Path(__file__).parent
    template_path = script_dir.parent / 'templates' / f'wht-{dj_name}.pdf'

    if not template_path.exists():
        print(f"Error: Template not found: {template_path}")
        sys.exit(1)

    # Get current date
    from datetime import date
    today = date.today()

    # Fill form
    tax_words = fill_wht_form(
        template_path,
        output_path,
        amount,
        tax,
        today.day,
        today.month,
        today.year
    )

    print(f"WHT form filled successfully!")
    print(f"  DJ: {dj_name.title()}")
    print(f"  Amount: ฿{amount:,.2f}")
    print(f"  Tax (5%): ฿{tax:,.2f}")
    print(f"  Written: {tax_words}")
    print(f"  Date: {today.strftime('%d/%m/%Y')}")
    print(f"  Output: {output_path}")

if __name__ == '__main__':
    main()
