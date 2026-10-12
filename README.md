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

Create these repositories in
[`LineageOS-Nexus-6P`](https://github.com/LineageOS-Nexus-6P) on branch
`lineage-22.2`:

| Repository | Android path |
| --- | --- |
| `android_device_huawei_angler` | `device/huawei/angler` |
| `android_vendor_huawei_angler` | `vendor/huawei/angler` |
| `android_kernel_huawei_angler` | `kernel/huawei/angler` |
| `android_packages_apps_PhhIms` | `packages/apps/PhhIms` |

`android_packages_apps_PhhIms` is cloned directly into the Android source tree.

## Clean source preparation

```sh
mkdir lineage-22.2-angler
cd lineage-22.2-angler

repo init -u https://github.com/LineageOS/android.git \
    -b lineage-22.2 --git-lfs

repo sync -c -j6
```

## Copy the Nexus 6P trees

```sh
mkdir -p device/huawei vendor/huawei kernel/huawei packages/apps

git clone -b lineage-22.2 --single-branch \
    https://github.com/LineageOS-Nexus-6P/android_device_huawei_angler.git \
    device/huawei/angler
git clone -b lineage-22.2 --single-branch \
    https://github.com/LineageOS-Nexus-6P/android_vendor_huawei_angler.git \
    vendor/huawei/angler
git clone -b lineage-22.2 --single-branch \
    https://github.com/LineageOS-Nexus-6P/android_kernel_huawei_angler.git \
    kernel/huawei/angler
git clone -b lineage-22.2 --single-branch \
    https://github.com/LineageOS-Nexus-6P/android_packages_apps_PhhIms.git \
    packages/apps/PhhIms
```

The current device tree also requires the MSM8994 display and media donor
branches:

```sh
git -C hardware/qcom/display remote add msm8994-donor \
    https://github.com/LineageOS-Nexus-6P/hardware_qcom_display.git
git -C hardware/qcom/display fetch msm8994-donor \
    lineage-23.0-caf-msm8994
git -C hardware/qcom/display switch -C lineage-23.0-caf-msm8994 FETCH_HEAD

mkdir -p hardware/qcom-caf/msm8994
git clone -b lineage-23.0-caf-msm8994 --single-branch \
    https://github.com/LineageOS-Nexus-6P/hardware_qcom_media.git \
    hardware/qcom-caf/msm8994/media
```

## Apply all platform changes

Clone the patch directory inside the LineageOS source tree and apply every
required project series with one command:

```sh
git clone -b lineage-22.2 --single-branch \
    https://github.com/LineageOS-Nexus-6P/nexus6p_patches.git \
    nexus6p_patches

./nexus6p_patches/apply.sh --source .
```

The script refuses a dirty repository, an unfinished `git am`, or a build ID
other than `BP1A.250505.005`. It validates every series against the currently
synced project HEAD in a temporary clone before changing any project and treats
a clean second invocation as already applied. It never runs a hard reset and
never overwrites unrelated local work. `--check` is available as an optional
no-write preflight, but it is not required before the normal command.

## Verify and build

```sh
./nexus6p_patches/verify.sh --source .

source build/envsetup.sh
lunch lineage_angler-bp1a-userdebug
mka bacon -j6
```

Do not use an `AP4A` platform tree. The `OPM7.181205.001` strings in the Angler
device and vendor repositories identify the final stock firmware and stock
fingerprint; they do not change the Android 15 platform build ID.

## Updating LineageOS 22.2

After a later `repo sync`, run `apply.sh` again on clean project heads. Its
temporary-clone preflight will stop before modifying the checkout if an
official update conflicts with a patch. Any radio-related patch update still
requires calls and LTE data to be tested together on the real device.
