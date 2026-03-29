#!/usr/bin/env python3
"""
Generate monthly invoice for Bright Ears DJ services at CRU & Cocoa XO.
Usage: python generate_invoice.py YYYY-MM [options]
"""

import argparse
import json
import re
import subprocess
import sys
from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from string import Template

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HOURLY_RATE = Decimal('900')
WHT_BUFFER_DIVISOR = Decimal('0.97')
HOURS_PER_EVENING = 4
VAT_RATE = Decimal('0.07')
WHT_RATE = Decimal('0.03')
NUM_VENUES = 2

# Derived rates
HOURLY_INVOICE_RATE = HOURLY_RATE / WHT_BUFFER_DIVISOR  # unrounded
PER_EVENING = (HOURLY_INVOICE_RATE * HOURS_PER_EVENING).quantize(
    Decimal('0.01'), rounding=ROUND_HALF_UP
)  # 3711.34

CUSTOMER = {
    'name': 'Central World Hotel Co., Ltd. (Head Office)',
    'address': '999/99 Rama I Road, Pathumwan',
    'city': 'Bangkok 10330 Thailand',
    'tax_id': '0105547030227',
}

TAX_NO = '0105550096659'

MONTH_NAMES = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

MONTH_FULL = ['', 'January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']

CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

# ---------------------------------------------------------------------------
# Number to words (with hyphens for compound numbers, decimal support)
# ---------------------------------------------------------------------------

ONES = ['', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN',
        'EIGHT', 'NINE', 'TEN', 'ELEVEN', 'TWELVE', 'THIRTEEN',
        'FOURTEEN', 'FIFTEEN', 'SIXTEEN', 'SEVENTEEN', 'EIGHTEEN', 'NINETEEN']
TENS = ['', '', 'TWENTY', 'THIRTY', 'FORTY', 'FIFTY',
        'SIXTY', 'SEVENTY', 'EIGHTY', 'NINETY']


def number_to_words(n):
    """Convert integer to English words (up to 999,999)."""
    if n == 0:
        return 'ZERO'
    if n < 20:
        return ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return TENS[tens] + ('-' + ONES[ones] if ones else '')
    if n < 1000:
        hundreds, remainder = divmod(n, 100)
        return ONES[hundreds] + ' HUNDRED' + (' ' + number_to_words(remainder) if remainder else '')
    if n < 1000000:
        thousands, remainder = divmod(n, 1000)
        return number_to_words(thousands) + ' THOUSAND' + (' ' + number_to_words(remainder) if remainder else '')
    return str(n)


