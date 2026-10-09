---
id: TASK-6
title: >-
  Phase C: migrate Cauldron + Villa 164 to upstream integration once feature
  parity lands
status: Deferred
assignee: []
created_date: '2026-07-14 23:52'
updated_date: '2026-10-09 16:35'
labels:
  - convergence
  - phase-c
  - cauldron
dependencies:
  - TASK-2
  - TASK-1
  - TASK-3
priority: low
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rescoped 2026-10-09 for v3. Gated on upstream merging the Phase B PRs (TASK-2, TASK-1, TASK-3). The fork now runs at TWO sites on the same Aroma-Link account, with different devices: Cauldron (372377 Kitchen, 397405 Foyer) and Villa 164 (419931 Main House, 419933 Pool House). Both have gates configured in Options. Migration per site: install aromalink_ha_integration; carry over the HA-owned schedule model and gate options (export from the store); rename the 17 entities per device back to current IDs; re-point dashboards using custom:aroma-link-schedule-card (Cauldron: aroma-link, md3-port, md3-wall, cauldron-v2; Villa 164: check). Then archive cjam28/homeassistant_aroma-link. No blueprint automations remain (v3 removed them).
<!-- SECTION:DESCRIPTION:END -->
