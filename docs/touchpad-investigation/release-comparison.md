# Touchpad driver release audit

Research performed on 2026-11-05. This is preparation for the parent investigation. No host driver, package, firmware, service, input setting or accessibility setting was changed.

## Decision

**Do not install a driver update as the touchpad fix yet.** I found no upstream change with a demonstrated match to this machine's touch-on-contact erratic movement. The newest packaged libinput available from the configured repositories is a security backport with no change to touch processing. The latest upstream library is suitable for an isolated comparison, which is now built and ready.

The missing evidence is a bad-contact recording with raw slot/tracking-ID transitions and corresponding processed motion. The warning alone cannot identify whether the fault is in hardware, firmware, HID processing, libinput state, or a higher layer. A similar symptom on two machines does not identify a shared cause until the second machine's hardware and stack are known.

## Evidence and scope

The supplied baseline is HP EliteBook 840 G10, `ELAN07AC:00 04F3:31EC`, firmware `0x0008`, Pop!_OS 22.04, GNOME X11, kernel `6.17.9-76061709-generic`, libinput `1.20.0-1ubuntu0.3`, X.Org input bridge `1.2.1-1`, and Touchégg. The parent restored speed `0.73529411764705888` and tap dragging `true` after an unsuccessful trial. This audit did not repeat that trial.

Read-only local checks confirmed the installed versions. The HID modalias is `hid:b0018g0004v000004F3p000031EC`. Group `0004` is Win8 multitouch. The device's current event node is `/dev/input/event5`; this number can change. fwupd reports IC type `11`, module `001D`, driver `HID`, protocol `tw.com.emc.elantp`, firmware `0x0008`, bootloader `0x0001`, and device ID `57f66c36438708fd2cccd927a890183db7c2ed06`.

All downloads, source clones, package extraction and build tools are under:

`/home/elhaam/.cache/touchpad-investigation/release-audit.oY4Hcwux`

Local evidence there includes `apt-policy.txt`, `apt-simulation.txt`, `installed-rdepends.txt`, `package-SHA256SUMS`, `fwupd-devices.json`, `kernel-releases.json`, upstream commit API responses, `libinput-tags.txt`, `libinput-relevant-log.txt`, `candidate-patches.txt`, and the extracted distro sources. `dpkg -V` reported no altered packaged files for the three installed libinput packages or the X.Org bridge.

The upstream GitLab web interface returned an anti-bot denial for some pages. Git transport worked, so release and patch claims below come from cloned upstream tags, commit messages and diffs. Release dates were read from tags or release metadata, rather than inferred from the clock. The kernel audit examined upstream tagged source and local distro changelog, not the complete Pop!_OS kernel patch series. That distinction matters when asserting that a backport is present in the running distro build.

## Release and package comparison

