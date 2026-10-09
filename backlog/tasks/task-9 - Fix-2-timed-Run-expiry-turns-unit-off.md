---
id: TASK-9
title: 'Fix #2: timed Run expiry turns unit off'
status: Done
assignee: []
created_date: '2026-10-09 15:30'
labels:
  - bug
  - timed-run
dependencies: []
modified_files:
  - custom_components/aroma_link_integration/timed_run.py
  - custom_components/aroma_link_integration/store.py
  - custom_components/aroma_link_integration/models.py
  - custom_components/aroma_link_integration/manifest.json
  - tests/test_models.py
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
GitHub issue #2 (@chrkov): pressing Run sprays, then turns the whole unit off when the run ends. Still present in v3.0.7 because TimedRunManager._expire() always sent power off.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Shipped in v3.0.8. Expiry clears the overlay and run, then hands power back: with the schedule enabled the gating engine decides; otherwise the pre-run power state (new TimedRunState.prior_power) is restored. Pure helper models.timed_run_expiry_power is unit-tested. Deployed to Cauldron and Villa 164 via HACS; issue #2 closed.
<!-- SECTION:FINAL_SUMMARY:END -->
