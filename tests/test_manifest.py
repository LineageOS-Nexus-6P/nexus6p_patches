#!/usr/bin/env python3

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "local_manifests/angler.xml.template"


class ManifestTemplateTest(unittest.TestCase):
    def test_manifest_contains_only_required_overrides(self):
        self.assertTrue(TEMPLATE.is_file())
        template = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("@NEXUS6P_ORG@", template)
        self.assertNotIn("LineageOS-UL", template)
        self.assertNotIn("lineage-priv", template)
        self.assertNotIn("AP4A", template)

        root = ET.fromstring(template.replace("@NEXUS6P_ORG@", "ExampleOrg"))
        projects = {project.attrib["path"]: project for project in root.findall("project")}
        expected = {
            "device/huawei/angler": "android_device_huawei_angler",
            "vendor/huawei/angler": "android_vendor_huawei_angler",
            "kernel/huawei/angler": "android_kernel_huawei_angler",
            "packages/apps/PhhIms": "android_packages_apps_PhhIms",
            "hardware/qcom/display": "davigamer987/hardware_qcom_display",
            "hardware/qcom-caf/msm8994/media": "davigamer987/hardware_qcom_media",
        }
        self.assertEqual(set(projects), set(expected))
        for path, name in expected.items():
            with self.subTest(path=path):
                self.assertEqual(projects[path].attrib["name"], name)

        for path in (
            "device/huawei/angler",
            "vendor/huawei/angler",
            "kernel/huawei/angler",
            "packages/apps/PhhIms",
        ):
            self.assertEqual(
                projects[path].attrib.get("upstream"), "refs/heads/lineage-22.2"
            )

        expected_revisions = {
            "device/huawei/angler": "refs/heads/lineage-22.2",
            "vendor/huawei/angler": "refs/heads/lineage-22.2",
            "kernel/huawei/angler": "refs/heads/lineage-22.2",
            "packages/apps/PhhIms": "refs/heads/lineage-22.2",
            "hardware/qcom/display": "refs/heads/lineage-23.0-caf-msm8994",
            "hardware/qcom-caf/msm8994/media":
                "refs/heads/lineage-23.0-caf-msm8994",
        }
        for path, revision in expected_revisions.items():
            with self.subTest(path=path):
                self.assertEqual(projects[path].attrib["revision"], revision)

        removed = {entry.attrib["path"] for entry in root.findall("remove-project")}
        self.assertEqual(removed, {"hardware/qcom/display"})


if __name__ == "__main__":
    unittest.main()
