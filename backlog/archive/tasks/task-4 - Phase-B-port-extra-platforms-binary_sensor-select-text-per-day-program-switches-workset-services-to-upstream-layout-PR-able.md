---
id: TASK-4
title: >-
  Phase B: port extra platforms (binary_sensor/select/text, per-day program
  switches, workset services) to upstream layout (PR-able)
status: Deferred
assignee: []
created_date: '2026-07-14 23:52'
updated_date: '2026-10-09 16:35'
labels:
  - convergence
  - phase-b
dependencies: []
priority: medium
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Package the platforms and schedule-matrix/workset services upstream lacks (binary_sensor, select, text, per-day program switches, schedule_active, batch save/load workset) for upstream's layout. PR-able unit; do NOT open the upstream PR until the user says go.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-09: obsolete. v3.0.0 deliberately removed these platforms (select/text/per-day program switches, workset services; ~51 entities down to 17 per device). The card plus ws API replaced them. Archived.
<!-- SECTION:NOTES:END -->
