from __future__ import annotations

import asyncio
import importlib.util
import os
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

from voxflow import image_adapter


WHITEBOARD_ROOT = Path(
    os.environ.get(
        "WHITEBOARD_ROOT",
        Path(__file__).resolve().parents[2] / "whiteboard",
    )
)
WHITEBOARD_IMAGE_SCRIPT = (
    WHITEBOARD_ROOT
    / "skills/whiteboard-video-workflow/scripts/generate-image.py"
)


def load_whiteboard_image_module():
    spec = importlib.util.spec_from_file_location("test_whiteboard_image", WHITEBOARD_IMAGE_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ImageSafetyTests(unittest.TestCase):
    @unittest.skipUnless(
        WHITEBOARD_IMAGE_SCRIPT.exists(), "external whiteboard image adapter is unavailable"
    )
    def test_batch_does_not_retry_fatal_errors(self):
        module = load_whiteboard_image_module()
        calls = 0

        async def fail_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            raise module.FatalError("HTTP 402: insufficient balance")

        with mock.patch.object(module, "generate_single", fail_once):
            result = asyncio.run(
                module.run_batch(
                    [{"prompt": "x", "aspectRatio": "16:9", "outputDir": ".", "index": 0, "total": 1}],
                    1,
                )
            )

        self.assertEqual(calls, 1)
        self.assertFalse(result[0]["retryable"])

    def test_windows_project_lock_rejects_second_runner(self):
        entered = threading.Event()
        release = threading.Event()

        async def hold_generation(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(timeout=5))
            return []

        settings = SimpleNamespace()
        with TemporaryDirectory() as temp:
            project = Path(temp)
            with mock.patch.object(image_adapter, "generate_images", hold_generation):
                first = threading.Thread(
                    target=image_adapter.generate_images_sync,
                    args=(settings, project),
                    daemon=True,
                )
                first.start()
                self.assertTrue(entered.wait(timeout=5))

                try:
                    with self.assertRaisesRegex(RuntimeError, "already running"):
                        image_adapter.generate_images_sync(settings, project)
                finally:
                    release.set()
                    first.join(timeout=5)

            self.assertFalse(first.is_alive())


if __name__ == "__main__":
    unittest.main()
