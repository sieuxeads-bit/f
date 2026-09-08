from __future__ import annotations

import json
import os
import re
import time
import types
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
import soundfile as sf

try:
    from num2words import num2words
except Exception:
    num2words = None


BASE_DIR = Path(__file__).resolve().parent
PROFILE_LAUNCHER = BASE_DIR / "profile_launcher.py"

# Build the existing Studio + profile UI, but take over its final mainloop so
# this layer can add quality/prosody controls without duplicating the base GUI.
source = PROFILE_LAUNCHER.read_text(encoding="utf-8")
marker = "\napp.mainloop()"
if marker not in source:
    raise RuntimeError("profile_launcher.py layout changed: app.mainloop() not found")
source = source.rsplit(marker, 1)[0] + "\n"
profile_ns: dict[str, object] = {
    "__file__": str(PROFILE_LAUNCHER),
    "__name__": "_kokoro_profile_embedded",
    "__package__": None,
}
exec(compile(source, str(PROFILE_LAUNCHER), "exec"), profile_ns)

app = profile_ns["app"]
studio_ns = profile_ns["namespace"]
studio = profile_ns["studio"]

NO_BLEND = studio_ns["NO_BLEND"]
PRESETS = studio_ns["PRESETS"]
normalize_scene = studio_ns["normalize_scene"]
make_kokoro = studio_ns["make_kokoro"]
resolve_provider = studio_ns["resolve_provider"]
resample_linear = studio_ns["resample_linear"]

LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
QUALITY_DIR = LOCALAPPDATA / "KokoroSRT" / "quality"
QUALITY_DIR.mkdir(parents=True, exist_ok=True)
PRONUNCIATION_FILE = QUALITY_DIR / "pronunciation.json"

QUALITY_HIGH = "High Prosody + Context"
QUALITY_BALANCED = "Balanced"

# Extra speaking presets. These change timing/pause behavior, not pitch-shifting
# or heavy post effects that can make Kokoro sound synthetic.
PRESETS.update(
    {
        "Narrator": {"speed": 0.96, "sentence": 0.34, "clause": 0.13, "blend": 8},
        "Conversation": {"speed": 1.00, "sentence": 0.22, "clause": 0.09, "blend": 6},
        "Documentary": {"speed": 0.94, "sentence": 0.38, "clause": 0.14, "blend": 10},
        "Dramatic": {"speed": 0.91, "sentence": 0.46, "clause": 0.18, "blend": 15},
        "Soft": {"speed": 0.93, "sentence": 0.34, "clause": 0.15, "blend": 8},
        "Energetic": {"speed": 1.05, "sentence": 0.20, "clause": 0.07, "blend": 8},
    }
)
try:
    studio_ns["preset_combo"]["values"] = list(PRESETS)
except Exception:
    pass


