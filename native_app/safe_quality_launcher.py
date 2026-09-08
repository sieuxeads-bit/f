from __future__ import annotations

import types
from pathlib import Path

import numpy as np


BASE_DIR = Path(__file__).resolve().parent
QUALITY_LAUNCHER = BASE_DIR / "quality_launcher.py"

# Build the full Quality UI but take over its final mainloop so this layer can
# harden the experimental context renderer against audible cuts/stutters.
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
context_combo = ns["context_combo"]
known_phonemes = ns["known_phonemes"]
original_make_kokoro = ns["make_kokoro"]

# Two neighboring cues are enough to carry sentence context. Five-cue groups
# make long synthesis windows and create more opportunities for audible joins.
context_combo["values"] = [1, 2]
try:
    if int(app.context_cues_var.get()) > 2:
        app.context_cues_var.set(2)
except Exception:
    app.context_cues_var.set(2)

_clamping_context = False


def clamp_context(*_args) -> None:
    global _clamping_context
    if _clamping_context:
        return
    try:
        value = int(app.context_cues_var.get())
    except Exception:
        value = 2
    if value < 1 or value > 2:
        _clamping_context = True
        try:
            app.context_cues_var.set(max(1, min(2, value)))
        finally:
            _clamping_context = False


app.context_cues_var.trace_add("write", clamp_context)


def _soft_zero_cut(audio: np.ndarray, predicted: int, sr: int, lo: int, hi: int) -> int:
    """Choose a quiet, near-zero sample around a predicted scene boundary."""
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if hi <= lo + 4:
        return max(lo, min(hi, predicted))

    # Search roughly +/-80 ms around the model timing. Score 8 ms RMS windows
    # every 1 ms. A quiet valley is much safer than slicing on a phoneme edge.
    search_radius = int(0.080 * sr)
    start = max(lo, predicted - search_radius)
    stop = min(hi, predicted + search_radius)
    frame = max(8, int(0.008 * sr))
    step = max(1, int(0.001 * sr))
    half = frame // 2

    best_center = max(start, min(stop, predicted))
    best_score = None
    for center in range(start, stop + 1, step):
        a = max(lo, center - half)
        b = min(hi, center + half)
        if b - a < 4:
            continue
        block = audio[a:b]
        rms = float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))
        distance_penalty = abs(center - predicted) / max(1, search_radius) * 0.012
        score = rms + distance_penalty
        if best_score is None or score < best_score:
            best_score = score
            best_center = center

    # Snap the quiet valley to the nearest zero crossing / smallest magnitude.
    snap = max(1, int(0.006 * sr))
    a = max(lo, best_center - snap)
    b = min(hi, best_center + snap)
    if b <= a:
        return best_center
    local = audio[a:b]
    signs = np.signbit(local)
    crossings = np.flatnonzero(signs[:-1] != signs[1:])
    if crossings.size:
        candidates = a + crossings + 1
        return int(candidates[np.argmin(np.abs(candidates - best_center))])
    return int(a + np.argmin(np.abs(local)))


