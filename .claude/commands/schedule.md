---
description: Create or view monthly DJ schedule
allowed-tools: Read, Write, Edit, Glob
argument-hint: [month] [action]
---

Work on the DJ schedule for: $1 (e.g., "2026-02")
Action: $2 (view/create/edit, default: view)

## Schedule Requirements

**Daily slots to fill:**
- CRU 21:00-01:00 (1 DJ, 4 hours)
- Cocoa XO 21:00-01:00 (1 DJ, 4 hours)

**Total:** 2 DJ slots per day, 7 days/week = 14 slots/week

## Rules
- Match DJ genres to venue requirements (see CLAUDE.md)
- Check DJ availability notes in profiles
- Avoid scheduling same DJ at overlapping times
- Consider DJ preferences for specific venues
- Balance workload across DJs

## Schedule Format (CSV)
```
date,day,cru_2100,cocoaxo_2100
2026-02-01,Sat,DJ Name,DJ Name
```

## File Location
`schedules/[month]/schedule.csv`
