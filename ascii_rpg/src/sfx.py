""" synthesized retro SFX (no audio files): tiny numpy-built blips.

Safe everywhere: lazy mixer init, master toggle, and total silence
(no crash) on headless machines or when disabled.
"""
from __future__ import annotations

_enabled = True
_sounds: dict[str, object] = {}
_ready = False


def set_enabled(on: bool) -> None:
    global _enabled
    _enabled = bool(on)


def _build() -> None:
    global _ready
    if _ready:
        return
    try:
        import pygame
        import numpy as _np
    except Exception:
        return
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
    except Exception:
        return

    rate = 22050

    def tone(f0: float, f1: float, dur: float, vol: float = 0.35,
             square: bool = False) -> object:
        n = max(1, int(rate * dur))
        xs = _np.linspace(0.0, 1.0, n)
        freq = f0 + (f1 - f0) * xs
        phase = _np.cumsum(freq / rate * 2 * _np.pi)
        wave = _np.sin(phase)
        if square:
            wave = _np.sign(wave) * 0.7
        env = _np.exp(-4.0 * xs)
        data = (wave * env * vol * 32767).astype(_np.int16)
        return pygame.mixer.Sound(buffer=data.tobytes())

    def seq(notes: list[tuple[float, float]], vol: float = 0.35) -> object:
        import numpy as _np2
        parts = []
        n = 0
        segs = []
        for freq, dur in notes:
            m = max(1, int(rate * dur))
            xs = _np2.linspace(0.0, 1.0, m)
            segs.append((_np2.sin(2 * _np2.pi * freq * xs) * _np2.exp(-4 * xs) * vol))
            n += m
        data = (_np2.concatenate(segs) * 32767).astype(_np2.int16)
        import pygame as _pg
        return _pg.mixer.Sound(buffer=data.tobytes())

    try:
        _sounds.update({
            "hit": tone(220, 110, 0.09, square=True),
            "hurt": tone(150, 70, 0.14, square=True),
            "coin": seq([(880, 0.06), (1320, 0.09)]),
            "slay": tone(160, 60, 0.16, square=True),
            "level": seq([(523, 0.09), (659, 0.09), (784, 0.14)]),
            "quest": seq([(659, 0.1), (880, 0.16)]),
            "death": tone(220, 55, 0.5),
            "heal": tone(440, 660, 0.15),
            "spell": tone(300, 900, 0.2),
            "ui": tone(600, 600, 0.035, vol=0.2),
        })
        _ready = True
    except Exception:
        _ready = False


def play(name: str) -> None:
    """Fire-and-forget blip. Never raises, never blocks."""
    if not _enabled:
        return
    try:
        _build()
        if not _ready:
            return
        snd = _sounds.get(name)
        if snd is not None:
            snd.play()
    except Exception:
        pass
