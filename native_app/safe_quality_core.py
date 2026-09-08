from __future__ import annotations

import os
import types
from pathlib import Path

import numpy as np


BASE_DIR = Path(__file__).resolve().parent
QUALITY_LAUNCHER = BASE_DIR / "quality_launcher.py"

# Build the full Quality/Profile UI but take over the final mainloop. The clean
# renderer keeps expressive text/prosody controls, synthesizes one SRT cue per
# pass, uses the FP32 model, and applies a light anti-static mastering pass.
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

CLEAN_MODE = "Clean Emotional FP32 + Anti-rè R2 (khuyên dùng)"
FAST_MODE = "Fast Emotional FP16"
ALLOWED_MODES = {CLEAN_MODE, FAST_MODE, QUALITY_BALANCED}

quality_combo["values"] = [CLEAN_MODE, FAST_MODE, QUALITY_BALANCED]
context_combo["values"] = [1]
app.quality_mode_var.set(CLEAN_MODE)
app.context_cues_var.set(1)

try:
    app.title("Kokoro SRT Studio · CLEAN R2")
except Exception:
    pass

# Snapshot the selected mode on the Tk/main thread before the worker starts.
_render_mode = CLEAN_MODE
_original_start_generate = app.start_generate
_original_studio_finish = ns["studio_finish"]


def _clean_lowpass(audio: np.ndarray, sr: int, cutoff: float = 7600.0) -> np.ndarray:
    """Linear-phase FIR low-pass for Kokoro's occasional high-band static."""
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

    audio -= np.float32(np.mean(audio, dtype=np.float64))
    audio = _clean_lowpass(audio, int(sr), cutoff=7600.0)
    if normalize:
        audio = _safe_normalize(audio)

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

# ---------------------------------------------------------------------------
# Legacy-profile guard
# ---------------------------------------------------------------------------
# profile_launcher/quality_launcher can restore an older session asynchronously.
# Earlier builds saved "High Prosody + Context". If that value comes back after
# startup it bypasses the clean path. Trace the variable permanently so old
# profiles can never silently reactivate the experimental renderer.
_mode_guard_busy = False
_context_guard_busy = False


def enforce_clean_legacy_guard(*_args) -> None:
    global _mode_guard_busy
    if _mode_guard_busy:
        return
    try:
        current = str(app.quality_mode_var.get())
    except Exception:
        current = CLEAN_MODE
    if current not in ALLOWED_MODES:
        _mode_guard_busy = True
        try:
            app.quality_mode_var.set(CLEAN_MODE)
            app.context_cues_var.set(1)
            app._append_log(
                f"Profile cũ '{current}' đã tự chuyển sang {CLEAN_MODE}."
            )
        finally:
            _mode_guard_busy = False


def enforce_context_one(*_args) -> None:
    global _context_guard_busy
    if _context_guard_busy:
        return
    try:
        value = int(app.context_cues_var.get())
    except Exception:
        value = 1
    if value != 1:
        _context_guard_busy = True
        try:
            app.context_cues_var.set(1)
        finally:
            _context_guard_busy = False


app.quality_mode_var.trace_add("write", enforce_clean_legacy_guard)
app.context_cues_var.trace_add("write", enforce_context_one)


def clean_start_generate(self) -> None:
    global _render_mode

    mode = str(self.quality_mode_var.get())
    if mode not in ALLOWED_MODES:
        mode = CLEAN_MODE
        self.quality_mode_var.set(CLEAN_MODE)

    self.context_cues_var.set(1)
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
        self.model_var.set(str(FULL_PRECISION_MODEL))
        self._append_log(
            "CLEAN R2 active · FP32 · context synth OFF · anti-rè 7.6 kHz · peak <= 0.90."
        )

    _original_start_generate()


app.start_generate = types.MethodType(clean_start_generate, app)
app.run_btn.configure(command=app.start_generate)


def periodic_guard() -> None:
    enforce_clean_legacy_guard()
    enforce_context_one()
    app.after(500, periodic_guard)


# Keep the real prosody context at one cue. The visible control is repurposed by
# parallel_render as "Luồng render" 1..10; it never merges scene audio.
app.after(250, periodic_guard)

from parallel_render import install_parallel_render

install_parallel_render(app, ns, context_combo, ns["studio"])
app._append_log(
    "CLEAN R2: FP32 + anti-rè · context synth OFF · Luồng render 1–10 · mỗi scene vẫn là file riêng."
)
app.mainloop()
