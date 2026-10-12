#!/usr/bin/env python3

import csv
import json
import os
import subprocess
import unittest
from pathlib import Path


ANDROID_ROOT_VALUE = os.environ.get("ANDROID_BUILD_TOP")
ANDROID_ROOT = Path(ANDROID_ROOT_VALUE).resolve() if ANDROID_ROOT_VALUE else None
PATCH_KIT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_WORKSPACE_PREFIX = "/home" "/surface"
PRIVATE_KEY_MARKER = "BEGIN " "PRIVATE KEY"

REPOSITORIES = (
    "device/huawei/angler",
    "vendor/huawei/angler",
    "kernel/huawei/angler",
    "packages/apps/PhhIms",
)

FORBIDDEN_DEVICE_PATHS = (
    "CAMERA_PORTING_STATUS.md",
    "RIL_DONOR_ANALYSIS.md",
    "RIL_GOLDEN_BASELINE.md",
    "camera/QCamera2/stack/mm-camera-test",
    "camera/QCamera2/stack/mm-jpeg-interface/test",
    "__pycache__",
    "tests/__pycache__",
)


def git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ("git", "-C", str(repository), *arguments),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


@unittest.skipUnless(ANDROID_ROOT_VALUE, "ANDROID_BUILD_TOP is required")
class StandaloneRepositoryTest(unittest.TestCase):
    def test_repositories_are_clean_lineage_22_2_branches(self):
        for relative_path in REPOSITORIES:
            with self.subTest(repository=relative_path):
                repository = ANDROID_ROOT / relative_path
                self.assertTrue(repository.is_dir())
                self.assertEqual(git(repository, "branch", "--show-current"), "lineage-22.2")
                self.assertEqual(
                    git(repository, "status", "--porcelain=v1", "--untracked-files=all"),
                    "",
                )

    def test_device_tree_has_no_local_diagnostics_or_python_cache(self):
        device = ANDROID_ROOT / "device/huawei/angler"
        for relative_path in FORBIDDEN_DEVICE_PATHS:
            with self.subTest(path=relative_path):
                self.assertFalse((device / relative_path).exists())

    def test_device_dependencies_match_the_published_repository_layout(self):
        dependency_file = ANDROID_ROOT / "device/huawei/angler/lineage.dependencies"
        dependencies = json.loads(dependency_file.read_text(encoding="utf-8"))
        self.assertEqual(
            dependencies,
            [
                {
                    "repository": "android_kernel_huawei_angler",
                    "target_path": "kernel/huawei/angler",
                    "branch": "lineage-22.2",
                },
                {
                    "repository": "android_vendor_huawei_angler",
                    "target_path": "vendor/huawei/angler",
                    "branch": "lineage-22.2",
                },
                {
                    "repository": "android_packages_apps_PhhIms",
                    "target_path": "packages/apps/PhhIms",
                    "branch": "lineage-22.2",
                },
            ],
        )

    def test_public_sources_do_not_embed_the_local_workspace_path(self):
        for relative_path in REPOSITORIES:
            repository = ANDROID_ROOT / relative_path
            paths = git(
                repository, "ls-files", "--cached", "--others", "--exclude-standard"
            ).splitlines()
            for tracked_path in paths:
                path = repository / tracked_path
                if not path.is_file() or path.is_symlink():
                    continue
                try:
                    contents = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                self.assertNotIn(
                    LOCAL_WORKSPACE_PREFIX, contents, f"local path embedded in {path}"
                )

    def test_device_executable_files_have_a_script_shebang(self):
        device = ANDROID_ROOT / "device/huawei/angler"
        index = git(device, "ls-files", "--stage")
        for line in index.splitlines():
            mode, _, _, tracked_path = line.split(maxsplit=3)
            if mode != "100755":
                continue
            path = device / tracked_path
            with self.subTest(path=tracked_path):
                self.assertEqual(path.read_bytes()[:2], b"#!")

    def test_public_repositories_contain_no_private_signing_keys(self):
        private_suffixes = {".pk8", ".pem", ".jks", ".keystore"}
        for relative_path in REPOSITORIES:
            repository = ANDROID_ROOT / relative_path
            tracked = git(repository, "ls-files", "-z").split("\0")
            for tracked_path in tracked:
                if tracked_path:
                    path = repository / tracked_path
                    self.assertNotIn(path.suffix, private_suffixes)
                    if not path.is_file() or path.is_symlink():
                        continue
                    try:
                        contents = path.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        continue
                    self.assertNotIn(PRIVATE_KEY_MARKER, contents)

    def test_standalone_repository_list_matches_checked_out_branches(self):
        lock_file = PATCH_KIT_ROOT / "standalone-repositories.tsv"
        with lock_file.open(encoding="utf-8", newline="") as stream:
            rows = [
                row
                for row in csv.reader(stream, delimiter="\t")
                if row and not row[0].startswith("#")
            ]
        for relative_path, branch in rows:
            repository = ANDROID_ROOT / relative_path
            with self.subTest(repository=relative_path):
                self.assertEqual(git(repository, "branch", "--show-current"), branch)

    def test_vendor_tree_contains_no_audit_only_camera_blob(self):
        vendor = ANDROID_ROOT / "vendor/huawei/angler"
        audit_only_blob = "vendor/lib64/libmmcamera2_q3a_core.so"
        self.assertFalse((vendor / "proprietary" / audit_only_blob).exists())
        self.assertNotIn(
            audit_only_blob,
            (
                ANDROID_ROOT / "device/huawei/angler/proprietary-files.txt"
            ).read_text(encoding="utf-8"),
        )

    def test_phhims_is_self_contained(self):
        phhims = ANDROID_ROOT / "packages/apps/PhhIms"
        self.assertFalse((phhims / ".gitmodules").exists())
        self.assertTrue((phhims / "Android.bp").is_file())
        self.assertTrue((phhims / "app/src/main/AndroidManifest.xml").is_file())
        self.assertTrue((phhims / "app/src/main/java/me/phh/sip/SipHandler.kt").is_file())
        readme = (phhims / "README.md").read_text(encoding="utf-8")
        self.assertIn("Nexus 6P", readme)
        self.assertIn("LineageOS 22.2", readme)
        self.assertIn("Ultra-Legacy-Hippeastrum", readme)
        self.assertNotIn("git submodule", readme)


if __name__ == "__main__":
    unittest.main()