def load_pronunciation_rules() -> dict[str, str]:
    try:
        data = json.loads(PRONUNCIATION_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {
                str(k).strip(): str(v).strip()
                for k, v in data.items()
                if str(k).strip() and str(v).strip()
            }
    except (OSError, ValueError, TypeError):
        pass
    return {}


pronunciation_rules: dict[str, str] = load_pronunciation_rules()


def save_pronunciation_rules(rules: dict[str, str]) -> None:
    global pronunciation_rules
    QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    temp = PRONUNCIATION_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(PRONUNCIATION_FILE)
    pronunciation_rules = dict(rules)


def apply_pronunciation_rules(text: str) -> str:
    result = text
    for source, replacement in sorted(
        pronunciation_rules.items(), key=lambda item: len(item[0]), reverse=True
    ):
        escaped = re.escape(source)
        left = r"(?<!\w)" if source[:1].isalnum() else ""
        right = r"(?!\w)" if source[-1:].isalnum() else ""
        result = re.sub(left + escaped + right, replacement, result, flags=re.IGNORECASE)
    return result


def open_pronunciation_editor() -> None:
    window = tk.Toplevel(app)
    window.title("Từ điển phát âm")
    window.geometry("720x520")
    window.minsize(600, 420)
    window.configure(bg="#0b1020")
    window.transient(app)

    frame = ttk.Frame(window, style="Root.TFrame", padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="TỪ ĐIỂN PHÁT ÂM", style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(
        frame,
        text=(
            "Mỗi dòng: từ/cụm từ = cách muốn Kokoro đọc. "
            "Ví dụ: RTX = R T X   |   OpenAI = Open A I"
        ),
        style="Subtitle.TLabel",
    ).pack(anchor="w", pady=(4, 10))

    editor = tk.Text(
        frame,
        wrap="none",
        bg="#0f172a",
        fg="#e2e8f0",
        insertbackground="#f8fafc",
        selectbackground="#263248",
        relief="flat",
        padx=12,
        pady=10,
        font=("Cascadia Mono", 10),
    )
    editor.pack(fill="both", expand=True)
    editor.insert(
        "1.0",
        "\n".join(f"{key} = {value}" for key, value in pronunciation_rules.items()),
    )

    buttons = ttk.Frame(frame, style="Root.TFrame")
    buttons.pack(fill="x", pady=(10, 0))

    def do_save() -> None:
        parsed: dict[str, str] = {}
        invalid: list[int] = []
        for line_number, raw in enumerate(editor.get("1.0", "end").splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                invalid.append(line_number)
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if not key or not value:
                invalid.append(line_number)
                continue
            parsed[key] = value
        if invalid:
            messagebox.showerror(
                "Sai định dạng",
                "Các dòng chưa đúng dạng 'từ = cách đọc': " + ", ".join(map(str, invalid)),
                parent=window,
            )
            return
        try:
            save_pronunciation_rules(parsed)
            pronunciation_count_var.set(f"{len(parsed)} quy tắc")
            app._append_log(f"Đã lưu {len(parsed)} quy tắc phát âm.")
            window.destroy()
        except OSError as exc:
            messagebox.showerror("Không lưu được", str(exc), parent=window)

    ttk.Button(buttons, text="Lưu từ điển", style="Accent.TButton", command=do_save).pack(side="right")
    ttk.Button(buttons, text="Đóng", style="Ghost.TButton", command=window.destroy).pack(side="right", padx=(0, 8))


UNIT_WORDS = {
    "km": "kilometers",
    "m": "meters",
    "cm": "centimeters",
    "mm": "millimeters",
    "kg": "kilograms",
    "g": "grams",
    "mg": "milligrams",
    "hz": "hertz",
    "khz": "kilohertz",
    "mhz": "megahertz",
    "ghz": "gigahertz",
    "kb": "kilobytes",
    "mb": "megabytes",
    "gb": "gigabytes",
    "tb": "terabytes",
    "km/h": "kilometers per hour",
    "mph": "miles per hour",
}
DIGIT_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def english_number_words(value: str, *, ordinal: bool = False) -> str:
    if num2words is None:
        return value
    value = value.replace(",", "")
    try:
        if ordinal:
            return str(num2words(int(value), to="ordinal", lang="en"))
        if "." in value:
            whole, fraction = value.split(".", 1)
            whole_words = str(num2words(int(whole or "0"), lang="en"))
            fraction_words = " ".join(DIGIT_WORDS[int(ch)] for ch in fraction if ch.isdigit())
            return f"{whole_words} point {fraction_words}".strip()
        number = int(value)
        if 1000 <= number <= 2099 and len(value) == 4:
            try:
                return str(num2words(number, to="year", lang="en"))
            except Exception:
                pass
        return str(num2words(number, lang="en"))
    except (ValueError, TypeError, OverflowError):
        return value


def smart_normalize_text(text: str, lang: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("…", "...")
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if not lang.lower().startswith("en"):
        return text

    def money_usd(match: re.Match[str]) -> str:
        raw = match.group(1).replace(",", "")
        try:
            amount = Decimal(raw)
            dollars = int(amount)
            cents = int((amount - dollars) * 100)
            spoken = f"{english_number_words(str(dollars))} dollar"
            if dollars != 1:
                spoken += "s"
            if cents:
                spoken += f" and {english_number_words(str(cents))} cents"
            return spoken
        except (InvalidOperation, ValueError):
            return match.group(0)

    text = re.sub(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)", money_usd, text)
    text = re.sub(
        r"(?<!\w)(\d+(?:\.\d+)?)\s*%",
        lambda m: f"{english_number_words(m.group(1))} percent",
        text,
    )
    text = re.sub(
        r"(?<!\w)(\d+(?:\.\d+)?)\s*°\s*C\b",
        lambda m: f"{english_number_words(m.group(1))} degrees Celsius",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?<!\w)(\d+(?:\.\d+)?)\s*°\s*F\b",
        lambda m: f"{english_number_words(m.group(1))} degrees Fahrenheit",
        text,
        flags=re.IGNORECASE,
    )

    unit_pattern = "|".join(sorted((re.escape(u) for u in UNIT_WORDS), key=len, reverse=True))

    def unit_repl(match: re.Match[str]) -> str:
        number = english_number_words(match.group(1))
        unit = UNIT_WORDS.get(match.group(2).lower(), match.group(2))
        return f"{number} {unit}"

    text = re.sub(
        rf"(?<!\w)(\d+(?:\.\d+)?)\s*({unit_pattern})(?!\w)",
        unit_repl,
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?<!\w)(\d+)(st|nd|rd|th)\b",
        lambda m: english_number_words(m.group(1), ordinal=True),
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?<![\w./-])\d{1,7}(?![\w./-])",
        lambda m: english_number_words(m.group(0)),
        text,
    )
    text = re.sub(r"(?<=\w)\s*&\s*(?=\w)", " and ", text)
    return re.sub(r"\s+", " ", text).strip()


def has_terminal_punctuation(text: str) -> bool:
    return bool(re.search(r"[.!?…,:;][\"'”’)]*$", text.rstrip()))


def prepare_cue_text(cues, index: int, lang: str, smart_text: bool) -> str:
    text = str(cues[index].text).strip()
    text = apply_pronunciation_rules(text)
    if smart_text:
        text = smart_normalize_text(text, lang)
    if not text or has_terminal_punctuation(text):
        return text

    if index + 1 < len(cues):
        gap = max(0.0, float(cues[index + 1].start) - float(cues[index].end))
        next_text = str(cues[index + 1].text).lstrip()
        if gap <= 0.18 or (next_text[:1].islower() and gap < 0.45):
            return text + ","
        if gap >= 0.40:
            return text + "."
        return text + ","
    return text + "."


def dialogue_marker(text: str) -> bool:
    stripped = text.lstrip()
    if stripped.startswith(("- ", "– ", "— ", ">>")):
        return True
    return bool(re.match(r"^[A-Z][A-Z0-9 _-]{1,24}:\s", stripped))


def build_context_groups(cues, texts: list[str], max_cues: int) -> list[list[int]]:
    if max_cues <= 1:
        return [[i] for i in range(len(cues))]

    groups: list[list[int]] = []
    current: list[int] = []
    current_chars = 0
    for index, cue in enumerate(cues):
        if not current:
            current = [index]
            current_chars = len(texts[index])
            continue
        previous = current[-1]
        gap = max(0.0, float(cue.start) - float(cues[previous].end))
        would_be = current_chars + 1 + len(texts[index])
        speaker_break = dialogue_marker(texts[previous]) or dialogue_marker(texts[index])
        if len(current) >= max_cues or gap > 1.5 or would_be > 700 or speaker_break:
            groups.append(current)
            current = [index]
            current_chars = len(texts[index])
        else:
            current.append(index)
            current_chars = would_be
    if current:
        groups.append(current)
    return groups


def adaptive_speed(base_speed: float, text: str, strength: float) -> float:
    scale = max(0.0, min(1.0, strength / 100.0))
    if scale <= 0:
        return base_speed
    factor = 1.0
    stripped = text.rstrip()
    words = re.findall(r"\b\w+\b", text)
    if "..." in text:
        factor -= 0.055 * scale
    if stripped.endswith("?"):
        factor -= 0.018 * scale
    if stripped.endswith("!"):
        factor += 0.028 * scale
    if len(words) <= 4:
        factor -= 0.030 * scale
    elif len(words) >= 28:
        factor -= 0.012 * scale
    return max(0.5, min(2.0, base_speed * factor))


def adaptive_pauses(sentence: float, clause: float, text: str, strength: float) -> tuple[float, float]:
    scale = max(0.0, min(1.0, strength / 100.0))
    sentence_out = sentence
    clause_out = clause
    if "..." in text:
        sentence_out += 0.10 * scale
    if text.rstrip().endswith("?"):
        sentence_out += 0.035 * scale
    if text.rstrip().endswith("!"):
        sentence_out += 0.025 * scale
    return min(sentence_out, 1.5), min(clause_out, 1.0)


def known_phonemes(kokoro, text: str, lang: str) -> str:
    phonemes = kokoro.tokenizer.phonemize(text, lang)
    phonemes = " ".join(phonemes.split())
    return kokoro.tokenizer.known(phonemes)


def split_context_audio(kokoro, joined_text: str, texts: list[str], timings, audio: np.ndarray, sr: int, lang: str) -> list[np.ndarray]:
    if not timings:
        raise ValueError("model returned no phoneme timings")
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

    total_seconds = len(audio) / sr
    pieces: list[np.ndarray] = []
    for idx, (start_i, end_i) in enumerate(ranges):
        while start_i < end_i and timings[start_i].phoneme.isspace():
            start_i += 1
        while end_i > start_i and timings[end_i - 1].phoneme.isspace():
            end_i -= 1
        if end_i <= start_i:
            raise ValueError("empty aligned cue")

        speech_start = max(0.0, float(timings[start_i].start))
        speech_end = min(total_seconds, float(timings[end_i - 1].end))
        left = max(0.0, speech_start - 0.018)
        if idx + 1 < len(ranges):
            next_start_i = ranges[idx + 1][0]
            while next_start_i < ranges[idx + 1][1] and timings[next_start_i].phoneme.isspace():
                next_start_i += 1
            next_start = float(timings[next_start_i].start)
            available_pause = max(0.0, next_start - speech_end)
            right = min(next_start - 0.010, speech_end + min(0.14, available_pause * 0.70))
        else:
            right = min(total_seconds, speech_end + 0.12)
        if right <= left:
            right = min(total_seconds, max(speech_end, left + 0.03))
        a = max(0, int(round(left * sr)))
        b = min(len(audio), int(round(right * sr)))
        pieces.append(np.asarray(audio[a:b], dtype=np.float32).copy())
    return pieces


def studio_finish(samples: np.ndarray, sr: int, normalize: bool, natural_edges: bool) -> np.ndarray:
    audio = np.asarray(samples, dtype=np.float32).reshape(-1).copy()
    if audio.size == 0:
        return audio
    audio -= np.float32(np.mean(audio, dtype=np.float64))
    if normalize:
        audio = normalize_scene(audio)
    fade = min(int(0.008 * sr), len(audio) // 2)
    if fade > 1:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        audio[:fade] *= ramp
        audio[-fade:] *= ramp[::-1]
    if natural_edges:
        head = np.zeros(int(0.018 * sr), dtype=np.float32)
        tail = np.zeros(int(0.060 * sr), dtype=np.float32)
        audio = np.concatenate([head, audio, tail])
    return np.clip(audio, -1.0, 1.0).astype(np.float32, copy=False)


# Quality UI
app.quality_mode_var = tk.StringVar(value=QUALITY_HIGH)
app.context_cues_var = tk.IntVar(value=3)
app.smart_text_var = tk.BooleanVar(value=True)
app.adaptive_expression_var = tk.BooleanVar(value=True)
app.natural_edges_var = tk.BooleanVar(value=True)
app.emotion_strength_var = tk.DoubleVar(value=35.0)

pronunciation_count_var = tk.StringVar(value=f"{len(pronunciation_rules)} quy tắc")
emotion_label_var = tk.StringVar(value="35%")
quality_status_var = tk.StringVar(value="Đang kiểm tra model prosody…")

ttk.Label(studio, text="Chất lượng", style="CardText.TLabel").grid(
    row=5, column=0, sticky="w", padx=(16, 8), pady=(4, 4)
)
quality_combo = ttk.Combobox(
    studio,
    textvariable=app.quality_mode_var,
    values=[QUALITY_HIGH, QUALITY_BALANCED],
    state="readonly",
    style="Modern.TCombobox",
)
quality_combo.grid(row=5, column=1, sticky="ew", pady=(4, 4))

ttk.Label(studio, text="Context cue", style="CardText.TLabel").grid(
    row=5, column=2, sticky="e", padx=(12, 8), pady=(4, 4)
)
context_combo = ttk.Combobox(
    studio,
    textvariable=app.context_cues_var,
    values=[1, 2, 3, 4, 5],
    state="readonly",
    width=7,
    style="Modern.TCombobox",
)
context_combo.grid(row=5, column=3, sticky="ew", pady=(4, 4))

emotion_frame = ttk.Frame(studio, style="Card.TFrame")
emotion_frame.grid(row=5, column=4, columnspan=2, sticky="ew", padx=(12, 16), pady=(4, 4))
emotion_frame.columnconfigure(1, weight=1)
ttk.Label(emotion_frame, text="Cảm xúc", style="CardText.TLabel").grid(row=0, column=0, padx=(0, 8))
ttk.Scale(
    emotion_frame,
    from_=0,
    to=100,
    variable=app.emotion_strength_var,
    style="Modern.Horizontal.TScale",
).grid(row=0, column=1, sticky="ew")
ttk.Label(emotion_frame, textvariable=emotion_label_var, width=5, style="CardValue.TLabel").grid(
    row=0, column=2, padx=(8, 0)
)

quality_flags = ttk.Frame(studio, style="Card.TFrame")
quality_flags.grid(row=6, column=0, columnspan=6, sticky="ew", padx=16, pady=(2, 12))
quality_flags.columnconfigure(5, weight=1)


def dark_check(parent, text: str, variable: tk.Variable):
    return tk.Checkbutton(
        parent,
        text=text,
        variable=variable,
        bg="#111827",
        fg="#f8fafc",
        activebackground="#111827",
        activeforeground="#f8fafc",
        selectcolor="#0f172a",
        highlightthickness=0,
        bd=0,
    )


dark_check(quality_flags, "Smart Text", app.smart_text_var).grid(row=0, column=0, padx=(0, 12))
dark_check(quality_flags, "Adaptive Expression", app.adaptive_expression_var).grid(row=0, column=1, padx=12)
dark_check(quality_flags, "Natural edges", app.natural_edges_var).grid(row=0, column=2, padx=12)
ttk.Button(
    quality_flags,
    text="Từ điển phát âm…",
    style="Ghost.TButton",
    command=open_pronunciation_editor,
).grid(row=0, column=3, padx=(12, 6))
ttk.Label(quality_flags, textvariable=pronunciation_count_var, style="CardText.TLabel").grid(
    row=0, column=4, padx=(0, 12)
)
ttk.Label(quality_flags, textvariable=quality_status_var, style="CardValue.TLabel").grid(
    row=0, column=5, sticky="e"
)


def refresh_emotion_label(*_args) -> None:
    emotion_label_var.set(f"{app.emotion_strength_var.get():.0f}%")


app.emotion_strength_var.trace_add("write", refresh_emotion_label)
refresh_emotion_label()
try:
    app.geometry("1120x880")
    app.minsize(1000, 760)
except tk.TclError:
    pass


# Synthesis override
original_start_generate = app.start_generate


def quality_start_generate(self) -> None:
    self._quality_fx = {
        "mode": self.quality_mode_var.get(),
        "context_cues": int(self.context_cues_var.get()),
        "smart_text": bool(self.smart_text_var.get()),
        "adaptive_expression": bool(self.adaptive_expression_var.get()),
        "natural_edges": bool(self.natural_edges_var.get()),
        "emotion_strength": float(self.emotion_strength_var.get()),
    }
    original_start_generate()


app.start_generate = types.MethodType(quality_start_generate, app)
app.run_btn.configure(command=app.start_generate)


def quality_generate_worker(
    self,
    model: Path,
    voices: Path,
    cues,
    output: Path,
    requested_voice: str,
    speed: float,
    lang: str,
    device: str,
) -> None:
    try:
        provider = resolve_provider(device)
        signature = (str(model), str(voices), provider)
        if self._kokoro is None or self._loaded_signature != signature:
            self._events.put(("status", "Đang nạp ONNX session chất lượng cao…"))
            self._kokoro, self._backend_provider = make_kokoro(model, voices, device)
            self._loaded_signature = (str(model), str(voices), self._backend_provider)

        kokoro = self._kokoro
        assert kokoro is not None
        provider = self._backend_provider or provider
        available = list(kokoro.get_voices())
        voice = requested_voice or (available[0] if available else "")
        if not voice or voice not in available:
            raise RuntimeError(f"Voice không tồn tại: {voice or '(trống)'}")

        fx = getattr(self, "_voice_fx", {})
        blend_voice = str(fx.get("blend_voice", NO_BLEND))
        blend_percent = max(0.0, min(100.0, float(fx.get("blend_percent", 0.0))))
        sentence_pause = max(0.0, min(1.5, float(fx.get("sentence_pause", 0.25))))
        clause_pause = max(0.0, min(1.0, float(fx.get("clause_pause", 0.10))))
        normalize = bool(fx.get("normalize", True))
        preset = str(fx.get("preset", "Natural"))

        qfx = getattr(self, "_quality_fx", {})
        quality_mode = str(qfx.get("mode", QUALITY_HIGH))
        context_cues = max(1, min(5, int(qfx.get("context_cues", 3))))
        smart_text = bool(qfx.get("smart_text", True))
        adaptive_expression = bool(qfx.get("adaptive_expression", True))
        natural_edges = bool(qfx.get("natural_edges", True))
        emotion_strength = max(0.0, min(100.0, float(qfx.get("emotion_strength", 35.0))))

        primary_style = kokoro.get_voice_style(voice)
        voice_style = primary_style
        actual_blend = 0.0
        if (
            blend_voice
            and blend_voice != NO_BLEND
            and blend_voice in available
            and blend_voice != voice
            and blend_percent > 0
        ):
            secondary_style = kokoro.get_voice_style(blend_voice)
            ratio = np.float32(blend_percent / 100.0)
            voice_style = (
                np.asarray(primary_style, dtype=np.float32) * (np.float32(1.0) - ratio)
                + np.asarray(secondary_style, dtype=np.float32) * ratio
            ).astype(np.float32, copy=False)
            actual_blend = blend_percent

        supports_timings = bool(getattr(kokoro, "has_timings", False))
        context_enabled = quality_mode == QUALITY_HIGH and context_cues > 1 and supports_timings
        continuous_enabled = quality_mode == QUALITY_HIGH and supports_timings

        prepared = [prepare_cue_text(cues, i, lang, smart_text) for i in range(len(cues))]
        groups = build_context_groups(cues, prepared, context_cues if context_enabled else 1)

        self._events.put(
            (
                "log",
                f"Quality: {quality_mode} · context {context_cues} cue"
                + (" · duration model READY" if supports_timings else " · no duration output, safe fallback")
                + (" · Smart Text ON" if smart_text else " · Smart Text OFF")
                + (f" · expression {emotion_strength:.0f}%" if adaptive_expression else " · expression OFF"),
            )
        )
        self._events.put(
            (
                "log",
                f"Voice: {preset} · {voice}"
                + (f" + {blend_voice} {actual_blend:.0f}%" if actual_blend else "")
                + f" · speed {speed:.2f}x · pause {sentence_pause:.2f}/{clause_pause:.2f}s",
            )
        )

        started = time.perf_counter()
        sample_rate: int | None = None
        cursor_sample = 0
        chunks: list[tuple[int, np.ndarray]] = []
        generated_audio_samples = 0
        total = len(cues)
        completed = 0

        dubbing_dir_text = getattr(self, "_dubbing_dir", "")
        dubbing_dir = Path(dubbing_dir_text) if dubbing_dir_text else output.parent / "2_Dubbing_Audio"
        dubbing_dir.mkdir(parents=True, exist_ok=True)
        for old_scene in dubbing_dir.glob("scene_*_audio.wav"):
            try:
                old_scene.unlink()
            except OSError:
                pass

        def save_scene(scene_index: int, samples: np.ndarray, sr: int) -> None:
            nonlocal sample_rate, cursor_sample, generated_audio_samples, completed
            audio = np.asarray(samples, dtype=np.float32).reshape(-1)
            if sample_rate is None:
                sample_rate = int(sr)
            elif int(sr) != sample_rate:
                audio = resample_linear(audio, round(len(audio) * sample_rate / int(sr)))
                sr = sample_rate

            assert sample_rate is not None
            audio = studio_finish(audio, sample_rate, normalize, natural_edges)
            scene_path = dubbing_dir / f"scene_{scene_index:03d}_audio.wav"
            sf.write(str(scene_path), audio, sample_rate, subtype="PCM_16")

            requested_start = max(0, int(round(float(cues[scene_index].start) * sample_rate)))
            start_sample = max(requested_start, cursor_sample)
            chunks.append((start_sample, audio))
            cursor_sample = start_sample + len(audio)
            generated_audio_samples += len(audio)
            completed += 1
            self._events.put(("progress", completed * 100.0 / total))

        def synthesize_one(scene_index: int) -> None:
            text = prepared[scene_index]
            local_speed = adaptive_speed(speed, text, emotion_strength) if adaptive_expression else speed
            local_sentence, local_clause = (
                adaptive_pauses(sentence_pause, clause_pause, text, emotion_strength)
                if adaptive_expression
                else (sentence_pause, clause_pause)
            )
            use_continuous = False
            if continuous_enabled:
                try:
                    use_continuous = len(known_phonemes(kokoro, text, lang)) > 260
                except Exception:
                    use_continuous = False
            samples, sr = kokoro.create(
                text,
                voice=voice_style,
                speed=local_speed,
                lang=lang,
                trim=True,
                sentence_pause=local_sentence,
                clause_pause=local_clause,
                continuous=use_continuous,
            )
            save_scene(scene_index, samples, int(sr))

        for group_number, group in enumerate(groups, start=1):
            if self._cancel.is_set():
                self._events.put(("cancelled", None))
                return

            first = group[0]
            last = group[-1]
            self._events.put(
                (
                    "status",
                    f"Đang tạo scene {first:03d}–{last:03d} · nhóm {group_number}/{len(groups)}…",
                )
            )

            if context_enabled and len(group) > 1:
                texts = [prepared[i] for i in group]
                joined = " ".join(texts)
                group_speed = adaptive_speed(speed, joined, emotion_strength) if adaptive_expression else speed
                group_sentence, group_clause = (
                    adaptive_pauses(sentence_pause, clause_pause, joined, emotion_strength)
                    if adaptive_expression
                    else (sentence_pause, clause_pause)
                )
                try:
                    samples, sr, timings = kokoro.create_timed(
                        joined,
                        voice=voice_style,
                        speed=group_speed,
                        lang=lang,
                        trim=True,
                        sentence_pause=group_sentence,
                        clause_pause=group_clause,
                        continuous=continuous_enabled,
                    )
                    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
                    pieces = split_context_audio(
                        kokoro,
                        joined,
                        texts,
                        timings,
                        samples,
                        int(sr),
                        lang,
                    )
                    if len(pieces) != len(group):
                        raise ValueError("context split returned the wrong number of scenes")
                    for scene_index, piece in zip(group, pieces):
                        save_scene(scene_index, piece, int(sr))
                    continue
                except Exception as exc:
                    self._events.put(
                        (
                            "log",
                            f"Context group {first:03d}-{last:03d} fallback sang từng scene: {exc}",
                        )
                    )

            for scene_index in group:
                if self._cancel.is_set():
                    self._events.put(("cancelled", None))
                    return
                synthesize_one(scene_index)

        assert sample_rate is not None
        final_length = max(
            cursor_sample,
            int(round(max(float(cue.end) for cue in cues) * sample_rate)),
            1,
        )
        timeline = np.zeros(final_length, dtype=np.float32)
        for start_sample, samples in chunks:
            end = min(start_sample + len(samples), final_length)
            if end > start_sample:
                timeline[start_sample:end] += samples[: end - start_sample]
        np.clip(timeline, -1.0, 1.0, out=timeline)

        output.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output), timeline, sample_rate, subtype="PCM_16")

        elapsed = max(time.perf_counter() - started, 1e-6)
        generated_seconds = generated_audio_samples / sample_rate
        speed_x = generated_seconds / elapsed
        self._events.put(("log", f"Đã xuất {total} scene chất lượng cao vào: {dubbing_dir}"))
        self._events.put(
            (
                "done",
                {
                    "output": str(output),
                    "dubbing_dir": str(dubbing_dir),
                    "elapsed": elapsed,
                    "generated_seconds": generated_seconds,
                    "speed_x": speed_x,
                    "provider": provider,
                    "cues": total,
                },
            )
        )
    except Exception as exc:
        self._events.put(("error", f"Lỗi tạo voice chất lượng cao: {exc}"))


