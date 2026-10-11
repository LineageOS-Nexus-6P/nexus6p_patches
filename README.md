# Nexus 6P patches for LineageOS 22.2

This repository converts a pinned, clean official LineageOS 22.2 checkout
into the tested Nexus 6P (`angler`) Android 15 source tree. Platform changes
are stored as ordered per-project mail patches because the Android checkout is
made of many independent Git repositories; `apply.sh` exposes them as one
validated operation.

Nothing in this repository replaces the complete LineageOS platform with an
Ultra Legacy tree. The exact limited UL provenance is documented in
[`docs/UL_USAGE.md`](docs/UL_USAGE.md).

## Required standalone repositories

Create these repositories in the Nexus 6P organization on branch
`lineage-22.2`:

| Repository | Android path |
| --- | --- |
| `android_device_huawei_angler` | `device/huawei/angler` |
| `android_vendor_huawei_angler` | `vendor/huawei/angler` |
| `android_kernel_huawei_angler` | `kernel/huawei/angler` |
| `android_packages_apps_PhhIms` | `packages/apps/PhhIms` |

`standalone-repositories.tsv` records the exact locally prepared heads and
trees. `android_packages_apps_PhhIms` is intentionally separate: the local
manifest downloads it directly into the Android environment.

## Clean source preparation

The patch baseline is official `LineageOS/android` commit
`a2a0887cc58d45a6950a138b08a5724ea374c3d0` from `lineage-22.2`.

```sh
mkdir lineage-22.2-angler
cd lineage-22.2-angler

repo init -u https://github.com/LineageOS/android.git \
    -b a2a0887cc58d45a6950a138b08a5724ea374c3d0 \
    --manifest-upstream-branch=lineage-22.2

mkdir -p .repo/local_manifests
sed 's/@NEXUS6P_ORG@/YOUR_GITHUB_ORGANIZATION/g' \
    ../nexus6p_patches/local_manifests/angler.xml.template \
    > .repo/local_manifests/angler.xml

repo sync -c -j6
```

Replace `YOUR_GITHUB_ORGANIZATION` only after the four standalone repositories
exist. The manifest also pins the MSM8994 display and media donor branches; it
does not add a LineageOS-UL platform remote.

## Apply all platform changes

First perform a complete no-write preflight:

```sh
../nexus6p_patches/apply.sh --source "$PWD" --check
```

Then apply every required project series with one command:

```sh
../nexus6p_patches/apply.sh --source "$PWD"
```

The script refuses a dirty repository, an unexpected baseline, an unfinished
`git am`, or a build ID other than `BP1A.250505.005`. It validates every series
in a temporary clone before changing any project, checks the resulting tree,
and treats a clean second invocation as already applied. It never runs a hard
reset and never overwrites unrelated local work.

## Verify and build

```sh
../nexus6p_patches/verify.sh --source "$PWD"

source build/envsetup.sh
lunch lineage_angler-bp1a-userdebug
mka bacon -j6
```

Do not use an `AP4A` platform tree. The `OPM7.181205.001` strings in the Angler
device and vendor repositories identify the final stock firmware and stock
fingerprint; they do not change the Android 15 platform build ID.

## Signing and publication exclusions

Release signing is local policy. Keep private signing keys under
`vendor/lineage-priv/keys` or another private location outside every public
manifest. Never commit private signing keys, generated certificates, factory
images, OTA packages, device logs, ramoops dumps, extracted user data, or the
local `out/` directory.

The proprietary vendor tree includes `BLOB_PROVENANCE.tsv`. Review applicable
redistribution terms before making proprietary binaries public.

## Updating the official baseline

Do not apply these patches blindly to a newer LineageOS manifest. Update one
project at a time, rebase its mail series, update `projects.tsv`, and run
`verify.sh` plus a clean build and real-device regression pass. Calls and LTE
data must be tested together before accepting any radio-related update.
