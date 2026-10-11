#!/usr/bin/env python3

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
APPLY_SCRIPT = REPOSITORY_ROOT / "apply.sh"


def run(*args: str, cwd: Path | None = None, check: bool = True):
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


class ApplyScriptTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(APPLY_SCRIPT.is_file(), "apply.sh must exist")
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root = Path(self.temporary_directory.name)
        self.source = root / "source"
        self.kit = root / "kit"
        self.project = self.source / "platform/foo"
        patch_directory = self.kit / "patches/platform_foo"
        patch_directory.mkdir(parents=True)
        self.project.mkdir(parents=True)
        (self.source / ".repo").mkdir()
        build_directory = self.source / "build/make/core"
        build_directory.mkdir(parents=True)
        (build_directory / "build_id.mk").write_text(
            "BUILD_ID=BP1A.250505.005\n", encoding="utf-8"
        )

        shutil.copy2(APPLY_SCRIPT, self.kit / "apply.sh")
        run("git", "init", "-b", "lineage-22.2", cwd=self.project)
        run("git", "config", "user.name", "Patch Kit Test", cwd=self.project)
        run("git", "config", "user.email", "patch-kit@example.invalid", cwd=self.project)
        (self.project / "value.txt").write_text("before\n", encoding="utf-8")
        run("git", "add", "value.txt", cwd=self.project)
        run("git", "commit", "-m", "baseline", cwd=self.project)
        self.baseline = run("git", "rev-parse", "HEAD", cwd=self.project).stdout.strip()

        (self.project / "value.txt").write_text("after\n", encoding="utf-8")
        run("git", "add", "value.txt", cwd=self.project)
        run("git", "commit", "-m", "test: apply fixture", cwd=self.project)
        self.result_tree = run(
            "git", "rev-parse", "HEAD^{tree}", cwd=self.project
        ).stdout.strip()
        patch = run("git", "format-patch", "-1", "--stdout", cwd=self.project).stdout
        (patch_directory / "0001-test-apply-fixture.patch").write_text(
            patch, encoding="utf-8"
        )
        run("git", "reset", "--hard", self.baseline, cwd=self.project)

        (self.kit / "projects.tsv").write_text(
            "# path\tbaseline\tresult_tree\tpatch_dir\n"
            f"platform/foo\t{self.baseline}\t{self.result_tree}\t"
            "patches/platform_foo\n",
            encoding="utf-8",
        )

    def apply(self, *extra: str, check: bool = True):
        return run(
            str(self.kit / "apply.sh"),
            "--source",
            str(self.source),
            *extra,
            check=check,
        )

    def test_check_validates_without_modifying_source(self):
        result = self.apply("--check")
        self.assertIn("applicable: platform/foo", result.stdout)
        self.assertEqual((self.project / "value.txt").read_text(), "before\n")
        self.assertEqual(
            run("git", "rev-parse", "HEAD", cwd=self.project).stdout.strip(),
            self.baseline,
        )

    def test_apply_is_idempotent(self):
        first = self.apply()
        self.assertIn("applied: platform/foo", first.stdout)
        self.assertEqual((self.project / "value.txt").read_text(), "after\n")
        self.assertEqual(
            run("git", "rev-parse", "HEAD^{tree}", cwd=self.project).stdout.strip(),
            self.result_tree,
        )
        second = self.apply()
        self.assertIn("already applied: platform/foo", second.stdout)

    def test_dirty_project_is_refused_even_if_patch_was_applied(self):
        self.apply()
        (self.project / "local-change.txt").write_text("do not overwrite\n")
        result = self.apply(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dirty repository: platform/foo", result.stdout)
        self.assertTrue((self.project / "local-change.txt").exists())

    def test_unexpected_baseline_is_refused(self):
        (self.project / "unrelated.txt").write_text("different baseline\n")
        run("git", "add", "unrelated.txt", cwd=self.project)
        run("git", "commit", "-m", "unexpected", cwd=self.project)
        result = self.apply(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("baseline mismatch: platform/foo", result.stdout)

    def test_ap4a_build_id_is_refused(self):
        build_id = self.source / "build/make/core/build_id.mk"
        build_id.write_text("BUILD_ID=AP4A.250205.002\n", encoding="utf-8")
        result = self.apply(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported BUILD_ID", result.stdout)


if __name__ == "__main__":
    unittest.main()
