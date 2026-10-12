# LineageOS-UL usage in the Nexus 6P port

LineageOS-UL was used only as a patch-level donor for gaps caused by the Nexus
6P Linux 3.10 kernel and removed MSM8994 platform code. The standard
LineageOS 22.2 manifest remains the platform authority.

## Directly derived components

### `packages/apps/PhhIms`

The standalone Angler repository descends from
`Ultra-Legacy-Hippeastrum/ims`, branch `hammerhead`, at commit
`a6ab624109e2ba01d6d9e59755114fd85c2b5f8e`. The Angler branch removes the
old submodule/JNI dependency, supplies a self-contained Soong build, and adds
the tested P-CSCF, subscription identity, network request, and SIP AKA behavior.

### `hardware/qcom/gps`

The missing MSM8994 `core`, `utils`, and `platform_lib_abstractions` closure
was restored from `Ultra-Legacy-Hippeastrum/android_hardware_qcom_gps`,
`lineage-21.0`, commit `bf8d5049a6318fad4791ebdbb13231ecfb373685`.
One squashed patch carries only the runtime sources and Android 15 Soong
definitions; obsolete Android Make and autotools files are excluded. The
exact patch is in `patches/hardware_qcom_gps`.

### `system/core`

PHH's old-kernel behavior informed the Angler Android 15 adaptation, but its
broad `init` error suppression is deliberately not carried. The retained
patch handles the missing cgroup v2 hierarchy inside `libprocessgroup`, avoids
repeated failures, and keeps one actionable warning without hiding unrelated
service-start errors.

## Designs adapted rather than copied

UL's old-kernel approach informed these Angler-specific implementations:

- the explicit non-eBPF route across `Connectivity`, `DnsResolver`, and
  `netd` when `ro.kernel.ebpf.supported=false`;
- the in-kernel LMK path that does not start unsupported PSI/memcg monitors;
- compatibility handling for legacy cgroups and process migration.

The non-eBPF route is required for the 3.10 kernel and is part of the
real-device-tested voice-plus-LTE baseline. It keeps networking operational,
but it is not equivalent to Android 15's eBPF-backed per-UID firewall, data
saver, and traffic-accounting enforcement. Changing this route requires a
separate security review and another combined calls-plus-LTE device test; it
must not be casually replaced while preparing the public trees.

These changes were written against the LineageOS 22.2 / Android 15 sources and
are not copied UL framework trees.

## Deliberately not copied

The following UL changes are not copied into this port:

- the UL platform manifest or its mass project overrides;
- permissive SELinux, ignored `neverallow` rules, or broad policy bypasses;
- bionic text-relocation allowances;
- UL RenderEngine/GLES and `frameworks/av` replacement series;
- old RIL v6/v8/v9 compatibility patches, because Angler uses RIL v12;
- a complete UL kernel or an `msm8994-common` device tree.

Display and media use organization-hosted forks of the pinned `davigamer987`
MSM8994 donor branches. Camera comes from Angler/Google/LineageOS 17.1 lineage,
while the kernel combines the Angler base with individually reviewed Google,
OnePlus, and Sony-compatible backports.

## Source policy

The official LineageOS `default.xml` is not edited. The four Nexus 6P
repositories are cloned from `LineageOS-Nexus-6P` after the official sync.
The MSM8994 display and media forks are checked out from
`LineageOS-Nexus-6P` separately. No LineageOS-UL platform remote is added.
