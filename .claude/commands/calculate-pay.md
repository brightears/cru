---
description: Calculate DJ payments for a period
allowed-tools: Read, Write, Glob
argument-hint: [month]
context: fork
model: claude-3-5-haiku-20241022
---

Calculate payments for: $1 (e.g., "2026-02")

## Payment Rates

**DJ Hourly Rate:** TBD
**Withholding Tax:** TBD

| Slot | Hours | Gross | WHT | Net |
|------|-------|-------|-----|-----|
| CRU | 4 | TBD | TBD | TBD |
| Cocoa XO | 4 | TBD | TBD | TBD |

## Instructions

1. Read schedule from `schedules/[month]/schedule.csv`
2. Count shifts per DJ per venue
3. Calculate:
   - Total hours per DJ
   - Gross pay
   - WHT deduction
   - Net pay

## Output Format

### DJ Payment Summary - [Month]

| DJ | CRU Shifts | Cocoa XO Shifts | Total Hours | Gross | WHT | Net |
|---|---|---|---|---|---|---|

### Bright Ears Invoice to Client
- Days worked: X
- Rate: TBD/day
- Total: TBD

Save to `payments/[month]-summary.md`
