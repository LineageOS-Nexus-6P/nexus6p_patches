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
Six ordered patches then adapt it to Android 15 Soong visibility and
package-local headers. The exact series is in `patches/hardware_qcom_gps`.

### `system/core`

The first `system/core` patch retains PHH's old-kernel behavior for devices
without usable cgroup v2. The second patch is the Angler Android 15 adaptation:
it detects an unusable hierarchy, avoids repeated failures, and keeps one
actionable warning.

## Designs adapted rather than copied

UL's old-kernel approach informed these Angler-specific implementations:

- the explicit non-eBPF route across `Connectivity`, `DnsResolver`, and
  `netd` when `ro.kernel.ebpf.supported=false`;
- the in-kernel LMK path that does not start unsupported PSI/memcg monitors;
- compatibility handling for legacy cgroups and process migration.

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

Display and media use the pinned `davigamer987` MSM8994 donor branches. Camera
comes from Angler/Google/LineageOS 17.1 lineage, while the kernel combines the
Angler base with individually reviewed Google, OnePlus, and Sony-compatible
backports.

## Manifest policy

The official LineageOS `default.xml` is not edited. The local manifest adds
only the four Nexus 6P repositories, replaces the incomplete current display
project, and adds the MSM8994 media donor. It contains no LineageOS-UL remote.
