from __future__ import annotations

import unittest
from pathlib import Path


class LiveGatedPackTest(unittest.TestCase):
    def test_live_pack_covers_live1_to_live5_and_blocks_auto_live(self) -> None:
        text = Path("docs/live-demo-gated-pack.md").read_text(encoding="utf-8")

        for marker in ["LIVE1", "LIVE2", "LIVE3", "LIVE4", "LIVE5"]:
            self.assertIn(marker, text)
        self.assertIn("NO_GO_FOR_REAL_LIVE", text)
        self.assertIn("READY_TO_USE_FOR_DEMO_PAPER", text)
        self.assertIn("Tidak ada tombol market order", text)
        self.assertIn("withdrawal disabled", text)
        self.assertIn("owner review", text)


if __name__ == "__main__":
    unittest.main()
