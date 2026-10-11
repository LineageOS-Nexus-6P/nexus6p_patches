#!/usr/bin/env python3

import csv
import os
import subprocess
import tempfile
import unittest
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
            if len(row) != 4:
                raise AssertionError(f"invalid projects.tsv row: {row!r}")
            projects.append(row)
    return projects


@unittest.skipUnless(ANDROID_ROOT_VALUE, "ANDROID_BUILD_TOP is required")
class RealPatchSeriesTest(unittest.TestCase):
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

    def test_all_platform_series_reproduce_the_current_working_trees(self):
        projects = load_projects()
        self.assertGreaterEqual(len(projects), 19)
        paths = [row[0] for row in projects]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(STANDALONE_PROJECTS.isdisjoint(paths))

        for project_path, baseline, result_tree, patch_directory in projects:
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
                self.assertEqual(
                    run("git", "rev-parse", "HEAD^{tree}", cwd=repository).stdout.strip(),
                    result_tree,
                )
                run("git", "cat-file", "-e", f"{baseline}^{{commit}}", cwd=repository)

                with tempfile.TemporaryDirectory() as temporary_directory:
                    clone = Path(temporary_directory) / "project"
                    run("git", "clone", "--quiet", "--shared", str(repository), str(clone))
                    run("git", "config", "user.name", "Patch Kit Test", cwd=clone)
                    run(
                        "git",
                        "config",
                        "user.email",
                        "patch-kit@example.invalid",
                        cwd=clone,
                    )
                    run("git", "checkout", "--quiet", "--detach", baseline, cwd=clone)
                    run("git", "am", "--quiet", "--3way", *(str(p) for p in patches), cwd=clone)
                    self.assertEqual(
                        run("git", "rev-parse", "HEAD^{tree}", cwd=clone).stdout.strip(),
                        result_tree,
                    )


if __name__ == "__main__":
    unittest.main()
