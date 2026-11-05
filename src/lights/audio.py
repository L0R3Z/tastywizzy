"""Audio-reactive modes: listens to what the PC plays (WASAPI loopback) and alters the bulbs' state."""
import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass

import numpy as np

from . import color

log = logging.getLogger(__name__)

MODES = ("off", "level", "beat", "color")
SILENCE_RMS = 1e-3  # below this, the block counts as silence
ACTIVE_HOLD_S = 2.0  # with no sound for this long, the bulbs go back to the plain screen sync
RANGE_ADAPT_DB_S = 2.0  # how fast the loudness range follows a new song
MIN_RANGE_DB = 3.0  # heavily limited tracks barely move: keep their small swings visible
LEVEL_RELEASE_S = 0.15
BEAT_DECAY_S = 0.3  # the bulbs' own fade softens anything much shorter
BEAT_HISTORY = 140  # about 3 s of audio blocks
BEAT_MIN_HISTORY = 10
BEAT_DEVIATIONS = 1.5
BEAT_MIN_RISE_DB = 1.5
BEAT_MIN_GAP_S = 0.12
BASS_MIN_SHARE = 0.02  # ignores rises in a band that is nearly empty
HUE_TAU_S = 0.25
BASS_HZ = 150
HUE_LOW_HZ, HUE_HIGH_HZ = 80.0, 6000.0
HUE_MAX = 0.75  # low sounds are red, high sounds go up to blue-violet
DEVICE_CHECK_S = 5.0
RETRY_S = 5.0
BLOCK_FRAMES = 1024


@dataclass(frozen=True)
class AudioState:
    active: bool = False  # sound was heard recently
    level: float = 0.0  # volume, 0-1, adapted to the recent loudness
    beat: float = 0.0  # 1 on a bass hit, then falls back to 0
    hue: float = 0.0  # 0-HUE_MAX, follows the pitch of the sound


def _fade(dt, tau):
    return math.exp(-max(dt, 0.0) / tau)


class AudioAnalyzer:
    """Turns audio blocks into an AudioState. feed() and state() may run on different threads."""

    def __init__(self):
        self._lock = threading.Lock()
        self._peak_db = self._floor_db = None  # loudness range of the current song
        self._level = self._beat = self._hue = 0.0
        self._previous = np.zeros(0, dtype=np.float32)
        self._bass_db = None
        self._rises = deque(maxlen=BEAT_HISTORY)
        self._last_feed = self._last_loud = self._last_beat = -math.inf

    def _is_hit(self, bass_db, audible, now):
        """A bass hit is a rise that stands out from this song's own recent rises, whatever its loudness."""
        rise = max(0.0, bass_db - self._bass_db) if self._bass_db is not None else 0.0
        self._bass_db = bass_db
        recent = np.array(self._rises) if len(self._rises) >= BEAT_MIN_HISTORY else None
        self._rises.append(rise)
        if recent is None or not audible or now - self._last_beat < BEAT_MIN_GAP_S:
            return False
        return rise > max(BEAT_MIN_RISE_DB, recent.mean() + BEAT_DEVIATIONS * recent.std())

    def _update_level(self, rms, dt):
        """Level = position within the song's recent range, so limited tracks still move the lights."""
        db = 20 * math.log10(rms)
        if self._peak_db is None:
            self._peak_db = self._floor_db = db
        self._peak_db = max(db, self._peak_db - RANGE_ADAPT_DB_S * dt)
        self._floor_db = min(db, self._floor_db + RANGE_ADAPT_DB_S * dt)
        span = max(self._peak_db - self._floor_db, MIN_RANGE_DB)
        return max(0.0, 1 - (self._peak_db - db) / span)

    def feed(self, samples, rate, now):
        """samples: mono floats between -1 and 1."""
        rms = float(np.sqrt(np.mean(samples ** 2))) if len(samples) else 0.0
        loud = rms >= SILENCE_RMS
        window = np.concatenate((self._previous, samples))  # longer window: steadier low frequencies
        self._previous = samples
        with self._lock:
            dt = now - self._last_feed if self._last_feed != -math.inf else 0.0
            self._last_feed = now
            level = self._update_level(rms, dt) if loud else 0.0
            self._level = max(level, self._level * _fade(dt, LEVEL_RELEASE_S))
            self._beat *= _fade(dt, BEAT_DECAY_S)
            if not loud:
                self._bass_db = None
                return
            self._last_loud = now
            spectrum = np.abs(np.fft.rfft(window * np.hanning(len(window)))) ** 2
            freqs = np.fft.rfftfreq(len(window), 1 / rate)
            bass = float(spectrum[freqs < BASS_HZ].sum())
            total = max(float(spectrum.sum()), 1e-12)
            bass_db = 10 * math.log10(max(bass, 1e-12))
            if self._is_hit(bass_db, bass / total >= BASS_MIN_SHARE, now):
                self._beat, self._last_beat = 1.0, now
            centroid = float((freqs * spectrum).sum()) / total
            position = math.log(max(centroid, HUE_LOW_HZ) / HUE_LOW_HZ) / math.log(HUE_HIGH_HZ / HUE_LOW_HZ)
            self._hue += (min(1.0, position) * HUE_MAX - self._hue) * (1 - _fade(dt, HUE_TAU_S))

    def state(self, now):
        with self._lock:
            idle = now - self._last_feed  # Windows delivers no audio at all when nothing plays
            return AudioState(now - self._last_loud < ACTIVE_HOLD_S,
                              self._level * _fade(idle, LEVEL_RELEASE_S),
                              self._beat * _fade(idle, BEAT_DECAY_S),
                              self._hue)


