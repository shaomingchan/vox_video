import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from voxflow import runninghub
from voxflow.runninghub import build_payload, effective_concurrency
from voxflow.util import read_json, write_json


class RunningHubTests(unittest.TestCase):
    def test_payload_uses_three_reference_nodes_and_exact_portrait_enum(self):
        payload = build_payload(
            {"instance_type": "default", "use_personal_queue": False},
            "openapi/test.png",
            "prompt",
            "9:16",
            123,
        )
        nodes = payload["nodeInfoList"]
        images = [item for item in nodes if item["fieldName"] == "image"]
        aspects = [item for item in nodes if item["fieldName"] == "aspect_ratio"]
        self.assertEqual([item["nodeId"] for item in images], ["97", "101", "132"])
        self.assertTrue(
            all(item["fieldValue"] == "9:16 (Portrait Widescreen)" for item in aspects)
        )

    def test_enterprise_profile_defaults_to_plus_instance(self):
        payload = build_payload(
            {
                "api_profile": "enterprise",
                "instance_type": "default",
                "enterprise_instance_type": "plus",
                "use_personal_queue": False,
            },
            "openapi/test.png",
            "prompt",
            "9:16",
            123,
        )
        self.assertEqual(payload["instanceType"], "plus")

    def test_enterprise_profile_allows_one_hundred_concurrent_jobs(self):
        self.assertEqual(
            effective_concurrency(
                {
                    "api_profile": "enterprise",
                    "concurrency": 3,
                    "enterprise_concurrency": 100,
                }
            ),
            100,
        )
        self.assertEqual(effective_concurrency({"api_profile": "member", "concurrency": 100}), 3)

    def test_lite_profile_omits_instance_type_for_scheduler_selection(self):
        payload = build_payload(
            {"instance_type": "lite", "use_personal_queue": False},
            "openapi/test.png",
            "prompt",
            "9:16",
            123,
        )
        self.assertNotIn("instanceType", payload)

    def test_limit_submits_only_selected_shots_and_retains_manifest(self):
        with TemporaryDirectory() as temp:
            project = Path(temp)
            image_dir = project / "images"
            image_dir.mkdir()
            shots = []
            for index in range(1, 4):
                image = image_dir / f"shot-{index:03d}.png"
                image.write_bytes(b"image" + bytes([index]))
                shots.append(
                    {
                        "id": f"{index:03d}",
                        "keyframe": str(image),
                        "video_prompt": f"prompt {index}",
                    }
                )
            write_json(
                project / "beats.json",
                {
                    "aspect": "16:9",
                    "beats": [{"id": 1, "narration": "test", "shots": shots}],
                },
            )
            write_json(
                project / "video_manifest.json",
                {"items": [{"shot_id": "099", "path": "retained.mp4"}]},
            )
            settings = {
                "runninghub": {
                    "workflow_id": "workflow",
                    "api_profile": "member",
                    "instance_type": "default",
                    "concurrency": 3,
                }
            }
            submitted: list[str] = []

            def generate(shot, aspect, output_dir, key, config):
                submitted.append(shot["id"])
                target = output_dir / f"shot-{shot['id']}.mp4"
                target.write_bytes(b"video-data")
                return {
                    "shot_id": shot["id"],
                    "path": str(target),
                    "task_id": f"task-{shot['id']}",
                    "sha256": "hash",
                    "usage": {},
                }

            with mock.patch.object(runninghub, "get_runninghub_key", return_value="secret"), mock.patch.object(
                runninghub, "_generate_one", side_effect=generate
            ):
                result = runninghub._generate_videos_unlocked(settings, project, limit=2)

            self.assertEqual(submitted, ["001", "002"])
            self.assertEqual([item["shot_id"] for item in result], ["001", "002"])
            manifest = read_json(project / "video_manifest.json")
            self.assertEqual(
                [item["shot_id"] for item in manifest["items"]], ["001", "002", "099"]
            )

    def test_large_paid_batch_requires_explicit_all(self):
        with TemporaryDirectory() as temp:
            project = Path(temp)
            image_dir = project / "images"
            image_dir.mkdir()
            shots = []
            for index in range(1, 4):
                image = image_dir / f"shot-{index:03d}.png"
                image.write_bytes(b"image")
                shots.append(
                    {
                        "id": f"{index:03d}",
                        "keyframe": str(image),
                        "video_prompt": f"prompt {index}",
                    }
                )
            write_json(
                project / "beats.json",
                {
                    "aspect": "16:9",
                    "beats": [{"id": 1, "narration": "test", "shots": shots}],
                },
            )
            settings = {
                "runninghub": {
                    "workflow_id": "workflow",
                    "max_unconfirmed_batch": 2,
                }
            }
            with mock.patch.object(runninghub, "get_runninghub_key", return_value="secret"):
                with self.assertRaisesRegex(RuntimeError, "paid-batch safety stop"):
                    runninghub._generate_videos_unlocked(settings, project)


if __name__ == "__main__":
    unittest.main()
