import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from voxflow.assembler import (
    _ffmpeg_concat_entry,
    _normalized_target,
    _repaired_clip,
    _subtitle_filter,
    _text_safe_keyframe,
    _trim_srt,
    allocate_shot_durations,
)


class AssemblerTests(unittest.TestCase):
    def test_concat_entry_uses_forward_slashes_and_escapes_quotes(self):
        entry = _ffmpeg_concat_entry(Path("folder/it's-a-clip.mp4"))
        self.assertTrue(entry.startswith("file '"))
        self.assertNotIn("\\", entry.replace("'\\''", ""))
        self.assertIn("'\\''", entry)

    def test_timeline_covers_voice_duration(self):
        plan = {
            "beats": [
                {"id": 1, "narration": "短句", "shots": [{"id": "001"}]},
                {
                    "id": 2,
                    "narration": "这是一段明显更长的旁白内容",
                    "shots": [{"id": "002"}, {"id": "003"}],
                },
            ]
        }
        timeline = allocate_shot_durations(plan, 12.0)
        self.assertEqual(len(timeline), 3)
        self.assertEqual(round(timeline[-1]["start"] + timeline[-1]["duration"], 3), 12.0)
        self.assertGreater(timeline[1]["duration"], timeline[0]["duration"] / 2)

    def test_trim_srt_clamps_last_caption(self):
        with TemporaryDirectory() as temp:
            source = Path(temp) / "source.srt"
            target = Path(temp) / "target.srt"
            source.write_text(
                "1\n00:00:00,000 --> 00:00:02,000\nfirst\n\n"
                "2\n00:00:02,000 --> 00:00:05,000\nsecond\n\n"
                "3\n00:00:06,000 --> 00:00:07,000\nthird\n",
                encoding="utf-8",
            )
            _trim_srt(source, target, 3.5)
            result = target.read_text(encoding="utf-8")
            self.assertIn("00:00:02,000 --> 00:00:03,500", result)
            self.assertNotIn("third", result)

    def test_text_safe_mode_uses_keyframe_for_title_shots(self):
        settings = {"assembly": {"text_safe_mode": "keyframe"}}
        self.assertTrue(_text_safe_keyframe(settings, {"title": True}))
        self.assertFalse(_text_safe_keyframe(settings, {"title": False}))

    def test_subtitle_defaults_match_reference_demo(self):
        result = _subtitle_filter(Path("captions.srt"), "Microsoft YaHei")
        self.assertIn("FontSize=56", result)
        self.assertIn("MarginV=64", result)

    def test_repaired_clip_detected_only_when_present(self):
        with TemporaryDirectory() as temp:
            repair_dir = Path(temp) / "repaired"
            self.assertIsNone(_repaired_clip(repair_dir, "007"))
            repair_dir.mkdir()
            existing = repair_dir / "shot-007.mp4"
            existing.write_bytes(b"clip")
            self.assertEqual(_repaired_clip(repair_dir, "007"), existing)

    def test_normalized_target_distinguishes_repaired_and_keyframe(self):
        item = {"shot_id": "007"}
        self.assertEqual(
            _normalized_target(Path("n"), item, False, True), Path("n/shot-007-repaired.mp4")
        )
        self.assertEqual(
            _normalized_target(Path("n"), item, True, False), Path("n/shot-007-keyframe.mp4")
        )
        self.assertEqual(
            _normalized_target(Path("n"), item, False, False), Path("n/shot-007.mp4")
        )


if __name__ == "__main__":
    unittest.main()
