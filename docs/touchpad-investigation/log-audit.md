# Touchpad log audit, 2026-11-05

## Findings and limits

The retained records contain real ELAN input anomalies. There are **17 Xorg touch-jump warnings and 17 matching Touchégg warnings**, grouped into 13 bursts on seven boots. Two kernel I2C-HID incomplete-report errors were logged during resume on separate dates. These findings justify investigating the device, firmware, HID decoding and kernel input path. They do not establish that every interaction error described by the user has that cause. No retained raw recording overlaps any of the 17 warning events. See the [jump ledger](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/jump-episodes.json) and [kernel evidence](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/kernel-warning-ledger.jsonl).

The requested period is **2026-08-05 00:00:00 through the audit snapshot at 2026-11-05 16:42:16.991993, Asia/Karachi, UTC+05:00**. The journal starts at **2026-10-03 19:23:00.672404**. There is no available general system/input log coverage for the preceding 59 days, 19 hours and 23 minutes. Today's time after the snapshot is outside the counted dataset. Later read-only verification and static probes are identified in the command ledger.

All 13 available incident files were examined, including their initial slot state. They contain 58,475 saved events, or 46,484 distinct events after removing overlaps within each boot. The largest same-contact movement within 20 ms is **3.284 mm**. This does not identify bad movement without a known finger trajectory. No retained event reaches the recorder's 40 mm threshold. There are no raw `SYN_DROPPED` markers, but that does not rule out hardware report loss or smaller errors. Synthetic replay completion is **not evidence that the touchpad behaved correctly**. [Trace summary](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/trace-summary.json), [deduplicated totals](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/trace-aggregate.json).

The strongest remaining blocker is the absence of a labeled failure with simultaneous raw contacts, generated pointer/button events and known finger motion. A second machine's hardware identity and logs are also unavailable. The recurrence on two machines is user testimony, not a verified common firmware or software cause.

## Scope and method

This was a read-only system audit. No settings, drivers, bindings, services, packages, accessibility or speech settings were changed. No logs were deleted. No additional mark was taken because there was no newly labeled live occurrence. Evidence and analysis programs were written only under `/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs`; this report is the only repository addition. Existing edits to `.codex/AGENTS.md` and `docs/touchpad-recovery.md` were preserved.

The audit streamed **1,023,421 journal records**, including accessible system and user journals across 12 retained boots and 34 calendar dates. A separate all-boot `_TRANSPORT=kernel` scan read **51,148 kernel records**. It inventoried 241 log/evidence files and scanned 75 relevant text log files and rotations, plus all 31 sysstat files and targeted authentication records. The inventory includes unrelated log families as metadata only; unrelated application histories were not collected. Exact source paths, sizes, access failures and date ranges are in the [source inventory](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/source-inventory.json) and [text coverage ledger](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/file-coverage.json).

Broad regex matches are discovery candidates, not confirmed fault totals. For example, a search for `gpu.*error` also catches ordinary application log text. Reported totals use the explicitly classified ledgers, not the broad category counts in `journal-summary.json` or `file-coverage.json`. System journal messages mirrored into syslog, kern.log and Xorg logs are counted once. Xorg and Touchégg are separate libinput consumers, not separate touchpads. Their jump warnings were matched within 25 ms, keeping each Xorg warning separate even in a fast burst. Exact matching times are retained. A burst ends after a gap greater than one second. No true physical failure count can be recovered from rate-limited warnings.

The diagnosis skill's live reproduction and fix phases do not apply to this historical audit. No deterministic test of the user's exact symptom was obtained, and no repair is claimed. The existing replay command exercises a custom threshold detector, not the running libinput/Xorg pipeline.

## Machine and current state

The machine reports HP EliteBook 840 14 inch G10 Notebook PC, BIOS `V70 Ver. 01.11.00`, BIOS date string `11/06/2025`, kernel `6.17.9-76061709-generic`, Pop GNOME 22.04 on X11. ELAN bus/vendor/product are `0018:04F3:31EC`, name `ELAN07AC:00 04F3:31EC Touchpad`, connected through `i2c_hid_acpi` and `hid-multitouch`. Its sibling node is named `ELAN07AC:00 04F3:31EC Mouse`. Numeric event nodes and X11 IDs change when devices reconnect. [Hardware snapshot](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/hardware.txt).

Installed packages are `libinput10` and `libinput-bin` `1.20.0-1ubuntu0.3`, `xserver-xorg-input-libinput` `1.2.1-1`, and Touchégg `2.0.15pop0~1674691430~22.04~2e20838`. No changes to these packages, kernel images/modules, firmware, GNOME Shell or Mutter were found in retained dpkg transaction logs within the requested dates. This says nothing about manual binary replacements. [Package versions](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/packages.txt), [package-history result](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/stack-package-history.json).

At inspection, GNOME speed was `0.73529411764705888`, tap-and-drag was `true`, and X11 showed speed `0.735294`, tapping and tapping-drag enabled, drag-lock off, adaptive acceleration, two-finger natural scrolling, clickfinger, and disable-while-typing enabled. The unsuccessful speed `0` / tap-and-drag `false` trial was already reverted by the parent session. It is not a fix and was not repeated. [X11 properties](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/input-settings.txt), [existing recovery note](../touchpad-recovery.md).

The recorder is active, with current service start November 3 at 13:00:46 and `NRestarts=0`. Its status listed both expected sources and `automatic_reset:false`. Repository and installed recorder copies have identical SHA-256 `a293bc73c33cf15809f846741d5421c6b4562d82cedcbdf75b7ae2948a1a02a6`. This verifies the inspected code for the current installation; it does not prove older installed copies were identical. [Service state](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/watch-status.txt), [recorder source](../../scripts/touchpad-watch.py).