app._generate_worker = types.MethodType(quality_generate_worker, app)


# Persist quality settings in existing Voice Profile / Last Session files.
original_current_state = profile_ns["current_state"]
original_apply_state = profile_ns["apply_state"]


def quality_current_state(name: str = "") -> dict[str, object]:
    data = original_current_state(name)
    data.update(
        {
            "version": 2,
            "quality_mode": app.quality_mode_var.get(),
            "context_cues": int(app.context_cues_var.get()),
            "smart_text": bool(app.smart_text_var.get()),
            "adaptive_expression": bool(app.adaptive_expression_var.get()),
            "natural_edges": bool(app.natural_edges_var.get()),
            "emotion_strength": float(app.emotion_strength_var.get()),
        }
    )
    return data


def quality_apply_state(data: dict[str, object], *, announce: bool, retries: int = 100) -> None:
    try:
        mode = str(data.get("quality_mode") or QUALITY_HIGH)
        app.quality_mode_var.set(mode if mode in (QUALITY_HIGH, QUALITY_BALANCED) else QUALITY_HIGH)
        app.context_cues_var.set(max(1, min(5, int(data.get("context_cues", 3)))))
        app.smart_text_var.set(bool(data.get("smart_text", True)))
        app.adaptive_expression_var.set(bool(data.get("adaptive_expression", True)))
        app.natural_edges_var.set(bool(data.get("natural_edges", True)))
        app.emotion_strength_var.set(max(0.0, min(100.0, float(data.get("emotion_strength", 35.0)))))
    except (TypeError, ValueError, tk.TclError):
        pass
    original_apply_state(data, announce=announce, retries=retries)


profile_ns["current_state"] = quality_current_state
profile_ns["apply_state"] = quality_apply_state

schedule_autosave = profile_ns.get("schedule_autosave")
if callable(schedule_autosave):
    for variable in (
        app.quality_mode_var,
        app.context_cues_var,
        app.smart_text_var,
        app.adaptive_expression_var,
        app.natural_edges_var,
        app.emotion_strength_var,
    ):
        variable.trace_add("write", schedule_autosave)


def update_quality_status() -> None:
    kokoro = getattr(app, "_kokoro", None)
    if kokoro is None:
        quality_status_var.set("Prosody: chờ nạp model")
    elif bool(getattr(kokoro, "has_timings", False)):
        quality_status_var.set("Prosody: READY · duration model")
    else:
        quality_status_var.set("Prosody: fallback · chạy lại START_PORTABLE")
    app.after(600, update_quality_status)


app.after(400, update_quality_status)
app.mainloop()
