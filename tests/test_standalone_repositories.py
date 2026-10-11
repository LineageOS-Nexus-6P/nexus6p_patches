#!/usr/bin/env python3

import csv
import hashlib
import os
import subprocess
import unittest
from pathlib import Path


ANDROID_ROOT_VALUE = os.environ.get("ANDROID_BUILD_TOP")
ANDROID_ROOT = Path(ANDROID_ROOT_VALUE).resolve() if ANDROID_ROOT_VALUE else None
LOCAL_WORKSPACE_PREFIX = "/home" "/surface"

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
        readme = (device / "README.md").read_text(encoding="utf-8")
        self.assertIn("LineageOS 22.2", readme)
        self.assertIn("PhhIms", readme)
        self.assertIn("nexus6p_patches", readme)
        self.assertNotIn("CAMERA_PORTING_STATUS", readme)

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
        private_suffixes = {".pk8", ".pem"}
        for relative_path in REPOSITORIES:
            repository = ANDROID_ROOT / relative_path
            tracked = git(repository, "ls-files", "-z").split("\0")
            for tracked_path in tracked:
                if tracked_path:
                    self.assertNotIn(Path(tracked_path).suffix, private_suffixes)

    def test_vendor_blob_provenance_is_retained(self):
        provenance = ANDROID_ROOT / "vendor/huawei/angler/BLOB_PROVENANCE.tsv"
        self.assertTrue(provenance.is_file())
        self.assertGreater(provenance.stat().st_size, 0)
        vendor = provenance.parent
        with provenance.open(encoding="utf-8", newline="") as stream:
            rows = csv.DictReader(stream, delimiter="\t")
            for row in rows:
                destination = vendor / "proprietary" / row["destination"]
                with self.subTest(destination=row["destination"]):
                    self.assertTrue(destination.is_file())
                    payload = destination.read_bytes()
                    self.assertEqual(hashlib.sha256(payload).hexdigest(), row["sha256"])
                    self.assertEqual(len(payload), int(row["bytes"]))

    def test_phhims_is_self_contained(self):
        phhims = ANDROID_ROOT / "packages/apps/PhhIms"
        self.assertFalse((phhims / ".gitmodules").exists())
        self.assertTrue((phhims / "Android.bp").is_file())
        self.assertTrue((phhims / "tools/test_android_tree_contract.py").is_file())
        readme = (phhims / "README.md").read_text(encoding="utf-8")
        self.assertIn("Nexus 6P", readme)
        self.assertIn("LineageOS 22.2", readme)
        self.assertIn("Ultra-Legacy-Hippeastrum", readme)
        self.assertNotIn("git submodule", readme)


if __name__ == "__main__":
    unittest.main()