## Retention and access gaps

| Source | Retained coverage or access | What remains unavailable |
|---|---|---|
| System and user journals | October 3 19:23 through November 5 snapshot, 12 boots, 1.0 GiB reported usage | August 5 through October 3 19:23; first retained boot is partial; silence within a boot is not proof of continuous logging |
| Journal retention configuration | `/usr/lib/systemd/journald.conf.d/pop.conf` sets `SystemMaxUse=1000M` | A size limit does not guarantee three months of retention; historic vacuum events are not available |
| Journal validation | 21 files pass `journalctl --verify`, including `.journal~` files; one `Unused data (entry_offset==0)` notice | Passing structural validation cannot recover suppressed or overwritten entries or establish complete history |
| `syslog`, `.1`, `.2.gz` through `.4.gz` | October 4 17:17:25 onward; newest text scan reached November 5 16:43:28 | Earlier general desktop/system messages; four weekly rotations configured |
| `kern.log` and four rotations | October 4 17:17:30 to November 5 16:30:38 | Earlier kernel diagnostics; duplicates journal kernel messages |
| `dmesg`, `.0`, `.1.gz` through `.4.gz` | Boot snapshots dated October 22, 24, 27, 28, 30 and November 3 | Boot-time snapshots do not record full sessions; direct current `dmesg` access denied |
| User Xorg log | Current session boot November 3, monotonic 23.222 to 89586.580; two jump warnings | Earlier sessions beyond `.old`; no raw pointer-motion log |
| User Xorg `.old` | Previous session boot October 30, monotonic 37.162 to 139751.689 | No additional jump warnings in this file; file mtime is not its session start |
| GDM logs and `/var/lib/gdm3/.local/share/xorg` | Traversal/listing denied | Root/GDM session logs cannot be assessed |
| Recorder | First retained service start October 11 00:44:21.073540; 13 manual files October 14 through November 5 | No persistent raw history before those files, between captures or at logged jump events; no candidate files |
| Recorder ring/retention | Up to 60 seconds or 50,000 events; at most 20 manual and 20 candidate files | Historical recorder memory is gone. No deletion is established merely from this limit. All extant files say `truncated:false` |
| Sysstat `sa06` through `sa31`, `sa01` through `sa05` | Headers date October 6 through November 5 | All 31 files return zero CPU/run-queue/memory samples with `sadf`; no resource time series to correlate |
| Auth logs and rotations | Readable; targeted manual reset/install records extracted | Not input telemetry; unrelated auth records were not exported |
| dpkg/APT history and rotations | Files extend before August; all relevant dated dpkg transactions inspected | No stack package transactions in the period; not evidence of input behavior |
| Apport rotations and `/var/crash` | Rotations inspected; only retained crash file is `/usr/bin/ps` on October 24 | No retained Touchégg/Xorg crash artifact; system coredump directory is empty |
| `/sys/fs/pstore` | Directory listing denied | Persistent kernel crash records, if any, cannot be assessed |
| `wtmp` | Reboot/shutdown records reach August and earlier, including August 7 | Lifecycle accounting only; unusual overlapping shutdown accounting is not reliable input-uptime coverage |
| Other conventional session paths | No `~/.xsession-errors`, `.old`, `~/.cache/upstart`, `/var/log/messages`, `/var/log/lightdm` or `/var/log/audit` | No alternative historical input/session log there |
| Other machine | No logs or hardware metadata supplied or present in this evidence set | Cannot compare controllers, firmware, drivers, OS versions or failure timing |

`sudo -n true` returned `sudo: a password is required`; no credential prompt or privileged fallback was used. Membership in `adm` permits the readable system logs above. [Access probes](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/extra-access.txt), [dmesg access](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/dmesg-access.txt), [journal config](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/journal-config.txt), [journal verification](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/journal-verify.txt), [user boot coverage](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/user-boots.txt), [sysstat ledger](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/sysstat-coverage.json), [wtmp](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/wtmp.txt).

There are explicit losses inside the retained interval:

- 23 journald suppression notices report **153,221 messages** suppressed from `user@1000.service`. Three notices near the October 22 desktop bursts alone report 30,227, 20,015 and 64,905 messages. These notices identify the service, not the contents of the lost messages.
- Nine rsyslog notices on October 11 from 02:44:57.057498 to 02:45:50.006960 report **12,540 messages lost** with a 500 messages / 5 seconds limit. Those notices exist in the journal even though their text-file forwarding is incomplete.
- Kernel callback suppression totals **6,507 callbacks** across 253 notices, mostly `kauditd_printk_skb`, plus `show_signal_msg`. This is not 6,507 touchpad events; it limits what kernel/audit silence can establish.
- Both libinput clients explicitly exceed **five messages per 24 hours** on October 5 at 11:37:01 and discard future warning messages. Do not treat subsequent quiet periods as recovery.

Sources are the [targeted journal ledger](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/journal-relevant.jsonl) and [libinput rate-limit rows](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/file-classified.json). The first two jump consumers and mirrored text copies must not be added together as physical events.

## Anomalies by boot

All dates below are 2026 in Asia/Karachi. `J X/T` means retained Xorg and Touchégg jump-warning messages. Lag includes device-processing and expired-timer warnings. Hung counts are task messages, not independent incidents. The suspend column gives entry/exit message counts; unmatched messages can reflect failed suspend, shutdown or retention boundaries.

