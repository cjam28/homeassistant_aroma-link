---
id: TASK-10
title: Verify schedule-flip gating is silent on hardware (Villa 164 Pool House)
status: In Progress
assignee: []
created_date: '2026-10-09 17:48'
updated_date: '2026-10-09 18:14'
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
- [x] #1 No beep when the gate closes or opens in Schedule flip mode
- [ ] #2 Diffusion stops within about 1 minute of the gate closing and resumes after it opens
- [ ] #3 Schedule sync returns to synced after each flip (no persistent error)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-09 18:07 UTC, first live test on Main House (419931) in Schedule flip mode, not Pool House: the gate closed when the Ecobee fan stopped (hvac_action fan -> idle). The engine set slots_gated=true and power stayed on (power last changed 17:50). User heard NO beep on gate close. Still pending: confirm the device actually stopped misting (work 10 s / pause 200 s, so within ~3.5 min), and test gate re-open (no beep, misting resumes).

2026-10-09 18:11 UTC, gate reopen: cooling resumed at 18:09:55; after the on-delay (~1 min) the engine re-armed the slots (slots_gated=false) at 18:11:13 with power untouched. User heard NO beep on reopen and the device went back on. Silent both ways on Main House. Not yet re-checked: Pool House, Night Owl on hardware, and sync health over a full day.
<!-- SECTION:NOTES:END -->
