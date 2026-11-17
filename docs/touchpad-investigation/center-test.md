# Labeled center test, 2026-11-05

The user clarified that the physical center of the touchpad was unreliable,
confirmed readiness for a touchpad-only test, then reported: "done center is
problematic". The requested action was slow one-finger center strokes for
15 seconds followed by edge strokes for 15 seconds, without pressing down.
The hand trajectory and actual finger count were not independently filmed.

The test started at wall-clock nanoseconds `1793889805261506476`, monotonic
nanoseconds `101152803082593`. Evidence is preserved under
`~/.local/state/touchpad-investigation/2026-11-05/captures/ready-test-1793889805261412975/`.
The `raw-preserved/` directory copies the available raw JSON recordings out
of the recorder's rolling retention. `raw-manifest.json` records hashes.

## Observations

- XInput recorded 2,300 raw motion events from touchpad source ID 10.
- That source emitted 65 scroll-button presses and one left-button press,
  each with a matching release. The 65 scroll events comprise button 5:
  36, button 6: 10, button 4: 10, and button 7: 9. These are X11 scroll
  emulation events, not 65 physical button presses.
- The wireless mouse, source 20, also produced events within the full
  recording interval. These were counted separately. They may include
  later navigation and the user's reply; they are not attributed to the pad.
- The raw window `touchpad-manual-1793889835718194739.json` includes 2,650
  touchpad SYN frames at or after test start. Of these, 2,454 have one active
  contact, 155 have two, and 41 have none in a slot-state reconstruction.
- There are repeated contact end/start transitions near X coordinates
  around 1,300 and 1,620. The interval between those bands has very few
  samples, although some later contacts cross it. This is a spatial lead,
  not proof of a permanent dead strip or known physical trajectory.
- Palm-tool transitions in this raw window precede the test start. The
  current evidence does not establish the stale-palm reopen failure fixed
  in libinput 1.32.0.

## Interpretation and limits

This is a labeled failure interval, unlike the earlier unlabelled captures.
The combination of reported one-finger use, two kernel contacts and X11
scroll output is consistent with contact splitting or an extra contact.
Unobserved extra physical contact remains possible. It is not yet a proven
firmware defect, kernel defect or hardware failure.

The XInput CLI does not print the raw event timestamps in this output.
Clock anchors and event ordering identify the test interval but do not
permit exact frame-by-frame pairing with evdev. Therefore individual scroll
events have not been causally matched to individual two-contact frames.

A raw HID plus evdev recording is still required to determine whether
Contact IDs, Tip/Confidence bits or coordinates are already wrong in the
device reports, or first become wrong in kernel decoding. The prepared
standard-tool capture requires administrator read access. A renewed private
credential request timed out, so no privileged capture ran.

The unsuccessful settings trial remains reverted. No driver, firmware,
quirk or input setting was changed during this test or analysis.
