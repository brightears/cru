#!/usr/bin/env python3
"""
Fill Thai Withholding Tax Form (ภ.ง.ด.3) with DJ payment data.
Usage: python fill_wht_form.py <dj_name> <amount> <tax> <output_path>
"""

import sys
from pathlib import Path
from pypdf import PdfReader, PdfWriter

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
