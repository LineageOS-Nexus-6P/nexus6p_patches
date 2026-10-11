#!/usr/bin/env python3

import csv
import hashlib
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
        readme = (device / "README.md").read_text(encoding="utf-8")
        self.assertIn("LineageOS 22.2", readme)
        self.assertIn("PhhIms", readme)
        self.assertIn("nexus6p_patches", readme)
        self.assertNotIn("CAMERA_PORTING_STATUS", readme)

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

    def test_ril_golden_baseline_is_unchanged(self):
        verifier = (
            ANDROID_ROOT
            / "device/huawei/angler/tests/verify_ril_golden_baseline.sh"
        )
        result = subprocess.run(
            ("bash", str(verifier)),
            cwd=ANDROID_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.assertIn("Angler RIL golden baseline: PASS", result.stdout)

    def test_ril_golden_hashes_do_not_pin_official_platform_files(self):
        manifest = (
            ANDROID_ROOT
            / "device/huawei/angler/tests/ril_golden_files.sha256"
        )
        allowed_roots = (
            "device/huawei/angler/",
            "vendor/huawei/angler/",
            "kernel/huawei/angler/",
            "packages/apps/PhhIms/",
        )
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            path = line.split(maxsplit=1)[1]
            with self.subTest(path=path):
                self.assertTrue(path.startswith(allowed_roots))

    def test_vendor_blob_provenance_is_retained(self):
        provenance = ANDROID_ROOT / "vendor/huawei/angler/BLOB_PROVENANCE.tsv"
        self.assertTrue(provenance.is_file())
        self.assertGreater(provenance.stat().st_size, 0)
        vendor = provenance.parent
        with provenance.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        destinations = [row["destination"] for row in rows]
        tracked_blobs = {
            path.removeprefix("proprietary/")
            for path in git(vendor, "ls-files", "proprietary").splitlines()
        }
        self.assertEqual(len(destinations), len(set(destinations)))
        self.assertEqual(set(destinations), tracked_blobs)
        for row in rows:
            destination = vendor / "proprietary" / row["destination"]
            with self.subTest(destination=row["destination"]):
                self.assertTrue(destination.is_file())
                payload = destination.read_bytes()
                self.assertEqual(hashlib.sha256(payload).hexdigest(), row["sha256"])
                self.assertEqual(len(payload), int(row["bytes"]))

    def test_vendor_tree_contains_no_audit_only_camera_blob(self):
        vendor = ANDROID_ROOT / "vendor/huawei/angler"
        audit_only_blob = "vendor/lib64/libmmcamera2_q3a_core.so"
        self.assertFalse((vendor / "proprietary" / audit_only_blob).exists())
        self.assertNotIn(
            audit_only_blob,
            (vendor / "BLOB_PROVENANCE.tsv").read_text(encoding="utf-8"),
        )
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
        self.assertTrue((phhims / "tools/test_android_tree_contract.py").is_file())
        readme = (phhims / "README.md").read_text(encoding="utf-8")
        self.assertIn("Nexus 6P", readme)
        self.assertIn("LineageOS 22.2", readme)
        self.assertIn("Ultra-Legacy-Hippeastrum", readme)
        self.assertNotIn("git submodule", readme)


if __name__ == "__main__":
    unittest.main()
