---
id: TASK-10
title: Verify schedule-flip gating is silent on hardware (Villa 164 Pool House)
status: To Do
assignee: []
created_date: '2026-10-09 17:48'
labels:
  - v3
  - gating
  - hardware
dependencies: []
priority: medium
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
v3.1.0 added a per-device "Schedule flip" gating mode: power is held on and a closed gate disarms the schedule slots instead of power-cycling the unit, which beeps on every toggle. Not yet proven on hardware: (1) whether a schedule write itself beeps, and (2) whether disarming the active slot stops diffusion promptly. Test: set Pool House (419933) to Schedule flip in Options, then listen and watch through a few HVAC cycles. Logs show "schedule slots disarmed/re-armed"; binary_sensor.*_scheduled_on gating attributes show mode and slots_gated. If schedule writes also beep, revert to Power and raise the HVAC off-delay instead.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No beep when the gate closes or opens in Schedule flip mode
- [ ] #2 Diffusion stops within about 1 minute of the gate closing and resumes after it opens
- [ ] #3 Schedule sync returns to synced after each flip (no persistent error)
<!-- AC:END -->
