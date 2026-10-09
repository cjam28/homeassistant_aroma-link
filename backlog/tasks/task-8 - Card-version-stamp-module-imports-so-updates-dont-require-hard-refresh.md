---
id: TASK-8
title: 'Card: version-stamp module imports so updates don''t require hard refresh'
status: Done
assignee: []
created_date: '2026-07-16 00:50'
updated_date: '2026-10-09 16:35'
labels:
  - aroma-link
  - v3
  - card
dependencies: []
modified_files:
  - custom_components/aroma_link_integration/__init__.py
  - custom_components/aroma_link_integration/manifest.json
priority: low
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The card's cache-buster (?v=hash) applies only to the entry resource URL; sub-module imports (./al-model.js etc.) are bare specifiers the browser caches heuristically. After a card update, a fresh entry can pair with stale cached modules (e.g. importing removeWindows from an old al-model.js) producing a Lovelace 'config error' until the user hard-refreshes — standard HACS-card annoyance, but fixable: add a release step that stamps a ?v=<version> query onto every relative import specifier in www/*.js (simple sed in a release script or pre-commit), so bumping the manifest version busts the whole module graph atomically.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Shipped in v3.0.9. Instead of stamping ?v= onto every import, www/ is mounted at /aroma_link_integration_card/<content-hash>/, so relative sub-module imports resolve under the new hash and the whole module graph refreshes on any asset change. No release step needed. _add_lovelace_resource matches any legacy card URL and migrates it in place; the unversioned /aroma_link_integration mount stays for back-compat.
<!-- SECTION:FINAL_SUMMARY:END -->