| Component | Installed | Latest stable verified upstream | Newest relevant package from this host's cached APT lists | Decision for this fault |
| --- | --- | --- | --- | --- |
| libinput library and tools | `1.20.0-1ubuntu0.3` | `1.32.0`, tagged 2026-09-17, commit `5cf833b572f5a33663888da321dce0ba1abd82a2` | `1.20.0-1ubuntu0.4`, Jammy security/updates | `.4` fixes a security issue, not contact motion. Use the isolated `1.32.0` tools to establish a difference first. [Upstream tag](https://gitlab.freedesktop.org/libinput/libinput/-/tags/1.32.0), [Ubuntu source](https://packages.ubuntu.com/source/jammy-updates/libinput), [Ubuntu notice](https://ubuntu.com/security/notices/USN-8602-1). |
| X.Org `xf86-input-libinput` | `1.2.1-1` | `1.5.0`, tagged 2024-10-15, commit `c712930ef4b544a5036fe2f55fd2ade9efb8ea78` | `1.2.1-1`, already installed | No ELAN contact-lifecycle or jump fix found in the intervening changes. [Upstream tags](https://gitlab.freedesktop.org/xorg/driver/xf86-input-libinput/-/tags), [release archive](https://xorg.freedesktop.org/archive/individual/driver/). |
| Linux HID/I2C/multitouch | Pop build based on upstream `6.17.9` | Kernel.org reports stable `7.3.1`, 2026-10-30; `7.4-rc1` is a development release | Pop `7.2.15-76070215.202611011338~1793722201~22.04~d7c4015`, priority 1001 | No established reason to install it for this symptom. HID modules belong to the kernel build and have no independent driver-version upgrade here. [Kernel release metadata](https://www.kernel.org/releases.json). |
| Touchpad firmware | `0x0008`, module `001D` | No compatible newer firmware established | Parent's targeted `fwupdmgr get-updates` returned `Devices: []` using existing metadata | No flash recommendation. Empty cached results do not establish that HP has never released newer firmware. [ELAN plugin documentation](https://fwupd.github.io/libfwupdplugin/elantp-README.html). |

Kernel.org also lists LTS `6.18.60` and `6.12.115`, both dated 2026-10-30. These are available release facts, not recommendations to switch kernels. The configured Pop kernel candidate is distinct from upstream's newest stable kernel.

APT metadata was not refreshed. Relevant cached InRelease timestamps were 2026-11-04 for Pop release and 2026-11-05 for Jammy security/updates. The system sources include Jammy, security, updates and backports, plus Pop release/proprietary and several unrelated third-party repositories. None supplies a newer libinput candidate. The toolchain and PipeWire PPAs are not libinput upgrade sources in the inspected policy.

## Exact distro changes

The installed libinput changelog and the downloaded `1.20.0-1ubuntu0.4` source identify the installed `.3` patch set as:

| Patch | Upstream identity | Scope |
| --- | --- | --- |
| `0001-evdev-strip-the-device-name-of-format-directives.patch` | Backport `6d11367f31e37c4bb3902e91ffebd5418a957f67`; mainline counterpart `a423d7d3269dc32a87384f79e29bb5ac021c83d1` | CVE-2022-1215, device-name logging. |
| `0001-quirks-add-quirks-for-Dell-Precision5680-Touchpad.patch` | `29a49e968e67eb7bf6d63c9f93b06ee983772018`, [issue 849](https://gitlab.freedesktop.org/libinput/libinput/-/issues/849), Ubuntu LP 2002609 | Disables pressure axes for Goodix `27C6:0F60`. Does not match this ELAN device. |
| `0001-quirks-Dell-Mayabay-Pressure-Pad.patch` | `74415b13fb72c457e5439c974f59e1b0d08a27ed`, Ubuntu LP 2023623 | Same pressure workaround for Synaptics `06CB:CFA0`. Does not match this device. |

The `.4` update adds only `CVE-2026-50292-pre1.patch` and `CVE-2026-50292.patch`. These add cleanup helpers and sanitize the device `phys` string in `libinput-device-group`. The latter names backport `f5ac1e51fffffdc19aace7708175c10840a8b801` from mainline `76f0d8a7f57e2868882864b4611281f12f704b55`. They do not modify touchpad contact processing, tapping, motion filtering or ELAN quirks. Ubuntu published the security notice on 2026-07-23. [Source package and patches](https://packages.ubuntu.com/source/jammy-updates/libinput), [security notice](https://ubuntu.com/security/notices/USN-8602-1).

The extracted X.Org `1.2.1-1` source has a placeholder-only quilt series. Packaging differences include CI and generated/build files, with no listed runtime patch to the bridge. The installed dependency is `xorg-input-abi-24` plus `libinput10 >= 1.19.1`.

The installed Pop kernel changelog explicitly says `Mainline build at commit: v6.17.9` and is dated 2025-12-02. The package suffix `b24b425` did not resolve as a source commit in the probed public `pop-os/linux` repository. Consequently, upstream `v6.17.9` is the comparison baseline here; the parent source investigation should confirm any assertion about Pop-specific changes against its exact kernel source.

## Specific libinput fixes and applicability

Stable containment below was checked with `git tag --contains`, excluding `.9xx` prereleases and checking the known cherry-picked counterpart where present. A patch that sounds similar is not evidence that this user's failing sequence matches it.

| Commit and first stable | What it fixes or changes | Match to this machine |
| --- | --- | --- |
| [`d0e6d43a78ee81f077dbd0dda98827440a3b5fc2`](https://gitlab.freedesktop.org/libinput/libinput/-/commit/d0e6d43a78ee81f077dbd0dda98827440a3b5fc2), **1.32.0**. [Issue 1319](https://gitlab.freedesktop.org/libinput/libinput/-/issues/1319), [MR 1505](https://gitlab.freedesktop.org/libinput/libinput/-/merge_requests/1505). | Resyncs `ABS_MT_TOOL_TYPE` after reopening a device. A palm released while the device is disabled could leave a slot marked as palm, suppressing all subsequent touches in it. The reported result is one finger doing nothing and two fingers moving the pointer. | Low current confidence. Requires that lifecycle and stale-palm signature. Erratic motion and a discarded-jump warning do not establish it. Worth testing only if the trace shows persistent missing output after resume/disable with a palm-marked slot. |
| [`d773056d2eda33c2da0ce2a9ce6d4278c0785da4`](https://gitlab.freedesktop.org/libinput/libinput/-/commit/d773056d2eda33c2da0ce2a9ce6d4278c0785da4), **1.27.1**. [Issue 1050](https://gitlab.freedesktop.org/libinput/libinput/-/issues/1050), [MR 1081](https://gitlab.freedesktop.org/libinput/libinput/-/merge_requests/1081). | Removes an assertion when an already-ended slot receives a pending tracking-ID `-1` immediately after reopening. | Low. Fixes an assertion/crash race; no matching crash or reopen-bound trace is established. It does not repair arbitrary coordinate jumps. |
| [`76f88deb249150ccdcb3be9b3d6b851a030d58bc`](https://gitlab.freedesktop.org/libinput/libinput/-/commit/76f88deb249150ccdcb3be9b3d6b851a030d58bc), **1.29.0**. [MR 1224](https://gitlab.freedesktop.org/libinput/libinput/-/merge_requests/1224). | Removes an old workaround that prevented reducing slot count to zero and requires a sufficiently recent libevdev. | Low. This host already has libevdev `1.12.1`. The change removes a workaround; its title does not establish a fix for this ELAN sequence. |
| [`15609213a64461e5351ea13556a308a8eb65acc9`](https://gitlab.freedesktop.org/libinput/libinput/-/commit/15609213a64461e5351ea13556a308a8eb65acc9), **1.26.0**. [Issue 981](https://gitlab.freedesktop.org/libinput/libinput/-/issues/981), [MR 982](https://gitlab.freedesktop.org/libinput/libinput/-/merge_requests/982). | Prevents tiny scroll events before a two-finger tap on touchpads without gesture support. | Low. Different event type and capability precondition. Does not explain one-finger contact motion. |
| [`92233df57b07c4bbc95ec4f5ed9ce5cc896eabce`](https://gitlab.freedesktop.org/libinput/libinput/-/commit/92233df57b07c4bbc95ec4f5ed9ce5cc896eabce), **1.21.0**. | Normalizes DPI for the touchpad flat acceleration profile, fixing unusably slow motion on low-resolution touchpads. | Low. Requires flat acceleration and a speed/normalization symptom. Does not correct slot identity or a sudden raw coordinate discontinuity. |
| [`2bb9c66cd7bd447261889f4939d3254892ec78bf`](https://gitlab.freedesktop.org/libinput/libinput/-/commit/2bb9c66cd7bd447261889f4939d3254892ec78bf), **1.30.0**. [MR 1249](https://gitlab.freedesktop.org/libinput/libinput/-/merge_requests/1249). | Lets plugins disable jump detection. | **Not a fix.** Disabling the detector can pass bad movement through. No such plugin was enabled, built or installed in this audit. |
| [`c73fc78407aa4eddd1dcd2f896d036ee68cb2c69`](https://gitlab.freedesktop.org/libinput/libinput/-/commit/c73fc78407aa4eddd1dcd2f896d036ee68cb2c69), **1.28.0**. [MR 1042](https://gitlab.freedesktop.org/libinput/libinput/-/merge_requests/1042). | Cancels ongoing gestures before sending a tap button. Its own commit message describes it as effectively a no-op for the existing state machines. | No established match. Do not present this as a tap-drag fix for the report. |
| [`04a35384e6bd6a8d6d1f6c4c3bad7c79ae7ad163`](https://gitlab.freedesktop.org/libinput/libinput/-/commit/04a35384e6bd6a8d6d1f6c4c3bad7c79ae7ad163), **1.32.0** on mainline; backport [`04abe57410d4cc1675b415ba843bb072989d9db5`](https://gitlab.freedesktop.org/libinput/libinput/-/commit/04abe57410d4cc1675b415ba843bb072989d9db5) is in **1.31.3**, released 2026-06-04. [MR 1486](https://gitlab.freedesktop.org/libinput/libinput/-/merge_requests/1486). | Rejects extreme or invalid axis metadata, including negative resolutions. | Low. Rejecting malformed devices is not a replacement resolution value for this touchpad. Need its actual axis ranges, resolutions and measured physical size. |

The core jump test still uses a 12 ms reference interval, a normalized distance above 20 mm or an increase above 7 mm, and skips a touch with no history in both `1.20.0` and `1.32.0`. Finger-count changes already reset motion history in the older implementation. A warning immediately after contact can therefore involve subsequent frames or a contact that the stack considers continuous; it is not proof that the first new contact was mishandled. [1.20 source](https://gitlab.freedesktop.org/libinput/libinput/-/blob/1.20.0/src/evdev-mt-touchpad.c), [1.32 source](https://gitlab.freedesktop.org/libinput/libinput/-/blob/1.32.0/src/evdev-mt-touchpad.c).

I found no explicit `ELAN07AC`, `31EC`, or EliteBook match in the `1.32.0` quirk database or the searched relevant history. The only change to `30-vendor-elantech.quirks` after `1.20.0` is [`57c71c567f85181dcf433476c0d3f223165e0c4c`](https://gitlab.freedesktop.org/libinput/libinput/-/commit/57c71c567f85181dcf433476c0d3f223165e0c4c), first stable `1.32.0`, for haptic `04F3:3355`. The older generic `*Elan Touchpad*`/`*Elantech Touchpad*` name rules remain. They are case-sensitive and must not be assumed to match `ELAN07AC...`. HP OmniBook pressure changes such as [`526130fe8d9545b9f38d0caf9d7c906775c48a75`](https://gitlab.freedesktop.org/libinput/libinput/-/commit/526130fe8d9545b9f38d0caf9d7c906775c48a75), first stable `1.32.0`, target a different DMI match. Copying them here would be unsupported. [ELAN quirks](https://gitlab.freedesktop.org/libinput/libinput/-/blob/1.32.0/quirks/30-vendor-elantech.quirks), [HP quirks](https://gitlab.freedesktop.org/libinput/libinput/-/blob/1.32.0/quirks/50-system-hp.quirks).

The X.Org `1.2.1..1.5.0` history adds custom acceleration configuration, tablet controls, clickfinger mapping and keyboard handling, with some startup/error-path fixes. For example, [`e87c7bfcc2b7e7148554467c6eff8ec28aabe0c2`](https://gitlab.freedesktop.org/xorg/driver/xf86-input-libinput/-/commit/e87c7bfcc2b7e7148554467c6eff8ec28aabe0c2), in `1.3.0`, corrects transforms for absolute pointers. A relative touchpad jump is not that defect. Contact tracking and jump suppression are in libinput, before this bridge. I found no relevant unreleased touchpad fix in the examined post-`1.32.0` libinput paths or post-`1.5.0` bridge history.

## Linux fixes worth checking against the trace

| Upstream commit | Release evidence | Applicability |
| --- | --- | --- |
| [`46f781e0d151844589dc2125c8cce3300546f92a`](https://git.kernel.org/linus/46f781e0d151844589dc2125c8cce3300546f92a), sticky fingers | Mainline `6.18`; backported code is absent in tagged `6.17.4` and present in `6.17.5` and `6.17.9`. | Relevant class of defect: a missing release while another finger remains. But upgrading from the upstream `6.17.9` baseline does not newly acquire this fix. Exact Pop source confirmation remains with the source investigation. |
| [`ff3f234ff1dcd6d626a989151db067a1b7f0f215`](https://git.kernel.org/linus/ff3f234ff1dcd6d626a989151db067a1b7f0f215), sticky-finger quirk for VTL. [Issue 1225](https://gitlab.freedesktop.org/libinput/libinput/-/issues/1225). | Mainline `6.19`; VTL class lacks the flag in `6.18` and has it in `6.19`. | Does not match the Win8 ELAN class. The reported device is TOPS `35CC:0104`, with stale two-finger state and false right clicks. |
| [`e8e60b6439eed340a611e9d7a5b9bcbd0ef62725`](https://git.kernel.org/linus/e8e60b6439eed340a611e9d7a5b9bcbd0ef62725), stale slots at zero contacts | Present in mainline `7.3`. The inspected stable `7.2.15` source still has the previous conditional. An October AUTOSEL proposal does not by itself establish a stable release backport. | The reported hardware is INGENIC `17EF:6161` touchscreen. Existing code already handles a zero-contact new frame for `MT_QUIRK_WIN8_PTP_BUTTONS`; this device enumerates as Win8. Low confidence of relevance unless HID data establishes a different failing path. |
| [`8813b0612275cc61fe9e6603d0ee019247ade6be`](https://git.kernel.org/linus/8813b0612275cc61fe9e6603d0ee019247ade6be), bounds-safe active-slot bitmap | Present in mainline `7.2` and stable `7.2.15`. | Fixes memory corruption for large slot counts from the sticky-finger bitmap. Need the advertised contact maximum and a matching failure. No panic, large-slot corruption, or such trace is established here. |

Release containment was checked in [stable tagged source](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/hid/hid-multitouch.c?h=v6.17.9) and [mainline 7.3 source](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/hid/hid-multitouch.c?h=v7.3), with downloaded copies retained. The inspected I2C-HID core/ACPI history after October 2025 adds reset and input-size quirks for other devices, bounds checks and ACPI changes. No `31EC`/`ELAN07AC` contact-motion fix was identified. HID resolution-multiplier work concerns relative high-resolution wheels, not automatically the touchpad's absolute coordinate resolution.

## Firmware options

The cached targeted update result is insufficient to certify `0x0008` as the newest firmware. No HP/LVFS release with a verified `ICTYPE_11`, module `001D`, HID match and a corresponding contact-jump fix was established. The HP driver page was not retrievable through the research interface. This is an evidence limit, not a claim that firmware does not exist.

The fwupd plugin's `updatable` flag shows a supported flash mechanism. It does not show that a compatible newer payload is available. Its documentation requires hardware/module identity and describes a period when the touchpad is nonfunctional during programming. A failed HID flash can require model-specific I2C recovery. Consequently firmware cannot be promised to satisfy the user's no-disruption condition. Do not use a Dell payload, an ELAN fingerprint update, or a Windows input-driver package as a touchpad firmware substitute. [Plugin documentation](https://fwupd.github.io/libfwupdplugin/elantp-README.html).

Future firmware preparation would require current vendor metadata or HP's exact supported product/module package, its release notes, supported IDs, firmware version and recovery procedure. This audit did not refresh fwupd metadata, run an update, or flash anything.

## Compatibility, staging and rollback

APT simulation for only the three `.4` packages reported **3 upgrades, 0 installs, 0 removals, 549 packages not upgraded**. All three `.4` amd64 binaries and matching source archives are staged. The available `.4` dependency bounds fit the installed Jammy libraries. This is the lowest-scope packaged path, but it does not meet the requested evidence threshold for a touchpad fix.

Both the installed and built upstream libraries use SONAME `libinput.so.10`. That supports old consumers linking to a newer library, but does not guarantee unchanged input behavior or package compatibility. Installed reverse dependencies include the X.Org driver, Touchégg, Mutter, Qt GUI and Clutter. A global replacement therefore has consequences beyond this touchpad. X.Org's module also has its own input ABI; a future rebuild must use this host's ABI-24 development headers, rather than a binary from another X server release.

Foreign-suite binaries are not a narrow upgrade path. For example, Ubuntu Noble's libinput package needs glibc `>= 2.38` and `libmtdev1t64`; Resolute also requires libwacom `>= 2.18.0`. This host's installed libwacom is `2.2.0`. Pulling a newer suite to satisfy these dependencies would expand the change beyond the driver. [Noble dependencies](https://packages.ubuntu.com/noble/libinput10), [Resolute dependencies](https://packages.ubuntu.com/resolute/libinput10).

Exact `.3` rollback debs for `libinput10`, `libinput-bin` and `libinput-tools` were downloaded from Launchpad's primary archive and extracted in the cache. The rollback library compares byte-for-byte equal to the installed `/usr/lib/x86_64-linux-gnu/libinput.so.10.13.0`. Their versions were checked with `dpkg-deb -f`; hashes are recorded. Archive.ubuntu.com no longer served the probed `.3` pool URLs, so rollback must use these staged copies rather than assume the old version remains an APT candidate.

If the parent later authorizes a packaged test, simulate its exact local packages first, keep all three package versions aligned, and retain the staged rollback files. The conditional rollback command, **not run**, is:

```bash
audit_dir=/home/elhaam/.cache/touchpad-investigation/release-audit.oY4Hcwux
sudo apt-get --no-download --allow-downgrades install \
  "$audit_dir/libinput10_1.20.0-1ubuntu0.3_amd64.deb" \
  "$audit_dir/libinput-bin_1.20.0-1ubuntu0.3_amd64.deb" \
  "$audit_dir/libinput-tools_1.20.0-1ubuntu0.3_amd64.deb"
```

Existing X.Org/Touchégg processes keep their mapped library after a package replacement. A logout/login and relevant daemon restart would be needed for a consistent live comparison, interrupting the session. A userspace library change does not intrinsically require a kernel reboot. A kernel change needs a reboot and retains the separate risks of the rest of that kernel. Neither form of global test is justified by a matching fix yet. The inspected `.4` library package declares the normal `ldconfig` trigger; no service restart script was present in the inspected library/quirk package controls.

If a source fix proves necessary, prefer a minimal backport built as Jammy packages under a unique version. Preserve the distro's security patches, include only the regression fix and its necessary dependencies, verify package simulation, and reuse the rollback set. Do not overwrite `/usr` or `/usr/local` with `meson install` as an experiment.

## Isolated tools prepared successfully

The cache now contains libinput **1.32.0**, checked out at the exact tagged commit above, and these compiled tools:

```text
libinput-build/libinput
libinput-build/libinput-debug-events
libinput-build/libinput-record
libinput-build/libinput-quirks
libinput-build/libinput.so.10
```

`libinput-build/libinput --version` prints `1.32.0`. `ldd` confirms the three diagnostic tools resolve libinput to the cache build, while using the existing host `libevdev.so.2` and `libudev.so.1`. Help output and quirk-database validation succeeded. No diagnostic tool was used to grab or reset the device; only version/help/validation/linkage checks were run. These smoke checks prove the build works, not that it fixes the fault. The installed `libinput --version` remains `1.20.0`, and package versions remain unchanged.

Build prerequisites were supplied entirely within the cache: Meson `1.6.1`, Ninja `1.11.1.3`, and an extracted Jammy `libevdev-dev 1.12.1+dfsg-1` package. The host already supplies a C compiler, pkg-config and libudev development files. The build disables GUI, full tests, documentation, Lua plugins, libwacom and mtdev. This is a diagnostic build for a Win8 protocol-B touchpad, not a complete desktop replacement; the disabled tablet/protocol-A facilities do not justify deploying this artifact globally.

`meson-launch.py` in the cache sets Python's executable path explicitly because the T3 AppImage environment otherwise reports the AppImage as `sys.executable`, which broke Meson's subprocess commands. It changes only the cached build launcher. Rebuild commands:

```bash
audit_dir=/home/elhaam/.cache/touchpad-investigation/release-audit.oY4Hcwux
cd "$audit_dir"
PATH="$audit_dir/build-tools/bin:$PATH" \
PKG_CONFIG_PATH="$audit_dir/build-deps/usr/lib/x86_64-linux-gnu/pkgconfig" \
  /usr/bin/python3 "$audit_dir/meson-launch.py" setup --reconfigure \
  libinput-build libinput
PYTHONPATH="$audit_dir/build-tools" "$audit_dir/build-tools/bin/ninja" \
  -C libinput-build libinput libinput-debug-events libinput-record libinput-quirks
```

No install step is needed. The source tree also supplies the newer `libinput-analyze-per-slot-delta.py`, whose Python libevdev/YAML dependencies are already installed. Its help works. It can analyze an existing YAML recording without accessing the device or changing the desktop.

## Experiment that determines the required fix

First capture one good and one bad occurrence on this machine. Do not reset/rebind before the bad recording. Include repeated one-finger landings, lift/relocation, and the precise gesture that causes the fault. Record whether another finger, a palm, typing, resume or a disable/enable event preceded it. Use the real touchpad event node; exclude keyboards and the companion Mouse node unless separately required.

The parent can run the installed and isolated debug contexts alongside a raw recording. These readers do not inject pointer movement into the desktop. Set identical diagnostic-context options to the actual X.Org settings when comparing processed output, including tapping, drag, profile and speed. Debug-context defaults are not necessarily the desktop's settings. [Tool context behavior](https://manpages.ubuntu.com/manpages/jammy/man1/libinput.1.html).

Example preparation commands, **not run against the device during this audit**:

```bash
audit_dir=/home/elhaam/.cache/touchpad-investigation/release-audit.oY4Hcwux
# Re-identify the event node first. event5 was correct at audit time only.
touchpad_node=/dev/input/event5

# Separate terminals, same reproduction. Ctrl+C ends each reader.
sudo libinput record --output-file "$audit_dir/failure.yml" "$touchpad_node"
sudo libinput debug-events --verbose --device "$touchpad_node"
sudo env LIBINPUT_QUIRKS_DIR="$audit_dir/libinput/quirks" \
  "$audit_dir/libinput-build/libinput-debug-events" \
  --verbose --device "$touchpad_node"

# Once the recording is closed, unprivileged offline inspection:
/usr/bin/python3 "$audit_dir/libinput/tools/libinput-analyze-per-slot-delta.py" \
  --use-mm --show-distance "$audit_dir/failure.yml"
```

Pass matching context options to both debug commands before interpreting motion differences. The baseline speed option is `--set-speed=0.73529411764705888`; the tap-drag option is `--enable-drag`. Confirm tapping and acceleration profile from the parent's captured X.Org properties rather than guess. The source-quirk environment variable is explicit because tools running in the AppImage environment may fail to recognize their source/build directory. The diagnostic commands never export a replacement library path into the desktop.

| Observation on the same failing interval | What it supports | Next source work |
| --- | --- | --- |
| HID report itself has the bad coordinates or reuses a contact without its release | Fault originates before libinput; firmware, transport, sensor conditions and hardware remain possible | Inspect report descriptor, contact count/ID, confidence, scan-time and raw reports. A kernel workaround needs a reproducible device-specific rule and a multi-packet/contact regression test. Firmware may be the actual correction. |
| HID report is consistent but evdev assigns the wrong slot or omits release | HID/input conversion defect | Fix `hid-multitouch.c` or input slot processing at the first wrong transition. Compare with the zero-count and sticky-finger fixes under their exact preconditions. |
| Raw evdev is correct; old libinput output is wrong and 1.32 output is correct | Userspace change can explain the same input | Replay/bisect in a disposable VM or otherwise isolated input environment, identify the exact fixing commit, and backport only that fix. Do not replay through host uinput into the live session as the first comparison. |
| Raw evdev is correct and both library versions produce bad output | A source fix or measured quirk may still be needed | Preserve the recording as a regression fixture; inspect `tp_new_touch`, `tp_sync_touch`, `tp_end_touch`, history reset and jump/pressure logic. Correct the first violated lifecycle invariant, rather than suppress every first delta or disable jump protection. |
| Both diagnostic contexts produce correct output while the desktop is wrong | X.Org configuration/bridge, Touchégg or another consumer is implicated | Compare with XInput raw/processed events and parent logs. Only then consider a controlled temporary session/service experiment. |
| Physical size and advertised resolution disagree | Wrong units may distort thresholds and acceleration | Measure the pad, calculate proper resolution, and test a narrowly matched temporary quirk in an isolated context before proposing a persistent correction. |

A raw evdev recording alone cannot distinguish a kernel conversion bug from a bad HID report. A non-grabbing HID recording and descriptor are needed for that boundary; the parent source/log investigation can supply them if evdev is already wrong. None of these observations alone proves broken physical hardware.

For hardware/software discrimination, identify the second laptop's device IDs, firmware, kernel, libinput version and exact symptom. Reproduce with the same finger pattern on battery and AC, with a clean dry pad and without a dock/peripheral influence, changing one condition at a time. A fresh live environment or already installed alternate OS on the **same laptop** can then separate the installed userspace/configuration from a cross-OS or firmware problem. A live-boot kernel change is a separate variable. Success or failure under a different OS is evidence, not a complete hardware diagnosis, because drivers can interpret or filter identical bad reports differently.

Upstream's jumping-cursor documentation says the warning is rate-limited and often reflects firmware or kernel data, while some jumps are suppressed as intended. Its requested evidence is a `libinput record` attachment. The log category `kernel bug` is emitted by libinput and is not an independent kernel diagnostic proving the cause. [Upstream explanation and reporting guidance](https://gitlab.freedesktop.org/libinput/libinput/-/blob/1.32.0/doc/user/touchpad-jumping-cursors.rst).

The blockers for an installation recommendation are the missing failing recording, an unverified match to a particular fix, and the still-unknown second laptop. The parent should combine this audit with its source/log findings. If no existing commit fits, the required deliverable is a trace-backed source correction at the first wrong transition, with a regression recording and an isolated before/after result.