| Boot prefix | First to last retained record | J X | J T | Lag | I2C incomplete | Hung task | Suspend in/out |
|---|---|---:|---:|---:|---:|---:|---:|
| `e5d1eaa3` | 10-03 19:23:00 to 10-04 21:49:21 | 0 | 0 | 0 | 0 | 10 | 2/1 |
| `42445c6d` | 10-05 11:36:14 to 10-08 19:25:59 | 5 | 5 | 7 | 0 | 10 | 8/8 |
| `045534ea` | 10-08 19:28:37 to 10-12 23:11:01 | 4 | 4 | 8 | 1 | 10 | 12/11 |
| `7cd2d45b` | 10-12 23:12:24 to 10-16 11:49:53 | 1 | 1 | 13 | 1 | 0 | 19/19 |
| `2743de96` | 10-16 11:51:17 to 10-17 12:29:54 | 0 | 0 | 0 | 0 | 0 | 2/2 |
| `0aa26228` | 10-17 19:02:15 to 10-22 13:45:02 | 2 | 2 | 10 | 0 | 0 | 13/13 |
| `a0307e39` | 10-22 13:45:37 to 10-24 10:03:08 | 0 | 0 | 7 | 0 | 0 | 3/3 |
| `a4a12e17` | 10-24 10:04:18 to 10-27 19:43:01 | 1 | 1 | 5 | 0 | 10 | 5/4 |
| `a282930e` | 10-27 19:55:50 to 10-28 03:01:00 | 0 | 0 | 0 | 0 | 10 | 1/0 |
| `d5b72b4c` | 10-28 08:00:03 to 10-30 13:27:01 | 2 | 2 | 5 | 0 | 10 | 7/7 |
| `d13a8a6a` | 10-30 13:28:45 to 11-03 05:37:01 | 0 | 0 | 0 | 0 | 10 | 10/9 |
| `a6e678aa` | 11-03 13:00:46 to 11-05 16:42:01 | 2 | 2 | 3 | 0 | 0 | 8/8 |
| Total | October 3 to November 5 | 17 | 17 | 58 | 2 | 70 | 90/85 |

Full boot IDs, per-boot raw counts and exact retained endpoints are in the [boot anomaly ledger](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/anomalies-by-boot.json). Warning ranges are in [anomaly ranges](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/anomaly-ranges.json).

## Exact touch-jump warning events

The first table timestamp is Xorg's wall-clock receipt timestamp, with six decimal places. The companion column is Touchégg's time on the same date. A few milliseconds between consumers is normal scheduling variation. It does not establish which client caused anything.

| Xorg date and time | Boot | Touchégg time | Since previous logged resume |
|---|---|---|---|
| 10-05 11:36:49.238369 | `42445c6d` | 11:36:49.237592 | none in this boot |
| 10-05 11:37:01.325848 | `42445c6d` | 11:37:01.325609 | none in this boot |
| 10-05 11:37:01.340209 | `42445c6d` | 11:37:01.340145 | none in this boot |
| 10-05 11:37:01.354243 | `42445c6d` | 11:37:01.354179 | none in this boot |
| 10-05 11:37:01.707332 | `42445c6d` | 11:37:01.706902 | none in this boot |
| 10-09 17:13:15.303922 | `045534ea` | 17:13:15.303361 | 12367.638 s |
| 10-10 19:37:05.504167 | `045534ea` | 19:37:05.505052 | 12248.867 s |
| 10-10 19:52:26.676399 | `045534ea` | 19:52:26.676903 | 13170.039 s |
| 10-10 19:52:27.081148 | `045534ea` | 19:52:27.080800 | 13170.444 s |
| 10-15 04:35:09.651622 | `7cd2d45b` | 04:35:09.651323 | 23610.008 s |
| 10-18 00:45:48.556020 | `0aa26228` | 00:45:48.556675 | 2952.020 s |
| 10-20 12:35:25.278019 | `0aa26228` | 12:35:25.277657 | 9865.671 s |
| 10-27 09:27:56.506312 | `a4a12e17` | 09:27:56.506742 | 1756.769 s |
| 10-28 10:09:28.790741 | `d5b72b4c` | 10:09:28.802222 | 302.143 s |
| 10-29 16:38:13.093653 | `d5b72b4c` | 16:38:13.094177 | 9382.425 s |
| 11-03 16:05:34.175211 | `a6e678aa` | 16:05:34.174725 | none in this boot |
| 11-05 13:39:44.967692 | `a6e678aa` | 13:39:44.966921 | 28.323 s |

The first warning is actually Touchégg at **October 5 11:36:49.237592**, followed by Xorg 0.777 ms later. The last is Xorg at **November 5 13:39:44.967692**. There are 13 bursts: one warning at October 5 11:36:49, four within 0.382 seconds at 11:37:01, two within 0.405 seconds at October 10 19:52:26, and ten other single-warning bursts. The seven boots with warnings include cleanly logged boot startup and long-running sessions. October 5's first warning is 34.304 seconds after that boot's first retained record. [Episode ledger](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/jump-episodes.json), [burst ledger](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/jump-bursts.json).

