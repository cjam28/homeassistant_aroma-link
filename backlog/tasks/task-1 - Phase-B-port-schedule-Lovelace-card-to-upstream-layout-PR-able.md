---
id: TASK-1
title: 'Phase B: port schedule Lovelace card to upstream layout (PR-able)'
status: Deferred
assignee: []
created_date: '2026-07-14 23:52'
updated_date: '2026-10-09 16:35'
labels:
  - convergence
  - phase-b
dependencies:
  - TASK-2
priority: medium
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rescoped 2026-10-09 for v3. Port the v3 schedule card (vendored Lit, multi-module www/: al-*.js + aroma-link-schedule-card.js), its ws API (aroma_link/* commands + aroma_link_integration_updated event), and the content-hashed static mount + Lovelace resource auto-registration (3.0.9, TASK-8) to upstream's aromalink_ha_integration domain/layout, as a PR-able unit. Depends on TASK-2 (v3 core). Do NOT open the upstream PR until the user says go.
<!-- SECTION:DESCRIPTION:END -->
