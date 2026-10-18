"""Tests des parties pures. Lancer : python -m unittest discover tests"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np  # noqa: E402

from lights import app, color, config, hotkey, wiz  # noqa: E402
from lights.smoothing import Smoother  # noqa: E402


class ColorTest(unittest.TestCase):
    def test_crop_black_bars(self):
        img = np.zeros((10, 10, 3), np.uint8)
        img[2:8, :] = 200
        self.assertEqual(color.crop_black_bars(img).shape, (6, 10, 3))

    def test_crop_all_black_keeps_image(self):
        img = np.zeros((4, 4, 3), np.uint8)
        self.assertEqual(color.crop_black_bars(img).shape, img.shape)

    def test_analyze_pure_red(self):
        img = np.zeros((4, 4, 3), np.uint8)
        img[..., 0] = 255
        h, s, c, v = color.analyze(img)
        self.assertAlmostEqual(h, 0.0, places=5)
        self.assertAlmostEqual(s, 1.0)
        self.assertAlmostEqual(c, 1.0)

    def test_analyze_grey_has_no_hue(self):
        h, s, c, _ = color.analyze(np.full((4, 4, 3), 128, np.uint8))
        self.assertIsNone(h)
        self.assertEqual(c, 0.0)

    def test_neutral_factor_range(self):
        self.assertEqual(color.neutral_factor(0.0, 0.1, 0.2), 0.0)
        self.assertEqual(color.neutral_factor(0.5, 0.1, 0.2), 1.0)
        self.assertAlmostEqual(color.neutral_factor(0.15, 0.1, 0.2), 0.5)


class SmootherTest(unittest.TestCase):
    def test_hue_takes_shortest_path(self):
        sm = Smoother(1.0)
        sm.update(0.95, 1, 1, 1, 0)
        h, *_ = sm.update(0.05, 1, 1, 1, 1.0)
        self.assertTrue(h > 0.95 or h < 0.05)

    def test_zero_tau_jumps(self):
        sm = Smoother(0)
        sm.update(0.2, 1, 1, 1, 0)
        self.assertAlmostEqual(sm.update(0.4, 1, 1, 1, 0.01)[0], 0.4)


class ComputeStateTest(unittest.TestCase):
    def cfg(self, **kw):
        return {**config.DEFAULTS, **kw}

    def test_dimming_clamped(self):
        cfg = self.cfg(dimming_max=250, brightness_scales={"night": 3, "day": 1})
        _, dimming, _ = app.compute_state(cfg, 0.0, 1.0, 1.0, 1.0)
        self.assertEqual(dimming, app.DIMMING_MAX)

    def test_neutral_rgb_mode_reaches_dimming_max(self):
        cfg = self.cfg(use_white_led=False, brightness_scales={"night": 1, "day": 1})
        rgb, dimming, white = app.compute_state(cfg, 0.0, 0.0, 0.0, 1.0)
        self.assertEqual(rgb, tuple(cfg["neutral_rgb"]))
        self.assertEqual((dimming, white), (cfg["dimming_max"], 0))

    def test_white_led_cap_applies_with_white_led(self):
        cfg = self.cfg(use_white_led=True, brightness_scales={"night": 1, "day": 1})
        rgb, dimming, white = app.compute_state(cfg, 0.0, 0.0, 0.0, 1.0)
        self.assertEqual((rgb, dimming, white), ((0, 0, 0), cfg["dimming_max_white"], 255))


class ConfigTest(unittest.TestCase):
    def test_defaults_valid(self):
        config.validate(dict(config.DEFAULTS))

    def test_rejects_zero_rate(self):
        with self.assertRaises(ValueError):
            config.validate({**config.DEFAULTS, "send_hz": 0})

    def test_rejects_unknown_pause_mode(self):
        with self.assertRaises(ValueError):
            config.validate({**config.DEFAULTS, "pause_mode": "stop"})

    def test_save_bulbs_keeps_formatting(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            p.write_text('{\n  "tau": 0.1,\n  "bulbs": {"a": "1.2.3.4"}\n}\n', encoding="utf-8")
            config.save_bulbs(p, {"a": {"ip": "1.2.3.5", "mac": "aa"}})
            text = p.read_text(encoding="utf-8")
            self.assertTrue(text.startswith('{\n  "tau": 0.1,\n'))
            self.assertEqual(json.loads(text)["bulbs"]["a"]["ip"], "1.2.3.5")


class HotkeyTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(hotkey.parse("ctrl+alt+l"), (0x0003, ord("L")))
        self.assertEqual(hotkey.parse("f24")[1], 0x87)

    def test_parse_rejects_bad_keys(self):
        for combo in ("f0", "f25", "ctl+x", "ctrl+space"):
            with self.assertRaises(ValueError):
                hotkey.parse(combo)

    def test_bad_combo_reports_error(self):
        self.assertIsNotNone(hotkey.PauseHotkey("ctl+x").error)


class WizTest(unittest.TestCase):
    def tearDown(self):
        if hasattr(self, "w"):
            self.w.sock.close()

    def test_restore_rgb_state(self):
        p = wiz._restore_params({"state": True, "r": 1, "g": 2, "b": 3, "c": 0, "w": 4, "dimming": 50})
        self.assertEqual(p, {"state": True, "dimming": 50, "r": 1, "g": 2, "b": 3, "c": 0, "w": 4})

    def test_restore_scene_keeps_speed(self):
        p = wiz._restore_params({"state": True, "sceneId": 4, "speed": 80, "r": 9, "dimming": 30})
        self.assertEqual(p, {"state": True, "dimming": 30, "sceneId": 4, "speed": 80})

    def test_reconfigure_keeps_removed_bulb_for_restore(self):
        w = self.w = wiz.Wiz({"a": "1.1.1.1", "b": "1.1.1.2"})
        w.bulbs[1].saved = {"state": True}
        w.reconfigure({"a": "1.1.1.1"}, 30)
        self.assertEqual([b.name for b in w.retired], ["b"])

    def test_reconfigure_new_ip_keeps_saved_state(self):
        w = self.w = wiz.Wiz({"a": {"ip": "1.1.1.1", "mac": "aa"}})
        w.bulbs[0].saved = {"state": True, "temp": 2700}
        w.reconfigure({"a": "1.1.1.9"}, 30)
        self.assertEqual((w.bulbs[0].ip, w.bulbs[0].mac), ("1.1.1.9", "aa"))
        self.assertEqual(w.bulbs[0].saved, {"state": True, "temp": 2700})
        self.assertEqual(w.retired, [])


if __name__ == "__main__":
    unittest.main()
