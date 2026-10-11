# Nexus 6P patches for LineageOS 22.2

This repository converts a freshly synced, clean official LineageOS 22.2 checkout
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

`android_packages_apps_PhhIms` is intentionally separate: the local manifest
downloads it directly into the Android environment.

## Clean source preparation

```sh
mkdir lineage-22.2-angler
cd lineage-22.2-angler

repo init -u https://github.com/LineageOS/android.git \
    -b lineage-22.2

mkdir -p .repo/local_manifests
sed 's/@NEXUS6P_ORG@/YOUR_GITHUB_ORGANIZATION/g' \
    ../nexus6p_patches/local_manifests/angler.xml.template \
    > .repo/local_manifests/angler.xml

repo sync -c -j6
```

Replace `YOUR_GITHUB_ORGANIZATION` only after the four standalone repositories
exist. The manifest follows their `lineage-22.2` branches and the MSM8994 donor
branches. It does not add a LineageOS-UL platform remote.

## Apply all platform changes

Apply every required project series with one command:

```sh
../nexus6p_patches/apply.sh --source "$PWD"
```

The script refuses a dirty repository, an unfinished `git am`, or a build ID
other than `BP1A.250505.005`. It validates every series against the currently
synced project HEAD in a temporary clone before changing any project and treats
a clean second invocation as already applied. It never runs a hard reset and
never overwrites unrelated local work. `--check` is available as an optional
no-write preflight, but it is not required before the normal command.

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

## Updating LineageOS 22.2

After a later `repo sync`, run `apply.sh` again on clean project heads. Its
temporary-clone preflight will stop before modifying the checkout if an
official update conflicts with a patch. Any radio-related patch update still
requires calls and LTE data to be tested together on the real device.