The paired consumers support a problem in the common event stream or common libinput interpretation, rather than a pointer warp generated only after Xorg has processed input. They do not distinguish faulty raw coordinates from a shared libinput state/heuristic error. The upstream 1.20 documentation says the warning is rate-limited and often concerns firmware or kernel coordinates. That is a lead, not a diagnosis for this laptop. [libinput 1.20 jumping-cursor documentation](https://wayland.freedesktop.org/libinput/doc/1.20.0/touchpad-jumping-cursors.html).

The inspected upstream 1.20 source uses the previous touch history point, normalizes movement to 12 ms, skips zero or greater-than-30 ms intervals, and detects either more than 20 mm normalized movement or an increase greater than 7 mm. It resets that touch's motion history when detected. This is materially different from the installed custom recorder's 40 mm / 20 ms and 2500 mm/s thresholds. The upstream code is a reference baseline, not a verified source reconstruction of Ubuntu's patched binary. [Saved upstream source, `tp_detect_jumps`, lines 1487 onward](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/libinput-1.20.0-evdev-mt-touchpad.c), [upstream tag](https://gitlab.freedesktop.org/libinput/libinput/-/blob/1.20.0/src/evdev-mt-touchpad.c#L1487).

## Kernel transport faults and manual actions

Two actual kernel errors name this touchpad:

| Time logged | Boot | Message | Context |
|---|---|---|---|
| October 11 16:47:03.501987 | `045534ea` | `i2c_hid_get_input: incomplete report (31/65280)` | Resume log flush, alongside ACPI interrupt unblock, i915 firmware restart, and an audio suspend UBSAN warning |
| October 15 13:08:18.590089 | `7cd2d45b` | Same incomplete-report message | Resume log flush, before `PM: suspend exit` at 13:08:18.678652 |

These are kernel-level input validation errors, below libinput and Xorg. Upstream Linux v6.17 emits this message when the report's declared length is invalid relative to the receive size and returns without forwarding it into HID input processing. The numbers describe a 31-byte receive size and a declared 65,280-byte report, not a cursor distance or 65,280 dropped events. The driver source also has negative receive-error paths that return without this particular diagnostic, so an absence of this warning cannot exclude every transport failure. The exact Pop kernel patchset was not reconstructed. [Linux v6.17 `i2c_hid_get_input`](https://github.com/torvalds/linux/blob/v6.17/drivers/hid/i2c-hid/i2c-hid-core.c#L490), [saved source](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/linux-v6.17-i2c-hid-core.c), [October 11 context](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/kernel-context-2026-10-11T164702.txt), [October 15 context](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/kernel-context-2026-10-15T130817.txt).

Neither error is within 60 seconds of a retained jump warning. They prove transport-level anomalies existed on those dates; they do not link the November 5 symptom to I2C. Kernel messages around suspend may be buffered until resume. Their journal wall times record receipt and cannot precisely date each instruction during sleep.

There are **eight recorder `read_failed` / `ENODEV` messages**, two nodes for each of four device rebindings. Authentication logs establish all four as manual actions:

| Manual rebind | Touchpad and sibling read errors | Meaning |
|---|---|---|
| October 14 18:29:27 | .773292 and .798215 | `sudo COMMAND=/usr/local/sbin/reset-touchpad-driver` |
| October 22 08:51:33 | .940364 and .960240 | Same authorized manual helper |
| October 23 16:10:09 | .531683 and .559623 | Same authorized manual helper |
| November 5 16:30:38 | .267543 and .310546 | Parent's manual rebind, explicitly excluded from spontaneous failures |

The parent also performed a soft X11 reset before that November 5 rebind. Its exact subsecond time is not established by this log set; a soft reset is not a kernel disconnect. The raw trace crossing the October 22 rebind changes identity from `.0001|input13` to `.0011|input56`; this is a new device identity, not an enormous finger jump. November 5 changes to `.0016|input77`. [Manual-action auth extracts](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/manual-actions-auth.json), [trace identities](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/trace-summary.json).

Earlier experimental automation is also present. October 10 has 77 starts of an idle-reset unit from 18:54:19 to 19:34:09 and 11 starts of a periodic-reset unit from 19:34:40 to 19:39:25. A jump-triggered recovery watcher started and stopped three times. These are interventions, not spontaneous device failures; unit start messages alone do not prove a reset executed. Later warnings show that the historical automation did not eliminate logged jumps. [Reset history with unit names](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/reset-history.json).

## Processing lag, resume, graphics and resource stalls

There are **58 libinput scheduling warnings**, 29 from each client: 54 device-processing warnings plus four late hold timers. Counts by device are below. Hold-timer event nodes resolve to the ELAN touchpad in the relevant boots.

| Device or timer | Messages | Reported delay, ms | Earliest | Latest |
|---|---:|---:|---|---|
| ELAN touchpad hold timer | 4 | 34 to 98 | 10-07 18:21:44 | 10-27 19:38:00 |
| ELAN07AC:00 04F3:31EC Touchpad | 15 | 21 to 422 | 10-09 16:53:18 | 10-29 15:32:22 |
| Lid Switch | 11 | 436 to 2756 | 10-06 11:22:19 | 11-05 13:39:16 |
| Power Button | 21 | 105 to 2274 | 10-05 21:04:55 | 11-05 13:39:16 |
| Video Bus | 1 | 47 to 47 | 10-08 19:29:09 | 10-08 19:29:09 |
| YICHIP 2.4G Receiver Mouse | 6 | 21 to 81 | 10-15 13:06:54 | 11-04 19:40:11 |

The 15 touchpad-processing messages are mostly Xorg, 14 versus one Touchégg. They are distinct from the 17 jump-warning pairs. All 11 lid-switch and 21 power-button lag messages are within five seconds on either side of a resume message; two of six receiver-mouse lag messages are also in that range. No named touchpad lag message is in that range. Receipt order matters: some lid lag messages precede the kernel's flushed `PM: suspend exit` by milliseconds. The directional `within5s_after_resume` field in the by-device ledger therefore undercounts resume associations; the absolute-window comparison above is the appropriate one. [Lag events with exact delays](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/lag-ledger.json), [device totals](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/lag-by-device.json).

November 5 has a specific sequence:

1. **13:39:16.616822**, Touchégg reports lid-switch lag of 596 ms and power-button lag of 281 ms.
2. **13:39:16.645138**, kernel logs `PM: suspend exit`.
3. **13:39:44.966921**, Touchégg reports a touch jump; Xorg follows at **13:39:44.967692**, **28.323 seconds** after the resume record.

This is temporal association, not proof of causation. Of the other post-resume jump events, the closest is October 28 at 302.143 seconds, and the others range from roughly 29 minutes to 6.56 hours. Five October 5 warnings and November 3's warning have no preceding suspend exit in the same retained boot. November 3's jump occurred about 3 hours 5 minutes after boot. The warnings are not confined to the immediate resume period. No other jump event has any processing-lag warning within 60 seconds. [Correlated episode ledger](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/jump-episodes.json).

The wider audit found these other fault families:

| Family | Count and dates | Relationship to retained touch jumps |
|---|---|---|
| Hung tasks over 122 seconds | 70 task-warning messages on seven boots, October 4 to November 2; seven date clusters, sometimes a second batch at 245 seconds | None within 60 seconds of a jump; no raw capture overlaps these diagnostic times |
| ACPI waits in hung-task stacks | `thermald`, `upowerd`, `kec_query` / `acpi_ec_event_processor` and deferred workers wait on ACPI semaphores/mutexes | Firmware/ACPI trouble is real, but no stack identifies the touchpad read path as the blocker |
| ACPI maximum reentrancy | 101 errors on October 8 from 17:22:38.854587 to 19:25:59.180426, boot `42445c6d` | None within 60 seconds of a jump |
| Suspend freeze failures | Two 20-second failures, October 5 21:05:44.292456 and October 15 17:22:27.049761 | None within 60 seconds of a jump |
| GNOME GC warnings in syslog | 55,079 direct warning lines in two October 22 bursts: 15,001 at 10:11:38 to 10:11:41; 40,078 at 11:50:41 to 11:50:42 | Neither overlaps raw windows or jump warnings; heavy desktop error output could cause stalls, but historic CPU/latency measurements are absent |
| i915 selective-fetch calculation | 11 `Selective fetch area calculation failed in pipe A` messages, one at each retained complete kernel startup | First October 5 warning is 34 seconds after one, but the same boot warning occurs on boots with no jumps; not evidence of a runtime GPU hang |
| GPU hang/reset signature | No `GPU HANG`, GPU reset/wedge or flip-timeout matching the audited patterns | Negative evidence is limited by retention and rate suppression; general desktop errors do exist |
| Audio faults around suspend | Three sound-core UBSAN warnings; 569 `sof_pcm_prepare` failures in a November 1 15:24:22 to 15:24:46 burst | Not the touchpad driver; none within 60 seconds of a jump |

The desktop diagnostics also include monitor-layout assertions, Clutter child-removal assertions and promise rejections. These demonstrate desktop faults; they do not establish wrong touchpad coordinates. Many messages emitted through `gnome-shell` belong to launched applications, so application websocket or media-decoder errors were not counted as GNOME input faults. No retained Touchégg crash/failure signature or additional out-of-range coordinate diagnostic was found in the audited sources. The existing jump and timing warnings remain the direct input evidence. [Kernel class counts](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/kernel-classified-summary.json), [kernel warning scan](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/kernel-warning-ledger.jsonl), [hung-task stack example](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/kernel-context-2026-11-02T231436.txt), [GC bursts](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/graphics-gc-bursts.json), [desktop signatures](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/desktop-diagnostics-summary.json), [strict text classification](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/file-classified.json).

## Reconstruction of all raw recordings

Each filename is `/var/lib/touchpad-watch/touchpad-manual-<suffix>.json`. Suffixes below identify every file. Their SHA-256 hashes and complete source paths are in the [per-file ledger](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/trace-summary.json). These are manual markers, not automatically verified faulty intervals.

| Filename suffix | Save/mark wall time, approximate | Boot | Initial events | Events / SYN frames | First-to-last event span, s | Idle tail before mark, s | Maximum step within 20 ms, mm |
|---|---|---|---:|---:|---:|---:|---:|
| `1791984523713210060` | 10-14 18:28:43.713210 | `7cd2d45b` | 17 | 11,276/2,173 | 59.390 | 0.603 | 2.015 |
| `1791984567687314393` | 10-14 18:29:27.687315 | `7cd2d45b` | 17 | 1,583/332 | 46.113 | 13.884 | 1.579 |
| `1792641093832382261` | 10-22 08:51:33.832382 | `0aa26228` | 17 | 6,216/1,033 | 29.344 | 3.620 | 3.205 |
| `1792641144261103634` | 10-22 08:52:24.261104 | `0aa26228` | 17 | 13,037/2,294 | 58.763 | 1.207 | 2.720 |
| `1792752309929538516` | 10-23 15:45:09.929538 | `a0307e39` | 15 | 4,653/845 | 49.147 | 7.443 | 3.027 |
| `1792753790087476882` | 10-23 16:09:50.087477 | `a0307e39` | 15 | 2,172/403 | 36.892 | 8.649 | 3.284 |
| `1792753803961741678` | 10-23 16:10:03.961742 | `a0307e39` | 15 | 2,172/403 | 36.892 | 22.524 | 3.284 |
| `1792753809394955871` | 10-23 16:10:09.394956 | `a0307e39` | 15 | 2,092/386 | 29.232 | 27.956 | 3.284 |
| `1792754083528843990` | 10-23 16:14:43.528844 | `a0307e39` | 6 | 3,126/550 | 22.286 | 7.243 | 3.066 |
| `1793878141313989460` | 11-05 16:29:01.313989 | `a6e678aa` | 21 | 2,376/637 | 14.772 | 40.224 | 0.774 |
| `1793878225047033440` | 11-05 16:30:25.047033 | `a6e678aa` | 21 | 4,160/873 | 7.689 | 27.965 | 1.850 |
| `1793878238123649385` | 11-05 16:30:38.123649 | `a6e678aa` | 21 | 4,160/873 | 7.689 | 41.042 | 1.850 |
| `1793878305164820189` | 11-05 16:31:45.164820 | `a6e678aa` | 21 | 1,452/254 | 5.655 | 45.865 | 2.260 |

The first marker is October 14 18:28:43.713210 and the last is November 5 16:31:45.164820. All 13 reasons are `manual_incident`; none says `candidate_only` and none has a capacity-truncation flag. The recorded event spans sum to **403.866 seconds**, or **308.697 seconds** after unioning overlaps within boots. These span lengths include any internal idle gaps. They are not five minutes of independently confirmed faulty movement, nor a three-month raw record. Distinct `SYN_REPORT` frames total **8,795**; the 11,056 file-frame total contains duplicate windows. A frame can contain more than one contact, which gives **9,444 distinct active contact/frame observations**. [Derived coverage](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/trace-derived-details.json).

The November 5 raw event ranges are approximately **16:28:06.318 to 16:28:21.090**, **16:29:49.393 to 16:29:57.082** twice, and **16:30:53.645 to 16:30:59.300**. The 13:39:44 jump is almost three hours earlier. The two duplicate 16:29 recordings stop 28 and 41 seconds before their markers. The post-rebind file stops 45.865 seconds before its marker. These idle tails are explicit capture limitations, not evidence of device freezes.

### Slot, identity and timing rules

The analysis replays all **218 `initial_events`** to seed slot selection, X/Y, tracking ID and tool type. It then applies stateful Type-B updates and inspects only complete `SYN_REPORT` frames. It carries unchanged coordinates forward, keeps slots separate, and does not compare across a new tracking ID, removal, device identity change or lost-event marker. Synthetic seed times are never used as genuine motion samples. These rules follow the [Linux Type-B multitouch protocol](https://www.kernel.org/doc/html/v6.17/input/multi-touch-protocol.html). The original raw files remain unchanged. [Analysis program](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/analyze_traces.py), [reconstructed frames](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/trace-frames.jsonl).

There are 161 distinct nonnegative tracking-ID start events in the captured windows, plus a contact already active in initial state. Distinct tracked identities/contact IDs seen in frames total 162: 48 on boot `7cd2d45b`, 42 on `0aa26228`, 55 on `a0307e39`, and 17 on `a6e678aa`. Only slots 0 and 1 are active in these recordings. No frame has more than two active contacts. Unused seeded slots are not counted as fingers.

Four distinct kernel `ABS_MT_TOOL_TYPE=2` reports mark palms: three tracks on October 14 and one on October 23. They cover 55 distinct active contact/frame observations. Some palm events appear twice in overlapping files. A palm label is real kernel input state, but cannot establish whether the user actually used a palm or the device misclassified a finger. The custom detector ignores movement on these labeled palms. There are no captured pressure, touch-major or touch-minor updates to independently assess contact geometry. A missing tool update after startup is not itself proof of a palm classification. [Tool and contact detail](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/trace-derived-details.json).

Recorder timestamps are `CLOCK_MONOTONIC`, selected with `EVIOCSCLOCKID`. They exclude suspended time; filename timestamps are wall-clock nanoseconds at save. The table maps each event backward from its marker using that file's wall-minus-monotonic offset and confirms the boot via the journal `recording_saved` path. Journal save receipt follows the filename by **5 to 22 ms**. This is not a guaranteed bound on writer scheduling before the filename was generated. Duplicate raw windows get wall estimates differing by about 1 ms. No mapped raw window crosses a known suspend/resume. The journal's 94 observed clock-offset segments are retained for checking this assumption. A single boot-time offset would be wrong across suspend. [Clock segments](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/journal-summary.json).

### Coordinates, smaller steps and generated interactions

Axis metadata in every file gives X `0..3689` at 32 units/mm and Y `0..2410` at 31 units/mm, roughly 115.28 by 77.74 mm. All seeded and recorded MT coordinates are within those advertised ranges. Across raw event updates, X reaches 0 and 3650, Y reaches 106 and 2368. In-range movement can still be wrong.

For a continuing contact, distance is `hypot(delta_x / 32, delta_y / 31)`. Deduplicated measurements for intervals greater than zero and at most 20 ms are:

| Threshold | Contact/frame steps at or above threshold |
|---|---:|
| 0.5 mm | 3,207 |
| 1 mm | 1,408 |
| 2 mm | 63 |
| 5 mm | 0 |
| 10 mm | 0 |
| 20 mm | 0 |
| 40 mm | 0 |

The maximum is **3.284057 mm in 7.067 ms**, about **464.703 mm/s**, October 23 approximately 16:09:28.083315, slot 0, tracking ID 13652, from X/Y **1005/971** to **1050/879**. It appears in three overlapping files and counts once. The fastest observed valid interval up to 30 ms gives 5.576 mm normalized to 12 ms, below the upstream 7 mm change threshold even if the preceding displacement were zero. This geometric comparison is not a libinput replay: libinput has its own history, touch lifecycle, quirks and filtering.

No examined continuing-contact pair has a nonpositive frame delta or a gap over 100 ms. A targeted small back-and-forth check found zero consecutive steps of at least 1 mm each within 20 ms, cosine below -0.8 and net return within 0.5 mm. These arbitrary descriptive thresholds are explicitly not a validated detector. Smooth but wrong gain, coordinate drift, false contact transitions, palm suppression and unintended taps can all escape them. The 1,408 steps above 1 mm are **not 1,408 errors**. [Top steps](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/trace-top-steps.json), [full frame ledger](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/trace-frames.jsonl), [aggregate](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/trace-aggregate.json).

Every retained event is from the `touchpad` source; there are **zero emitted sibling `mouse` events** in these windows, despite the recorder opening both nodes. There are zero `EV_REL` mouse movements, zero `BTN_LEFT/RIGHT/MIDDLE` physical button updates and zero `SYN_DROPPED` events. The captured key-type events are touch/contact-count indicators such as `BTN_TOUCH`, `BTN_TOOL_FINGER` and `BTN_TOOL_DOUBLETAP`. Tap-to-click and tap-drag can synthesize desktop button events from contacts without a raw `BTN_LEFT` event. Thus the physical-button count says nothing conclusive about clicks seen by applications. [Raw event-type counts](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/trace-aggregate.json), [button ledger](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/trace-buttons.jsonl).

The raw stream also contains **8,791 distinct `MSC_TIMESTAMP` events**, 11,050 counting overlapping copies. For 8,502 adjacent event frames with an active contact on both sides and host interval at most 30 ms, device timestamp increments are 7,000 microseconds in 8,493 pairs and 6,900 in nine. None is nonpositive. Corresponding evdev intervals range from 5.808 to 27.788 ms. This shows stable reported scan-time increments alongside some delivery-time variation; it does not prove that every physical scan reached evdev. Inactive intervals and contact restarts must not be treated as lost packets. [Hardware timestamp analysis](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/trace-hardware-timestamps.json), [analysis source](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/analyze_hardware_timestamps.py).

The recorder does not record XInput2 output, XTEST or pointer warps, processed libinput events, Touchégg action execution, the user's finger intent, power-supply state or HID report payloads. It observes the evdev output of the kernel, not electrical I2C traffic. No `SYN_DROPPED` in its own stream can establish that another client's evdev queue did not overflow. The existing code clears state on a drop but does not reconstruct the full state via evdev ioctls, so a future dropped-event trace would need that limitation called out. [Recorder source](../../scripts/touchpad-watch.py), [Linux input event semantics](https://docs.kernel.org/input/event-codes.html).

All 13 custom replays ran successfully and emitted `replay_complete`, with zero `touch_jump`, `events_lost` or `recovery_requested` decisions. Some emit expected `device_changed` decisions. **`replay_complete` is an end-of-file message, not an assertion that movement was normal.** The detector requires at least 40 mm in no more than 20 ms, at least 2500 mm/s, repeated jumps for a candidate save, ignores palms, and suppresses some intervals around identity changes and long gaps. The current traces do not validate that threshold against a real fault. Per-file replay outputs are beside the summary. No virtual input replay into the desktop was run.

## Gestures and the boundary still missing

Touchégg runs `/usr/bin/touchegg --daemon` with input access. Its installed default configuration maps two-finger pinches to key combinations and three-finger swipes to Pop Shell focus actions. The recorder saw up to two contacts, so pinch interpretation remains a possible interaction path; the retained raw windows do not show three simultaneously active contacts. Configuration shows what can execute, not what did execute at a particular time. There is no retained action-by-action gesture log. [Unit](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/gestures-unit.txt), [default configuration](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/gestures-touchegg.xml), [config path inventory](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/gestures-config-paths.txt).

The evidence supports three different statements with different strength:

1. **Established below user space:** the kernel rejected two invalid I2C-HID report lengths. Their contribution to the user's touch-only symptom remains unproved.
2. **Observed at a shared input-processing boundary:** two independent libinput consumers flag the same coordinate jumps. Device/firmware/kernel output is a strong candidate, but a common libinput tracking/history issue cannot be excluded without raw data at those times.
3. **Unresolved for clicks, drags and overall erratic interaction:** there are no synchronized generated events or labeled finger trajectories. Legitimate contacts transformed into unintended output by tapping, acceleration, gestures, an application or pointer injection remain distinguishable hypotheses, not proven causes.

A complete proof requires a symptom timestamp, continuous raw slots/IDs, X11 motion and button output with source IDs, and either a known stationary finger or an independently observed physical trajectory. To split firmware/I2C from HID decoding inside the kernel, capture matching HID payloads and evdev output, then compare the coordinate values across that boundary. The current JSON format lacks the HID descriptor and original report payloads. To name an injecting X11 client rather than merely see generated motion, further X protocol/client attribution may be required. The evidence does not justify another reset, settings trial or package change.

## Next reproducible diagnostic

Keep the existing settings and recorder. Capture the missing X11 pointer output during the next real occurrence. The following reads pointer events for 90 seconds and records clock/device metadata. It opens no keyboard recording and does not reset or grab a device:

```bash
diag_dir="$HOME/.local/state/touchpad-investigation/2026-11-05/logs"
date --iso-8601=ns > "$diag_dir/next-clock.txt"
python3 -c 'import time; print("realtime", time.time_ns(), "monotonic", time.monotonic_ns())' >> "$diag_dir/next-clock.txt"
xinput list --short > "$diag_dir/next-xinput-devices.txt"
xinput list-props 'ELAN07AC:00 04F3:31EC Touchpad' > "$diag_dir/next-xinput-props.txt"
timeout --signal=INT 90s stdbuf -oL xinput test-xi2 --root 'Virtual core pointer' > "$diag_dir/next-xi2-pointer.txt" 2>&1
```

During that capture, reproduce one short action at a time: hold a single fingertip still without clicking, draw a slow straight stroke, then separately reproduce the failing interaction. At the symptom, leave the finger where it is if practical and run in another terminal:

```bash
/home/elhaam/dotfiles/scripts/fixtouchpad --mark
```

Record the wall time and a precise label, for example `single finger held still, pointer moved right` or `one finger moving, unexpected drag began`. Mark immediately; later marks only retain the preceding minute. This is a diagnostic observation, not a request to change behavior permanently. A one-second unattended XI2 probe was run and accepted the pointer device with no stderr; it timed out normally, exit 124. It did **not** reproduce the symptom, so the proposed capture is not yet a verified reproducer. [Probe](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/xi2-probe.txt), [installed xinput manual](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/xinput-installed-man.txt).

Review the new raw mark and XI2 capture together. A contact-coordinate discontinuity during a physically still finger would establish bad input before desktop event generation. A generated button with no raw physical button must be interpreted against tap/contact state. Pointer output from another source, or motion without a corresponding pad contact delta, moves the investigation toward generated events, pointer warps or application behavior. XI2 alone may not identify the responsible X client. If the pointer remains stable while only the drawn display stutters, resource/rendering stalls become more relevant. Each outcome names the next boundary to inspect; none requires a settings guess.

If administrative **read** access becomes available, `libinput record --with-hidraw` restricted to the two ELAN event nodes can add synchronized HID payloads and a standard device description. The installed 1.20 manual confirms `--with-hidraw` and experimental `--with-libinput`. This audit did not run them because `sudo -n` lacks permission. `--with-libinput` creates a separate context with defaults, cannot copy Xorg's settings, and may interleave its output differently. It is not a trace of the running Xorg context; a separate debug-events context would need the observed configuration explicitly matched. Do not use `--all`, `--grab` or device replay on the running desktop for this step. [Installed record manual](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/libinput-record-installed-man.txt), [upstream recording guidance](https://wayland.freedesktop.org/libinput/doc/1.20.0/tools.html), [reporting guidance](https://wayland.freedesktop.org/libinput/doc/1.20.0/reporting-bugs.html).

## Command provenance and evidence index

Exact argument arrays, exit codes and stderr for collector probes and replay commands are in [commands.jsonl](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/commands.jsonl). The executable analysis sources provide the exact transformations and discovery patterns:

- [audit_logs.py](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/audit_logs.py) streams the journal with the explicit calendar window, inventories sources, scans gzip/plain rotations and captures static metadata. It never saves the full private journal.
- [extra_audit.py](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/extra_audit.py) scans every retained kernel record explicitly across boots and checks desktop diagnostics in every syslog rotation.
- [summarize_logs.py](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/summarize_logs.py) pairs consumers, forms bursts, calculates correlations, queries sysstat headers/samples and checks stack package history.
- [analyze_traces.py](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/analyze_traces.py) reconstructs seeded slots, tracking IDs, contact motion, button codes and deduplicates raw events.
- [derive_details.py](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/derive_details.py) checks auxiliary statistics, absolute resume correlations, trace hashes and report links.
- [trace-derived-details.json](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/trace-derived-details.json) records union coverage, distinct reports, palms and 30 ms geometric comparisons.
- [source-inventory.json](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/source-inventory.json), [file-coverage.json](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/file-coverage.json) and [journal-summary.json](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/journal-summary.json) inventory coverage, per-day journal counts and clock segments.
- [provenance.md](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/provenance.md) records interactive commands and limitations; [evidence-manifest.json](/home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/evidence-manifest.json) hashes generated evidence.

Core collection and analysis invocations, run from `/home/elhaam/dotfiles`, were:

```bash
python3 /home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/audit_logs.py
python3 /home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/analyze_traces.py
python3 /home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/summarize_logs.py
python3 /home/elhaam/.local/state/touchpad-investigation/2026-11-05/logs/extra_audit.py
journalctl --verify --no-pager
```

The primary journal query was `journalctl --since '2026-08-05 00:00:00' --until '2026-11-05 16:42:16' --no-pager -o json --all` with `TZ=Asia/Karachi`. The summary's fractional snapshot is the process start time; the actual journal filter ends at the whole second shown. The latest retained record returned is 16:42:01.745654. Supporting file scans continued briefly after this fixed journal snapshot. No warning counts from later probes were folded into the frozen dataset.

A first discovery query used `journalctl -k`, which defaults to the current boot. Its `kernel-subsystems.txt` is labeled a current-boot discovery aid only. The reported all-boot kernel results use `_TRANSPORT=kernel` in `extra_audit.py` and the timestamp-scoped context queries. One first execution of `summarize_logs.py` failed on a nullable resume distance; this was corrected and the complete program rerun. No event data was altered. Source download attempts returning 404 or failing in web fetch are noted in provenance; the libinput raw source was successfully fetched directly from its upstream tag. Analysis scripts are local audit tools, not modifications to the live recorder.
