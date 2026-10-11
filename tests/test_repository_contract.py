#!/usr/bin/env python3

import csv
import stat
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_WORKSPACE_PREFIX = "/home" "/surface"
PRIVATE_KEY_MARKER = "BEGIN " "PRIVATE KEY"


def tracked_files():
    output = subprocess.run(
        ("git", "ls-files", "-z"),
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    return [ROOT / entry.decode() for entry in output.rstrip(b"\0").split(b"\0")]


class RepositoryContractTest(unittest.TestCase):
    def test_documentation_covers_the_reproducible_build_workflow(self):
        readme_path = ROOT / "README.md"
        self.assertTrue(readme_path.is_file())
        readme = readme_path.read_text(encoding="utf-8")
        for required in (
            "LineageOS/android",
            "lineage-22.2",
            "-b a2a0887cc58d45a6950a138b08a5724ea374c3d0",
            "--manifest-upstream-branch=lineage-22.2",
            "repo sync -c -j6",
            "android_packages_apps_PhhIms",
            "apply.sh",
            "BP1A.250505.005",
            "mka bacon -j6",
            "private signing keys",
        ):
            with self.subTest(required=required):
                self.assertIn(required, readme)

    def test_ul_usage_is_documented_without_an_ul_manifest_override(self):
        ul_document = ROOT / "docs/UL_USAGE.md"
        self.assertTrue(ul_document.is_file())
        text = ul_document.read_text(encoding="utf-8")
        self.assertIn("packages/apps/PhhIms", text)
        self.assertIn("hardware/qcom/gps", text)
        self.assertIn("system/core", text)
        self.assertIn("not copied", text.lower())
        self.assertNotIn("LineageOS-UL/android.git", text)

    def test_standalone_repository_lock_has_four_clean_public_projects(self):
        lock = ROOT / "standalone-repositories.tsv"
        self.assertTrue(lock.is_file())
        with lock.open(encoding="utf-8", newline="") as stream:
            rows = [row for row in csv.reader(stream, delimiter="\t") if row and not row[0].startswith("#")]
        self.assertEqual(len(rows), 4)
        self.assertEqual({row[1] for row in rows}, {"lineage-22.2"})
        self.assertEqual(
            {row[0] for row in rows},
            {
                "device/huawei/angler",
                "vendor/huawei/angler",
                "kernel/huawei/angler",
                "packages/apps/PhhIms",
            },
        )

    def test_verifier_is_executable(self):
        verifier = ROOT / "verify.sh"
        self.assertTrue(verifier.is_file())
        self.assertTrue(verifier.stat().st_mode & stat.S_IXUSR)

    def test_publishable_files_contain_no_local_paths_or_private_keys(self):
        forbidden_suffixes = {".pk8", ".pem", ".jks", ".keystore"}
        for path in tracked_files():
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(path.suffix, forbidden_suffixes)
                if not path.is_file() or path.is_symlink():
                    continue
                try:
                    contents = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                self.assertNotIn(LOCAL_WORKSPACE_PREFIX, contents)
                self.assertNotIn(PRIVATE_KEY_MARKER, contents)


if __name__ == "__main__":
    unittest.main()
