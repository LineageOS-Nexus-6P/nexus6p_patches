#!/usr/bin/env python3

import csv
import os
import subprocess
import unittest
from collections import Counter
from pathlib import Path


PATCH_KIT_ROOT = Path(__file__).resolve().parents[1]
ANDROID_ROOT_VALUE = os.environ.get("ANDROID_BUILD_TOP")
ANDROID_ROOT = Path(ANDROID_ROOT_VALUE).resolve() if ANDROID_ROOT_VALUE else None
LOCK_FILE = PATCH_KIT_ROOT / "projects.tsv"

STANDALONE_PROJECTS = {
    "device/huawei/angler",
    "vendor/huawei/angler",
    "kernel/huawei/angler",
    "packages/apps/PhhIms",
}


def run(*args: str, cwd: Path | None = None, check: bool = True):
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def load_projects():
    projects = []
    with LOCK_FILE.open(encoding="utf-8", newline="") as stream:
        for row in csv.reader(stream, delimiter="\t"):
            if not row or row[0].startswith("#"):
                continue
            if len(row) != 2:
                raise AssertionError(f"invalid projects.tsv row: {row!r}")
            projects.append(row)
    return projects


@unittest.skipUnless(ANDROID_ROOT_VALUE, "ANDROID_BUILD_TOP is required")
class RealPatchSeriesTest(unittest.TestCase):
    def test_series_do_not_hide_bulk_formatting_rewrites(self):
        for project_path, patch_directory in load_projects():
            for patch in sorted((PATCH_KIT_ROOT / patch_directory).glob("*.patch")):
                added = Counter()
                removed = Counter()
                in_hunk = False
                for line in patch.read_text(encoding="utf-8").splitlines():
                    if line == "-- " or line.startswith("diff --git "):
                        in_hunk = False
                    elif line.startswith("@@"):
                        in_hunk = True
                    elif in_hunk and line.startswith("+") and not line.startswith("+++"):
                        added[" ".join(line[1:].split())] += 1
                    elif in_hunk and line.startswith("-") and not line.startswith("---"):
                        removed[" ".join(line[1:].split())] += 1
                formatting_pairs = sum((added & removed).values())
                with self.subTest(project=project_path, patch=patch.name):
                    self.assertLessEqual(
                        formatting_pairs,
                        40,
                        "patch contains a bulk formatting rewrite",
                    )

    def test_gps_patch_excludes_obsolete_build_system_files(self):
        gps = ANDROID_ROOT / "hardware/qcom/gps"
        for relative_path in (
            "Android.mk",
            "msm8994/Android.mk",
            "msm8994/utils/Makefile.am",
        ):
            with self.subTest(path=relative_path):
                self.assertFalse((gps / relative_path).exists())

    def test_legacy_radio_unit_tests_have_soong_targets(self):
        legacy_radio = (
            ANDROID_ROOT / "hardware/lineage/interfaces/radio/1.4/legacy"
        )
        build_file = (legacy_radio / "Android.bp").read_text(encoding="utf-8")
        for test_source in sorted((legacy_radio / "tests").glob("*.cpp")):
            with self.subTest(source=test_source.name):
                self.assertIn(f'"tests/{test_source.name}"', build_file)

    def test_non_ebpf_bypass_is_scoped_to_the_legacy_opt_out(self):
        connectivity = ANDROID_ROOT / "packages/modules/Connectivity"
        bpf_maps = (
            connectivity
            / "service/src/com/android/server/BpfNetMaps.java"
        ).read_text(encoding="utf-8")
        network_stats = (
            connectivity
            / "service-t/src/com/android/server/net/NetworkStatsService.java"
        ).read_text(encoding="utf-8")
        bpf_header = (
            connectivity / "bpf/headers/include/bpf/BpfMap.h"
        ).read_text(encoding="utf-8")

        self.assertIn("ro.kernel.ebpf.supported", bpf_maps)
        self.assertIn("isBpfSupported()", network_stats)
        self.assertNotIn("catch (Throwable t)", bpf_maps)
        self.assertIn("bool allowMissing = false", bpf_header)
        self.assertIn("if (allowMissing && !mMapFd.ok()) return;", bpf_header)

    def test_all_platform_series_are_recognized_in_the_current_working_trees(self):
        projects = load_projects()
        self.assertGreaterEqual(len(projects), 19)
        paths = [row[0] for row in projects]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(STANDALONE_PROJECTS.isdisjoint(paths))

        result = run(
            str(PATCH_KIT_ROOT / "apply.sh"),
            "--source",
            str(ANDROID_ROOT),
            "--check",
        )
        for project_path, patch_directory in projects:
            with self.subTest(project=project_path):
                repository = ANDROID_ROOT / project_path
                patches = sorted((PATCH_KIT_ROOT / patch_directory).glob("*.patch"))
                self.assertTrue(repository.is_dir())
                self.assertTrue(patches)
                self.assertEqual(
                    run(
                        "git",
                        "status",
                        "--porcelain=v1",
                        "--untracked-files=all",
                        cwd=repository,
                    ).stdout,
                    "",
                )
                self.assertIn(f"already applied: {project_path}", result.stdout)


if __name__ == "__main__":
    unittest.main()
