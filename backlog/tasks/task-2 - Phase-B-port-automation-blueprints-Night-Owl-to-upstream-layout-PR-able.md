---
id: TASK-2
title: >-
  Phase B: port v3 core (models, reconciler, gating engine, Night Owl) to
  upstream layout (PR-able)
status: Deferred
assignee: []
created_date: '2026-07-14 23:52'
updated_date: '2026-10-09 16:35'
labels:
  - phase-b
  - upstream
  - v3
dependencies: []
priority: medium
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rescoped 2026-10-09 for v3. The blueprints this task originally ported no longer exist: v3.0.0 replaced all three with the native gating engine. The foundation PR is now the v3 "power-gated" core: models.py (HA-owned schedule, Mon=0 with Sun=0 cloud conversion), store.py, reconciler.py (single slot writer, verify-after-write, hourly drift heal), engine.py (HVAC/occupancy gates with per-gate off-delays, motion-gated Night Owl), timed_run.py (persisted runs, 3.0.8 expiry hand-back) and migration.py, adapted to upstream's aromalink_ha_integration domain/layout. TASK-1 and TASK-3 build on this. Do NOT open the upstream PR until the user says go.
<!-- SECTION:DESCRIPTION:END -->
