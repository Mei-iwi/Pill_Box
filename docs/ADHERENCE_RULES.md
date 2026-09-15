# Adherence rules

`TAKEN_ON_TIME`: correct slot opened within the on-time window.

`TAKEN_LATE`: correct slot opened after the on-time window but within the late tracking window. Store scheduled time, taken time and delay; do not alter the next schedule and do not give dosage advice.

`MISSED`: reminder timed out without a valid correct-slot opening.

`WRONG_SLOT`: a non-active or incorrect slot was opened. The current reminder continues until correct, timeout, or caregiver action.

The prototype never prescribes, calculates, doubles, reschedules, or claims medication safety based on sensors.