def amount_to_words(amount):
    """Convert decimal amount to English words for invoice.
    Example: 229657.73 -> 'TWO HUNDRED TWENTY-NINE THOUSAND SIX HUNDRED FIFTY-SEVEN POINT SEVENTY-THREE BAHT'
    """
    amount_str = f"{amount:.2f}"
    integer_part, decimal_part = amount_str.split('.')

    words = number_to_words(int(integer_part))

    cents = int(decimal_part)
    if cents > 0:
        words += ' POINT ' + number_to_words(cents)

    return words + ' BAHT'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ordinal(n):
    """Return ordinal suffix: 1->st, 2->nd, 3->rd, else->th."""
    if 11 <= n % 100 <= 13:
        return 'th'
    return {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')


def format_date_range(year, month):
    """Format as DD.MM.YY - DD.MM.YY for base charge line."""
    days = monthrange(year, month)[1]
    yy = str(year)[-2:]
    return f"01.{month:02d}.{yy} - {days:02d}.{month:02d}.{yy}"


def format_date_single(year, month, day):
    """Format as DD.MM.YYYY for adjustment lines."""
    return f"{day:02d}.{month:02d}.{year}"


def fmt(amount):
    """Format Decimal amount for display: 3,711.34 THB"""
    return f"{amount:,.2f} THB"


# ---------------------------------------------------------------------------
# Schedule parser
# ---------------------------------------------------------------------------

def parse_schedule(schedule_path, year, month):
    """Parse schedule.md to detect guest DJ dates.
    Returns dict: {'CRU': [13, 14, 15], 'XO': [1, 20, 21]}
    """
    content = Path(schedule_path).read_text()
    month_abbr = MONTH_NAMES[month]

    guest_dj = {'CRU': [], 'XO': []}

    for line in content.split('\n'):
        match = re.match(
            r'\|\s*' + month_abbr + r'\s+(\d+)\s*\|\s*\w+\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|',
            line
        )
        if match:
            day = int(match.group(1))
            cru_dj = match.group(2).strip()
            xo_dj = match.group(3).strip()

            if 'Guest DJ' in cru_dj:
                guest_dj['CRU'].append(day)
            if 'Guest DJ' in xo_dj:
                guest_dj['XO'].append(day)

    return guest_dj


# ---------------------------------------------------------------------------
# Line item builder
# ---------------------------------------------------------------------------

def build_line_items(year, month, guest_dj, extra_hours=None):
    """Build invoice line items.

    Args:
        year, month: invoice period
        guest_dj: dict with 'CRU' and 'XO' lists of day numbers
        extra_hours: list of dicts {'venue': str, 'day': int, 'time': str, 'hours': int}

    Returns: list of line item dicts
    """
    days_in_month = monthrange(year, month)[1]
    total_venue_days = days_in_month * NUM_VENUES
    month_abbr = MONTH_NAMES[month]

    # Base charge: use unrounded rate for precision, then round total
    base_amount = (HOURLY_INVOICE_RATE * HOURS_PER_EVENING * total_venue_days).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )

    items = [{
        'no': 1,
        'description': 'Cocoa XO &amp; CRU DJ Service',
        'date': format_date_range(year, month),
        'time': '21:00 - 01:00',
        'price': base_amount,
        'amount': base_amount,
    }]

    # Build deductions sorted by date, then venue (CRU before XO for readability)
    deductions = []
    for day in guest_dj.get('CRU', []):
        deductions.append(('CRU', day))
    for day in guest_dj.get('XO', []):
        deductions.append(('XO', day))
    deductions.sort(key=lambda x: (x[1], 0 if x[0] == 'CRU' else 1))

    line_no = 2
    for venue, day in deductions:
        venue_label = 'XO' if venue == 'XO' else 'CRU'
        items.append({
            'no': line_no,
            'description': f'No DJ at {venue_label} on {month_abbr} {day}<sup>{ordinal(day)}</sup>',
            'date': format_date_single(year, month, day),
            'time': '-',
            'price': -PER_EVENING,
            'amount': -PER_EVENING,
        })
        line_no += 1

    # Extra partial hours (e.g., 2-hour sets on otherwise cancelled days)
    if extra_hours:
        for eh in extra_hours:
            venue = eh['venue']
            day = eh['day']
            time_range = eh['time']
            hours = eh['hours']

            venue_label = 'XO' if venue == 'XO' else 'CRU'
            partial_amount = (HOURLY_INVOICE_RATE * hours).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            # Only deduct full evening if not already deducted via guest_dj
            already_deducted = day in guest_dj.get(venue, [])
            if not already_deducted:
                items.append({
                    'no': line_no,
                    'description': f'No DJ at {venue_label} on {month_abbr} {day}<sup>{ordinal(day)}</sup>',
                    'date': format_date_single(year, month, day),
                    'time': '-',
                    'price': -PER_EVENING,
                    'amount': -PER_EVENING,
                })
                line_no += 1

            # Add back partial hours
            items.append({
                'no': line_no,
                'description': f'DJ at {venue_label} on {month_abbr} {day}<sup>{ordinal(day)}</sup>',
                'date': format_date_single(year, month, day),
                'time': time_range,
                'price': partial_amount,
                'amount': partial_amount,
            })
            line_no += 1

    return items