def safe_split_context_audio(kokoro, joined_text: str, texts: list[str], timings, audio: np.ndarray, sr: int, lang: str) -> list[np.ndarray]:
    """Split context speech only at quiet/zero-crossing valleys.

    The previous renderer cut almost directly at phoneme timing boundaries. A
    timing edge can still sit inside voiced energy, producing clicks, roughness
    or a tiny repeated/stuttered syllable after each scene is exported again.
    """
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not timings or audio.size == 0:
        raise ValueError("model returned no usable timing/audio")

    joined_known = known_phonemes(kokoro, joined_text, lang)
    if not joined_known:
        raise ValueError("joined text produced no known phonemes")
    if len(timings) < len(joined_known):
        raise ValueError(
            f"timing/phoneme mismatch: {len(timings)} timings for {len(joined_known)} phonemes"
        )

    ranges: list[tuple[int, int]] = []
    cursor = 0
    for text in texts:
        part = known_phonemes(kokoro, text, lang).strip()
        if not part:
            raise ValueError("a cue produced no known phonemes")
        at = joined_known.find(part, cursor)
        if at < 0:
            raise ValueError("could not align a cue inside the context phonemes")
        ranges.append((at, at + len(part)))
        cursor = at + len(part)

    # Clean whitespace from timing ranges first.
    cleaned: list[tuple[int, int]] = []
    for start_i, end_i in ranges:
        while start_i < end_i and timings[start_i].phoneme.isspace():
            start_i += 1
        while end_i > start_i and timings[end_i - 1].phoneme.isspace():
            end_i -= 1
        if end_i <= start_i:
            raise ValueError("empty aligned cue")
        cleaned.append((start_i, end_i))

    total = len(audio)
    first_start = max(0, int(round((float(timings[cleaned[0][0]].start) - 0.020) * sr)))
    last_end = min(total, int(round((float(timings[cleaned[-1][1] - 1].end) + 0.100) * sr)))
    cuts = [first_start]

    for idx in range(len(cleaned) - 1):
        _, end_i = cleaned[idx]
        next_start_i, _ = cleaned[idx + 1]
        speech_end = float(timings[end_i - 1].end)
        next_start = float(timings[next_start_i].start)
        # Model timing gap gives a good center; if timings overlap, use the end
        # of the previous cue and let the low-energy search find a safer valley.
        predicted_seconds = (speech_end + next_start) * 0.5 if next_start >= speech_end else speech_end
        predicted = int(round(predicted_seconds * sr))
        min_piece = int(0.040 * sr)
        lo = cuts[-1] + min_piece
        hi = last_end - (len(cleaned) - idx - 1) * min_piece
        cut = _soft_zero_cut(audio, predicted, sr, lo, hi)
        cuts.append(max(lo, min(hi, cut)))

    cuts.append(last_end)
    pieces: list[np.ndarray] = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b <= a:
            raise ValueError("unsafe context boundary")
        pieces.append(audio[a:b].copy())
    return pieces


ns["split_context_audio"] = safe_split_context_audio


def safe_make_kokoro(model, voices, device_name):
    kokoro, provider = original_make_kokoro(model, voices, device_name)
    original_create_timed = kokoro.create_timed

    def create_timed_no_group_sliding(self, *args, **kwargs):
        # Multi-cue context is already useful without sliding-window synthesis.
        # create() in kokoro-onnx calls create_timed() with `continuous` as the
        # 9th positional argument. Direct create_timed() calls usually pass it
        # as a keyword. Handle both forms so it is never supplied twice.
        if len(args) >= 9:
            mutable_args = list(args)
            mutable_args[8] = False
            kwargs.pop("continuous", None)
            return original_create_timed(*mutable_args, **kwargs)

        kwargs["continuous"] = False
        return original_create_timed(*args, **kwargs)

    kokoro.create_timed = types.MethodType(create_timed_no_group_sliding, kokoro)
    return kokoro, provider


ns["make_kokoro"] = safe_make_kokoro

# Existing quality worker resolves its helpers through this same exec namespace,
# so replacing split_context_audio/make_kokoro above hardens it without copying
# the complete renderer. Keep context <=2 even when an older saved profile had 5.
original_start_generate = app.start_generate


def safe_start_generate(self) -> None:
    try:
        self.context_cues_var.set(max(1, min(2, int(self.context_cues_var.get()))))
    except Exception:
        self.context_cues_var.set(2)
    original_start_generate()


app.start_generate = types.MethodType(safe_start_generate, app)
app.run_btn.configure(command=app.start_generate)


def enforce_safe_context_after_profile_restore() -> None:
    clamp_context()
    app.after(800, enforce_safe_context_after_profile_restore)


app.after(500, enforce_safe_context_after_profile_restore)
app._append_log(
    "Safe Prosody: context tối đa 2 cue · group continuous OFF · quiet/zero-cross scene cuts ON."
)
app.mainloop()
