import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from voxflow.planner import create_plan, iter_shots, runninghub_prompt, split_sentences, title_from_text


class PlannerTests(unittest.TestCase):
    def test_split_sentences_keeps_chinese_punctuation(self):
        self.assertEqual(split_sentences("第一句。第二句！"), ["第一句。", "第二句！"])

    def test_title_stops_before_contrast_phrase(self):
        self.assertEqual(title_from_text("地铁线路图不是地图，而是视觉索引。"), "地铁线路图不是地图")

    def test_create_plan_has_prompts_and_varied_motion(self):
        with TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            source = tmp_path / "script.txt"
            source.write_text(
                "地图不是现实。设计师拉直线路，让复杂城市可以快速阅读。"
                "这不是欺骗，而是信息设计。",
                encoding="utf-8",
            )
            plan = create_plan("demo", source, tmp_path / "beats.json", target_beat_seconds=5)
            shots = [shot for _, shot in iter_shots(plan)]
            self.assertTrue(shots)
            self.assertTrue(all("paper collage" in shot["image_prompt"].lower() for shot in shots))
            self.assertTrue(
                all(
                    shot["video_prompt"].startswith(
                        "For the target video, at 0.00 seconds into the target video"
                    )
                    for shot in shots
                )
            )
            self.assertTrue(
                all("integrated_multimodal_description" in shot["video_prompt"] for shot in shots)
            )
            self.assertTrue(all("5.00-second" in shot["video_prompt"] for shot in shots))
            self.assertTrue(all("subject_definitions" not in shot["video_prompt"] for shot in shots))
            self.assertGreater(len({shot["camera_move"] for shot in shots}), 1)

    def test_runninghub_prompt_uses_h3_i2va_field_order_and_text_guard(self):
        prompt = runninghub_prompt(
            {
                "title": True,
                "camera_move": "push_in",
                "element_motion": "paper arrows slide into place",
            }
        )
        fields = (
            "integrated_multimodal_description:",
            "overall_soundscape:",
            "non_diegetic_music:",
        )
        positions = [prompt.index(field) for field in fields]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("small amplitude at slow speed", prompt)
        self.assertIn("pixel-stable and readable", prompt)
        self.assertIn("post-production", prompt)


if __name__ == "__main__":
    unittest.main()
