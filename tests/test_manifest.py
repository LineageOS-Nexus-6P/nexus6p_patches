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
            "device/huawei/angler": "976572f842d0ffa06776ee08948cd22cbee370bc",
            "vendor/huawei/angler": "2256f968e072c2388286fd5e589d48513f202547",
            "kernel/huawei/angler": "f34f4533ece113b5d01e44585902c81e105e3b22",
            "packages/apps/PhhIms": "3909c4517022d3632c459b618101d13c8c73e966",
            "hardware/qcom/display": "547dcd0bbe974a3f7540f134de592e6687674bec",
            "hardware/qcom-caf/msm8994/media":
                "e76c745c520ec3d36bd8b20ba019d331927db95a",
        }
        for path, revision in expected_revisions.items():
            with self.subTest(path=path):
                self.assertEqual(projects[path].attrib["revision"], revision)

        removed = {entry.attrib["path"] for entry in root.findall("remove-project")}
        self.assertEqual(removed, {"hardware/qcom/display"})


if __name__ == "__main__":
    unittest.main()
