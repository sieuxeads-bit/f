from __future__ import annotations

import os
import types
from pathlib import Path

import numpy as np


BASE_DIR = Path(__file__).resolve().parent
QUALITY_LAUNCHER = BASE_DIR / "quality_launcher.py"

# Build the full Quality/Profile UI but take over the final mainloop. The clean
# renderer keeps expressive text/prosody controls, synthesizes one SRT cue per
# pass, uses the FP32 model, and applies a very light anti-static mastering pass
# to suppress short high-frequency bursts without pitch/time manipulation.
source = QUALITY_LAUNCHER.read_text(encoding="utf-8")
marker = "\napp.mainloop()"
if marker not in source:
    raise RuntimeError("quality_launcher.py layout changed: app.mainloop() not found")
source = source.rsplit(marker, 1)[0] + "\n"
ns: dict[str, object] = {
    "__file__": str(QUALITY_LAUNCHER),
    "__name__": "_kokoro_quality_embedded",
    "__package__": None,
}
exec(compile(source, str(QUALITY_LAUNCHER), "exec"), ns)

app = ns["app"]
quality_combo = ns["quality_combo"]
context_combo = ns["context_combo"]
QUALITY_BALANCED = ns["QUALITY_BALANCED"]

MODEL_DIR = Path(os.environ.get("KOKORO_MODEL_DIR", BASE_DIR / "models"))
FULL_PRECISION_MODEL = Path(
    os.environ.get("KOKORO_CLEAN_MODEL", str(MODEL_DIR / "kokoro-v1.0.onnx"))
)

CLEAN_MODE = "Clean Emotional FP32 + Anti-rè (khuyên dùng)"
FAST_MODE = "Fast Emotional FP16"

quality_combo["values"] = [CLEAN_MODE, FAST_MODE, QUALITY_BALANCED]
context_combo["values"] = [1]
app.quality_mode_var.set(CLEAN_MODE)
app.context_cues_var.set(1)

# Snapshot the selected mode on the Tk/main thread before the worker starts.
_render_mode = CLEAN_MODE
_original_start_generate = app.start_generate
_original_studio_finish = ns["studio_finish"]


def _clean_lowpass(audio: np.ndarray, sr: int, cutoff: float = 7600.0) -> np.ndarray:
    """Linear-phase FIR low-pass for Kokoro's occasional high-band static.

    At 24 kHz this keeps normal speech presence while strongly attenuating the
    8-12 kHz region where the short crackle/static bursts are most obvious.
    The symmetric FIR does not shift pitch, stretch time, or move scene timing.
    """
    data = np.asarray(audio, dtype=np.float32).reshape(-1)
    if data.size < 64 or sr <= 0:
        return data.copy()
    nyquist = sr * 0.5
    cutoff = min(float(cutoff), nyquist * 0.82)
    if cutoff <= 0:
        return data.copy()

    taps = 63
    n = np.arange(taps, dtype=np.float64) - (taps - 1) / 2.0
    fc = cutoff / sr
    kernel = 2.0 * fc * np.sinc(2.0 * fc * n)
    kernel *= np.hamming(taps)
    kernel /= np.sum(kernel)
    return np.convolve(data, kernel.astype(np.float32), mode="same").astype(np.float32)


def _safe_normalize(audio: np.ndarray) -> np.ndarray:
    """Gentle level matching that does not amplify model noise aggressively."""
    data = np.asarray(audio, dtype=np.float32).reshape(-1).copy()
    if data.size == 0:
        return data

    rms = float(np.sqrt(np.mean(data.astype(np.float64) ** 2)))
    if rms > 1e-7:
        # About -20 dBFS RMS. Never boost more than +1.9 dB. The previous
        # normalizer allowed up to 3x gain, which made quiet Kokoro artifacts
        # much easier to hear on some scenes.
        target_rms = 10.0 ** (-20.0 / 20.0)
        gain = min(target_rms / rms, 1.25)
        data *= np.float32(gain)

    peak = float(np.max(np.abs(data)))
    if peak > 0.90:
        data *= np.float32(0.90 / peak)
    return data


def clean_studio_finish(samples, sr: int, normalize: bool, natural_edges: bool):
    global _render_mode
    if _render_mode != CLEAN_MODE:
        return _original_studio_finish(samples, sr, normalize, natural_edges)

    audio = np.asarray(samples, dtype=np.float32).reshape(-1).copy()
    if audio.size == 0:
        return audio

    # Remove scene DC, then suppress the narrow high-band static before level
    # matching so the normalizer cannot re-amplify it afterwards.
    audio -= np.float32(np.mean(audio, dtype=np.float64))
    audio = _clean_lowpass(audio, int(sr), cutoff=7600.0)
    if normalize:
        audio = _safe_normalize(audio)

    # Very short edge fades prevent exported scene boundaries from clicking.
    fade = min(int(0.010 * sr), len(audio) // 2)
    if fade > 1:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        audio[:fade] *= ramp
        audio[-fade:] *= ramp[::-1]

    if natural_edges:
        head = np.zeros(int(0.020 * sr), dtype=np.float32)
        tail = np.zeros(int(0.070 * sr), dtype=np.float32)
        audio = np.concatenate([head, audio, tail])

    return np.clip(audio, -0.90, 0.90).astype(np.float32, copy=False)


# The quality worker resolves studio_finish from this exec namespace at runtime.
ns["studio_finish"] = clean_studio_finish


def clean_start_generate(self) -> None:
    global _render_mode
    self.context_cues_var.set(1)
    mode = str(self.quality_mode_var.get())
    _render_mode = mode

    if mode == CLEAN_MODE:
        if not FULL_PRECISION_MODEL.is_file():
            from tkinter import messagebox

            messagebox.showerror(
                "Thiếu model FP32",
                "Chưa có Kokoro FP32 clean model. Đóng app rồi chạy lại START_PORTABLE.bat để tải model khoảng 326 MB.",
                parent=self,
            )
            return
        # Force FP32 immediately before rendering so an older saved profile
        # cannot silently restore the FP16 path.
        self.model_var.set(str(FULL_PRECISION_MODEL))

    _original_start_generate()


app.start_generate = types.MethodType(clean_start_generate, app)
app.run_btn.configure(command=app.start_generate)


def restore_clean_default() -> None:
    # The profile layer restores the previous session shortly after startup.
    current = str(app.quality_mode_var.get())
    if current not in (CLEAN_MODE, FAST_MODE, QUALITY_BALANCED):
        app.quality_mode_var.set(CLEAN_MODE)
    app.context_cues_var.set(1)


app.after(1400, restore_clean_default)
app._append_log(
    "Clean FP32 Anti-rè: mỗi cue synth độc lập · 7.6 kHz anti-static FIR · safe normalize max +1.9 dB · cảm xúc/Smart Text vẫn ON."
)
app.mainloop()