def apply_effect(cfg, rgb, dimming, white, audio):
    """Screen-based state -> state to send, according to audio_mode. Silence leaves it unchanged.

    The sound lowers the resting brightness and rises towards dimming_max, so that a dark
    screen still leaves room for a visible reaction.
    """
    mode = cfg["audio_mode"]
    if mode == "off" or not audio.active:
        return rgb, dimming, white
    strength = cfg["audio_intensity"] / 100
    cap = cfg["dimming_max"]
    if mode == "color":
        rgb, dimming, white = color.hs_to_rgb(audio.hue, 1.0, cfg["color_gamma"]), cap, 0
    drive = audio.beat if mode == "beat" else audio.level
    rest = max(10, dimming * (1 - strength))
    return rgb, round(rest + max(0, cap - rest) * strength * drive), white


class AudioListener:
    """Captures the default output device in the background, only while enabled."""

    def __init__(self):
        self.analyzer = AudioAnalyzer()
        self._enabled = threading.Event()
        self._closed = threading.Event()
        self._wake = threading.Event()
        self._thread = None

    def set_enabled(self, enabled):
        if enabled:
            self._enabled.set()
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()
        else:
            self._enabled.clear()
        self._wake.set()

    def close(self):
        self._closed.set()
        self._wake.set()
        if self._thread:
            self._thread.join(2)

    def state(self):
        return self.analyzer.state(time.monotonic()) if self._enabled.is_set() else AudioState()

    def _wait(self, seconds):
        self._wake.wait(seconds)
        self._wake.clear()

    def _run(self):
        try:
            import pyaudiowpatch
        except ImportError:
            log.warning("Audio modes unavailable: PyAudioWPatch is not installed.")
            return
        while not self._closed.is_set():
            if not self._enabled.is_set():
                self._wait(1.0)
                continue
            try:
                self._capture(pyaudiowpatch)
            except Exception as e:  # device unplugged, driver error...
                log.warning("Audio capture unavailable, retrying: %s", e)
                self._wait(RETRY_S)

    def _capture(self, pa_module):
        pa = pa_module.PyAudio()
        stream = None
        try:
            device = pa.get_default_wasapi_loopback()
            channels, rate = device["maxInputChannels"], int(device["defaultSampleRate"])

            def callback(data, _frames, _time, _status):
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768
                self.analyzer.feed(samples.reshape(-1, channels).mean(axis=1), rate, time.monotonic())
                return None, pa_module.paContinue

            stream = pa.open(format=pa_module.paInt16, channels=channels, rate=rate, input=True,
                             input_device_index=device["index"], frames_per_buffer=BLOCK_FRAMES,
                             stream_callback=callback)
            log.info("Audio capture: %s", device["name"])
            while self._enabled.is_set() and not self._closed.is_set():
                self._wait(DEVICE_CHECK_S)
                if pa.get_default_wasapi_loopback()["name"] != device["name"]:  # output switched
                    log.info("Audio output changed.")
                    return
        finally:
            if stream:
                stream.close()
            pa.terminate()