def build_line_items_html(items):
    """Convert line items to HTML table rows."""
    rows = []
    for item in items:
        price_str = fmt(item['price'])
        amount_str = fmt(item['amount'])
        rows.append(f"""    <tr>
      <td class="col-no">{item['no']}</td>
      <td class="col-desc">{item['description']}</td>
      <td class="col-date">{item['date']}</td>
      <td class="col-time">{item['time']}</td>
      <td class="col-price">{price_str}</td>
      <td class="col-amount">{amount_str}</td>
    </tr>""")
    return '\n'.join(rows)


# ---------------------------------------------------------------------------
# Invoice config (number tracking)
# ---------------------------------------------------------------------------

def get_config_path():
    return Path(__file__).parent.parent / 'invoice_config.json'


def get_next_invoice_no():
    config_path = get_config_path()
    if config_path.exists():
        config = json.loads(config_path.read_text())
        return config['last_invoice_no'] + 1
    return None


def save_invoice_no(invoice_no, month_str):
    config_path = get_config_path()
    config = {'last_invoice_no': invoice_no, 'last_invoice_month': month_str}
    config_path.write_text(json.dumps(config, indent=2) + '\n')


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def generate_pdf(html_path, pdf_path):
    """Convert HTML to PDF using Chrome headless."""
    cmd = [
        CHROME,
        '--headless=new',
        '--disable-gpu',
        f'--print-to-pdf={pdf_path}',
        '--print-to-pdf-no-header',
        f'file://{html_path}',
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Warning: PDF generation may have issues: {result.stderr[:200]}")
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_extra_arg(extra_str):
    """Parse --extra argument: 'CRU:17:17:00-19:00' -> dict"""
    parts = extra_str.split(':')
    if len(parts) < 3:
        print(f"Error: Invalid --extra format: {extra_str}")
        print("Expected: VENUE:DAY:START-END (e.g., CRU:17:17:00-19:00)")
        sys.exit(1)

    venue = parts[0].upper()
    day = int(parts[1])
    time_range = ':'.join(parts[2:])  # rejoin in case time has colons

    # Parse hours from time range
    time_match = re.match(r'(\d+):(\d+)-(\d+):(\d+)', time_range)
    if time_match:
        start_h = int(time_match.group(1))
        end_h = int(time_match.group(3))
        hours = end_h - start_h
        if hours < 0:
            hours += 24  # overnight
    else:
        hours = 2  # default

    return {
        'venue': venue,
        'day': day,
        'time': time_range.replace('-', ' - '),
        'hours': hours,
    }


def parse_args():
    parser = argparse.ArgumentParser(description='Generate Bright Ears monthly invoice')
    parser.add_argument('month', help='Invoice month (YYYY-MM)')
    parser.add_argument('--invoice-no', type=int, help='Invoice number (auto-increments if omitted)')
    parser.add_argument('--date', help='Invoice date (DD.MM.YYYY, defaults to today)')
    parser.add_argument('--no-dj', action='append', help='No DJ dates: VENUE:DAY,DAY,... (e.g., CRU:1,17,18)')
    parser.add_argument('--extra', action='append', help='Extra partial hours: VENUE:DAY:START-END')
    parser.add_argument('--html-only', action='store_true', help='Skip PDF generation')
    parser.add_argument('--dry-run', action='store_true', help='Preview calculations only')
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    year, month = map(int, args.month.split('-'))
    month_str = f"{year}-{month:02d}"

    # 1. Invoice number
    if args.invoice_no:
        invoice_no = args.invoice_no
    else:
        invoice_no = get_next_invoice_no()
        if invoice_no is None:
            print("Error: No previous invoice found. Use --invoice-no to set the first number.")
            sys.exit(1)

    # 2. Parse schedule for guest DJ dates
    schedule_path = Path(__file__).parent.parent.parent / 'schedules' / month_str / 'schedule.md'
    if schedule_path.exists():
        guest_dj = parse_schedule(schedule_path, year, month)
        print(f"Auto-detected from schedule ({schedule_path.name}):")
        if guest_dj['CRU']:
            print(f"  CRU guest DJ dates: {guest_dj['CRU']}")
        if guest_dj['XO']:
            print(f"  XO guest DJ dates:  {guest_dj['XO']}")
        if not guest_dj['CRU'] and not guest_dj['XO']:
            print("  No guest DJ dates found (full month)")
    else:
        print(f"Warning: Schedule not found at {schedule_path}")
        guest_dj = {'CRU': [], 'XO': []}

    # 3. Apply manual --no-dj overrides
    if args.no_dj:
        for nd in args.no_dj:
            parts = nd.split(':')
            venue = parts[0].upper()
            days = [int(d) for d in parts[1].split(',')]
            if venue in guest_dj:
                for d in days:
                    if d not in guest_dj[venue]:
                        guest_dj[venue].append(d)
            else:
                guest_dj[venue] = days
        guest_dj['CRU'].sort()
        guest_dj['XO'].sort()

    # 4. Parse extra hours
    extra_hours = [parse_extra_arg(e) for e in args.extra] if args.extra else None

    # 5. Build line items
    items = build_line_items(year, month, guest_dj, extra_hours)

    # 6. Calculate totals
    sub_total = sum(item['amount'] for item in items)
    vat = (sub_total * VAT_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    grand_total = sub_total + vat
    wht = (sub_total * WHT_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    net_amount = grand_total - wht

    # 7. Print summary
    print(f"\n{'='*50}")
    print(f"Invoice #{invoice_no} — {MONTH_FULL[month]} {year}")
    print(f"{'='*50}")
    print(f"\nLine items:")
    for item in items:
        desc = re.sub(r'<[^>]+>', '', item['description'])  # strip HTML for display
        print(f"  {item['no']:>2}. {desc:<40} {item['amount']:>12,.2f}")
    print(f"\n  {'Sub Total:':<42} {sub_total:>12,.2f} THB")
    print(f"  {'VAT 7%:':<42} {vat:>12,.2f} THB")
    print(f"  {'Grand Total:':<42} {grand_total:>12,.2f} THB")
    print(f"  {'WHT 3%:':<42} {-wht:>12,.2f} THB")
    print(f"  {'Net Amount:':<42} {net_amount:>12,.2f} THB")
    print(f"\n  Written: {amount_to_words(net_amount)}")

    if args.dry_run:
        print("\n[Dry run — no files generated]")
        return

    # 7. Load template and generate HTML
    template_path = Path(__file__).parent.parent / 'templates' / 'invoice-template.html'
    template = Template(template_path.read_text())

    invoice_date = args.date or date.today().strftime('%d.%m.%Y')

    html = template.safe_substitute(
        INVOICE_NO=f'# {invoice_no}',
        INVOICE_DATE=invoice_date,
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

    # 8. Write output
    output_dir = Path(__file__).parent.parent / month_str
    output_dir.mkdir(exist_ok=True)

    month_abbr = MONTH_NAMES[month].lower()
    filename_base = f"invoice-{invoice_no}-{month_abbr}{year}"

    html_path = output_dir / f"{filename_base}.html"
    html_path.write_text(html)
    print(f"\nHTML: {html_path}")

    # 9. Generate PDF
    if not args.html_only:
        pdf_path = output_dir / f"{filename_base}.pdf"
        print(f"Generating PDF...")
        generate_pdf(str(html_path.resolve()), str(pdf_path.resolve()))
        print(f"PDF:  {pdf_path}")

    # 10. Update invoice counter
    save_invoice_no(invoice_no, month_str)
    print(f"\nInvoice #{invoice_no} generated successfully.")


if __name__ == '__main__':
    main()
