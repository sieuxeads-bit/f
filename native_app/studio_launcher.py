from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
import soundfile as sf

from app import (
    AUTO_DEVICE,
    KokoroSrtApp,
    available_providers,
    make_kokoro,
    resample_linear,
    resolve_provider,
)


BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get("KOKORO_MODEL_DIR", BASE_DIR / "models"))
INT8_MODEL = MODEL_DIR / "kokoro-v1.0.int8.onnx"
FP16_MODEL = MODEL_DIR / "kokoro-v1.0.fp16.onnx"
VOICES_PATH = MODEL_DIR / "voices-v1.0.bin"
DEFAULT_VOICE = "am_michael"

ALL_REGIONS = "Tất cả quốc gia / accent"
ALL_GENDERS = "Tất cả giới tính"
MALE = "♂ Nam"
FEMALE = "♀ Nữ"
UNKNOWN = "? Không rõ"
NO_BLEND = "— Không blend —"

VOICE_PREFIXES = {
    "af": ("🇺🇸 Mỹ · American English", FEMALE, "en-us"),
    "am": ("🇺🇸 Mỹ · American English", MALE, "en-us"),
    "bf": ("🇬🇧 Anh · British English", FEMALE, "en-gb"),
    "bm": ("🇬🇧 Anh · British English", MALE, "en-gb"),
    "jf": ("🇯🇵 Nhật · Japanese", FEMALE, "ja"),
    "jm": ("🇯🇵 Nhật · Japanese", MALE, "ja"),
    "zf": ("🇨🇳 Trung Quốc · Mandarin", FEMALE, "zh"),
    "zm": ("🇨🇳 Trung Quốc · Mandarin", MALE, "zh"),
    "ef": ("🇪🇸 Tây Ban Nha · Spanish", FEMALE, "es"),
    "em": ("🇪🇸 Tây Ban Nha · Spanish", MALE, "es"),
    "ff": ("🇫🇷 Pháp · French", FEMALE, "fr-fr"),
    "fm": ("🇫🇷 Pháp · French", MALE, "fr-fr"),
    "hf": ("🇮🇳 Ấn Độ · Hindi", FEMALE, "hi"),
    "hm": ("🇮🇳 Ấn Độ · Hindi", MALE, "hi"),
    "if": ("🇮🇹 Ý · Italian", FEMALE, "it"),
    "im": ("🇮🇹 Ý · Italian", MALE, "it"),
    "pf": ("🇧🇷 Brazil · Portuguese", FEMALE, "pt-br"),
    "pm": ("🇧🇷 Brazil · Portuguese", MALE, "pt-br"),
}

PRESETS = {
    "Natural": {"speed": 1.00, "sentence": 0.25, "clause": 0.10, "blend": 0},
    "Warm": {"speed": 0.96, "sentence": 0.32, "clause": 0.12, "blend": 12},
    "Deep": {"speed": 0.92, "sentence": 0.36, "clause": 0.14, "blend": 20},
    "Bright": {"speed": 1.04, "sentence": 0.22, "clause": 0.08, "blend": 10},
}


def voice_meta(voice_id: str) -> tuple[str, str, str]:
    key = voice_id[:2].lower()
    if key in VOICE_PREFIXES:
        return VOICE_PREFIXES[key]
    gender = (
        FEMALE
        if len(voice_id) > 1 and voice_id[1].lower() == "f"
        else MALE
        if len(voice_id) > 1 and voice_id[1].lower() == "m"
        else UNKNOWN
    )
    return "🌐 Khác / không rõ", gender, "en-us"


def normalize_scene(samples: np.ndarray) -> np.ndarray:
    """Gentle RMS normalization with a peak limiter; no pitch/time processing."""
    audio = np.asarray(samples, dtype=np.float32).reshape(-1).copy()
    if audio.size == 0:
        return audio

    rms = float(np.sqrt(np.mean(np.square(audio.astype(np.float64)))))
    if rms > 1e-7:
        # About -18 dBFS RMS, with a conservative amplification cap.
        target_rms = 10.0 ** (-18.0 / 20.0)
        gain = min(target_rms / rms, 3.0)
        audio *= np.float32(gain)

    peak = float(np.max(np.abs(audio)))
    if peak > 0.95:
        audio *= np.float32(0.95 / peak)
    return audio


class StudioKokoroSrtApp(KokoroSrtApp):
    """Portable Kokoro studio with voice styling and per-scene dubbing export."""

    def option_add(self, pattern, value, priority=None):
        # Fix Tcl parsing of the two-word Segoe UI family on some Windows/Tk builds.
        if pattern == "*Font" and value == "Segoe UI 10":
            value = "{Segoe UI} 10"
        if priority is None:
            return super().option_add(pattern, value)
        return super().option_add(pattern, value, priority)

    def start_generate(self) -> None:
        srt_text = self.srt_var.get().strip()
        self._dubbing_dir = (
            str(Path(srt_text).expanduser().parent / "2_Dubbing_Audio")
            if srt_text
            else ""
        )

        # Capture all Tk variables on the main thread before the worker starts.
        self._voice_fx = {
            "blend_voice": self.blend_voice_var.get().strip(),
            "blend_percent": float(self.blend_percent_var.get()),
            "sentence_pause": float(self.sentence_pause_var.get()),
            "clause_pause": float(self.clause_pause_var.get()),
            "normalize": bool(self.normalize_var.get()),
            "preset": self.preset_var.get().strip() or "Natural",
        }
        super().start_generate()

    def _generate_worker(
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
                self._events.put(("status", "Đang nạp ONNX session tối ưu…"))
                self._kokoro, self._backend_provider = make_kokoro(model, voices, device)
                self._loaded_signature = (
                    str(model),
                    str(voices),
                    self._backend_provider,
                )

            assert self._kokoro is not None
            provider = self._backend_provider or provider
            available = list(self._kokoro.get_voices())
            voice = requested_voice or (available[0] if available else "")
            if not voice:
                raise RuntimeError("Không tìm thấy voice trong voices .bin.")
            if voice not in available:
                raise RuntimeError(f"Voice không tồn tại: {voice}")

            fx = getattr(self, "_voice_fx", {})
            blend_voice = str(fx.get("blend_voice", NO_BLEND))
            blend_percent = max(0.0, min(100.0, float(fx.get("blend_percent", 0.0))))
            sentence_pause = max(0.0, min(1.5, float(fx.get("sentence_pause", 0.25))))
            clause_pause = max(0.0, min(1.0, float(fx.get("clause_pause", 0.10))))
            normalize = bool(fx.get("normalize", True))
            preset = str(fx.get("preset", "Natural"))

            primary_style = self._kokoro.get_voice_style(voice)
            voice_style = primary_style
            actual_blend = 0.0
            if (
                blend_voice
                and blend_voice != NO_BLEND
                and blend_voice in available
                and blend_voice != voice
                and blend_percent > 0
            ):
                secondary_style = self._kokoro.get_voice_style(blend_voice)
                ratio = np.float32(blend_percent / 100.0)
                voice_style = np.asarray(primary_style) * (np.float32(1.0) - ratio) + np.asarray(secondary_style) * ratio
                voice_style = np.asarray(voice_style, dtype=np.float32)
                actual_blend = blend_percent

            self._events.put(
                (
                    "log",
                    f"Style: {preset} · {voice}"
                    + (
                        f" + {blend_voice} {actual_blend:.0f}%"
                        if actual_blend > 0
                        else ""
                    )
                    + f" · speed {speed:.2f}x · pause {sentence_pause:.2f}/{clause_pause:.2f}s"
                    + (" · normalize ON" if normalize else " · normalize OFF"),
                )
            )

            started = time.perf_counter()
            sample_rate: int | None = None
            cursor_sample = 0
            chunks: list[tuple[int, np.ndarray]] = []
            generated_audio_samples = 0
            total = len(cues)

            dubbing_dir_text = getattr(self, "_dubbing_dir", "")
            dubbing_dir = (
                Path(dubbing_dir_text)
                if dubbing_dir_text
                else output.parent / "2_Dubbing_Audio"
            )
            dubbing_dir.mkdir(parents=True, exist_ok=True)

            for old_scene in dubbing_dir.glob("scene_*_audio.wav"):
                try:
                    old_scene.unlink()
                except OSError:
                    pass

            for scene_index, cue in enumerate(cues):
                i = scene_index + 1
                if self._cancel.is_set():
                    self._events.put(("cancelled", None))
                    return

                if i == 1 or i == total or i % 5 == 0:
                    self._events.put(
                        (
                            "status",
                            f"Đang tạo scene {scene_index:03d} · {i}/{total}…",
                        )
                    )

                samples, sr = self._kokoro.create(
                    cue.text,
                    voice=voice_style,
                    speed=speed,
                    lang=lang,
                    trim=True,
                    sentence_pause=sentence_pause,
                    clause_pause=clause_pause,
                )
                samples = np.asarray(samples, dtype=np.float32).reshape(-1)
                sr = int(sr)

                if sample_rate is None:
                    sample_rate = sr
                elif sr != sample_rate:
                    samples = resample_linear(
                        samples,
                        round(len(samples) * sample_rate / sr),
                    )

                if normalize:
                    samples = normalize_scene(samples)

                assert sample_rate is not None
                scene_path = dubbing_dir / f"scene_{scene_index:03d}_audio.wav"
                sf.write(str(scene_path), samples, sample_rate, subtype="PCM_16")

                requested_start = max(0, int(round(cue.start * sample_rate)))
                start_sample = max(requested_start, cursor_sample)
                chunks.append((start_sample, samples))
                cursor_sample = start_sample + len(samples)
                generated_audio_samples += len(samples)

                if start_sample > requested_start and (i == 1 or i % 10 == 0):
                    delay = (start_sample - requested_start) / sample_rate
                    self._events.put(
                        (
                            "log",
                            f"Scene {scene_index:03d}: dời +{delay:.2f}s trong WAV tổng để tránh chồng giọng.",
                        )
                    )

                self._events.put(("progress", i * 100.0 / total))

            assert sample_rate is not None
            final_length = max(
                cursor_sample,
                int(round(max(cue.end for cue in cues) * sample_rate)),
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
            self._events.put(("log", f"Đã xuất {total} scene vào: {dubbing_dir}"))
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
        except TypeError as exc:
            if "sentence_pause" in str(exc) or "clause_pause" in str(exc):
                self._events.put(
                    (
                        "error",
                        "Kokoro library đang là bản cũ, chưa hỗ trợ Pause. Chạy lại START_PORTABLE.bat để tự cập nhật thư viện.",
                    )
                )
            else:
                self._events.put(("error", f"Lỗi tạo voice: {exc}"))
        except Exception as exc:
            self._events.put(("error", f"Lỗi tạo voice: {exc}"))

    def open_output_folder(self) -> None:
        srt_text = self.srt_var.get().strip()
        if srt_text:
            folder = Path(srt_text).expanduser().parent / "2_Dubbing_Audio"
        else:
            output = self.output_var.get().strip()
            folder = (
                Path(output).expanduser().parent / "2_Dubbing_Audio"
                if output
                else Path.cwd()
            )
        if not folder.exists():
            folder = folder.parent

        try:
            if sys.platform.startswith("win"):
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror("Không mở được thư mục", str(exc))


providers = set(available_providers())
has_gpu = "CUDAExecutionProvider" in providers or "DmlExecutionProvider" in providers
model_path = FP16_MODEL if has_gpu and FP16_MODEL.is_file() else INT8_MODEL

app = StudioKokoroSrtApp()
app.speed_var.set(1.0)
app.device_var.set(AUTO_DEVICE)

if model_path.is_file():
    app.model_var.set(str(model_path))
if VOICES_PATH.is_file():
    app.voices_var.set(str(VOICES_PATH))

app._device_changed()

# ---- Voice Studio panel -------------------------------------------------
root = app.winfo_children()[0]
children = root.winfo_children()
before_widget = children[4] if len(children) > 4 else None
studio = ttk.Frame(root, style="Card.TFrame")
pack_args = {"fill": "x", "pady": (0, 10)}
if before_widget is not None:
    pack_args["before"] = before_widget
studio.pack(**pack_args)

region_var = tk.StringVar(value=ALL_REGIONS)
gender_var = tk.StringVar(value=ALL_GENDERS)
voice_info_var = tk.StringVar(value="Đang chờ danh sách voice…")
app.preset_var = tk.StringVar(value="Natural")
app.blend_voice_var = tk.StringVar(value=NO_BLEND)
app.blend_percent_var = tk.DoubleVar(value=0.0)
app.sentence_pause_var = tk.DoubleVar(value=0.25)
app.clause_pause_var = tk.DoubleVar(value=0.10)
app.normalize_var = tk.BooleanVar(value=True)

blend_label_var = tk.StringVar(value="0%")
sentence_label_var = tk.StringVar(value="0.25s")
clause_label_var = tk.StringVar(value="0.10s")

for col, weight in ((1, 2), (3, 1), (5, 2)):
    studio.columnconfigure(col, weight=weight)

ttk.Label(studio, text="VOICE STUDIO", style="CardTitle.TLabel").grid(
    row=0, column=0, columnspan=6, sticky="w", padx=16, pady=(12, 7)
)

# Row 1: catalog filters.
ttk.Label(studio, text="Quốc gia / accent", style="CardText.TLabel").grid(
    row=1, column=0, sticky="w", padx=(16, 8), pady=4
)
region_combo = ttk.Combobox(
    studio,
    textvariable=region_var,
    values=[ALL_REGIONS],
    state="readonly",
    style="Modern.TCombobox",
)
region_combo.grid(row=1, column=1, sticky="ew", pady=4)

ttk.Label(studio, text="Giới tính", style="CardText.TLabel").grid(
    row=1, column=2, sticky="e", padx=(12, 8), pady=4
)
gender_combo = ttk.Combobox(
    studio,
    textvariable=gender_var,
    values=[ALL_GENDERS, MALE, FEMALE],
    state="readonly",
    style="Modern.TCombobox",
)
gender_combo.grid(row=1, column=3, sticky="ew", pady=4)

ttk.Label(studio, text="Đang chọn", style="CardText.TLabel").grid(
    row=1, column=4, sticky="e", padx=(12, 8), pady=4
)
ttk.Label(studio, textvariable=voice_info_var, style="CardValue.TLabel").grid(
    row=1, column=5, sticky="w", padx=(0, 16), pady=4
)

# Row 2: preset and blend.
ttk.Label(studio, text="Preset", style="CardText.TLabel").grid(
    row=2, column=0, sticky="w", padx=(16, 8), pady=4
)
preset_combo = ttk.Combobox(
    studio,
    textvariable=app.preset_var,
    values=list(PRESETS),
    state="readonly",
    style="Modern.TCombobox",
)
preset_combo.grid(row=2, column=1, sticky="ew", pady=4)

ttk.Label(studio, text="Blend voice", style="CardText.TLabel").grid(
    row=2, column=2, sticky="e", padx=(12, 8), pady=4
)
blend_combo = ttk.Combobox(
    studio,
    textvariable=app.blend_voice_var,
    values=[NO_BLEND],
    state="readonly",
    style="Modern.TCombobox",
)
blend_combo.grid(row=2, column=3, sticky="ew", pady=4)

blend_frame = ttk.Frame(studio, style="Card.TFrame")
blend_frame.grid(row=2, column=4, columnspan=2, sticky="ew", padx=(12, 16), pady=4)
blend_frame.columnconfigure(0, weight=1)
ttk.Scale(
    blend_frame,
    from_=0,
    to=50,
    variable=app.blend_percent_var,
    style="Modern.Horizontal.TScale",
).grid(row=0, column=0, sticky="ew")
ttk.Label(blend_frame, textvariable=blend_label_var, width=5, style="CardValue.TLabel").grid(
    row=0, column=1, padx=(8, 0)
)

# Row 3: pause controls and normalization.
ttk.Label(studio, text="Nghỉ dấu chấm", style="CardText.TLabel").grid(
    row=3, column=0, sticky="w", padx=(16, 8), pady=(4, 12)
)
sentence_frame = ttk.Frame(studio, style="Card.TFrame")
sentence_frame.grid(row=3, column=1, sticky="ew", pady=(4, 12))
sentence_frame.columnconfigure(0, weight=1)
ttk.Scale(
    sentence_frame,
    from_=0.0,
    to=0.8,
    variable=app.sentence_pause_var,
    style="Modern.Horizontal.TScale",
).grid(row=0, column=0, sticky="ew")
ttk.Label(sentence_frame, textvariable=sentence_label_var, width=6, style="CardValue.TLabel").grid(
    row=0, column=1, padx=(8, 0)
)

ttk.Label(studio, text="Nghỉ dấu phẩy", style="CardText.TLabel").grid(
    row=3, column=2, sticky="e", padx=(12, 8), pady=(4, 12)
)
clause_frame = ttk.Frame(studio, style="Card.TFrame")
clause_frame.grid(row=3, column=3, sticky="ew", pady=(4, 12))
clause_frame.columnconfigure(0, weight=1)
ttk.Scale(
    clause_frame,
    from_=0.0,
    to=0.4,
    variable=app.clause_pause_var,
    style="Modern.Horizontal.TScale",
).grid(row=0, column=0, sticky="ew")
ttk.Label(clause_frame, textvariable=clause_label_var, width=6, style="CardValue.TLabel").grid(
    row=0, column=1, padx=(8, 0)
)

normalize_check = tk.Checkbutton(
    studio,
    text="Normalize âm lượng từng scene",
    variable=app.normalize_var,
    bg="#111827",
    fg="#f8fafc",
    activebackground="#111827",
    activeforeground="#f8fafc",
    selectcolor="#0f172a",
    highlightthickness=0,
    bd=0,
)
normalize_check.grid(row=3, column=4, columnspan=2, sticky="e", padx=(12, 16), pady=(4, 12))

all_voices: list[str] = []
last_applied: tuple[str, ...] = ()


def refresh_labels(*_args) -> None:
    blend_label_var.set(f"{app.blend_percent_var.get():.0f}%")
    sentence_label_var.set(f"{app.sentence_pause_var.get():.2f}s")
    clause_label_var.set(f"{app.clause_pause_var.get():.2f}s")


app.blend_percent_var.trace_add("write", refresh_labels)
app.sentence_pause_var.trace_add("write", refresh_labels)
app.clause_pause_var.trace_add("write", refresh_labels)
refresh_labels()


def update_voice_info(_event=None) -> None:
    voice = app.voice_var.get().strip()
    if not voice:
        voice_info_var.set("Không có voice phù hợp")
        return
    region, gender, lang = voice_meta(voice)
    voice_info_var.set(f"{gender} · {region} · {voice}")
    app.lang_var.set(lang)


def apply_filters(prefer: str | None = None) -> None:
    global last_applied
    region = region_var.get()
    gender = gender_var.get()
    filtered = [
        voice
        for voice in all_voices
        if (region == ALL_REGIONS or voice_meta(voice)[0] == region)
        and (gender == ALL_GENDERS or voice_meta(voice)[1] == gender)
    ]
    app.voice_combo["values"] = filtered
    last_applied = tuple(filtered)
    current = app.voice_var.get().strip()
    if current not in filtered:
        if prefer and prefer in filtered:
            app.voice_var.set(prefer)
        elif filtered:
            app.voice_var.set(filtered[0])
        else:
            app.voice_var.set("")
    update_voice_info()


def apply_preset(_event=None) -> None:
    preset = PRESETS.get(app.preset_var.get(), PRESETS["Natural"])
    app.speed_var.set(float(preset["speed"]))
    app.sentence_pause_var.set(float(preset["sentence"]))
    app.clause_pause_var.set(float(preset["clause"]))
    app.blend_percent_var.set(float(preset["blend"]))
    app.normalize_var.set(True)
    app._append_log(
        f"Preset {app.preset_var.get()}: speed {preset['speed']:.2f}x · pause {preset['sentence']:.2f}/{preset['clause']:.2f}s · blend {preset['blend']}%"
    )


region_combo.bind("<<ComboboxSelected>>", lambda _e: apply_filters())
gender_combo.bind("<<ComboboxSelected>>", lambda _e: apply_filters())
preset_combo.bind("<<ComboboxSelected>>", apply_preset)
app.voice_combo.bind("<<ComboboxSelected>>", update_voice_info, add="+")


def watch_voice_catalog() -> None:
    global all_voices, last_applied
    current = tuple(app.voice_combo["values"])

    if current and current != last_applied and current != tuple(all_voices):
        all_voices = list(current)
        regions = sorted({voice_meta(v)[0] for v in all_voices})
        genders = [
            g
            for g in (MALE, FEMALE, UNKNOWN)
            if any(voice_meta(v)[1] == g for v in all_voices)
        ]
        region_combo["values"] = [ALL_REGIONS] + regions
        gender_combo["values"] = [ALL_GENDERS] + genders
        blend_combo["values"] = [NO_BLEND] + all_voices
        region_var.set(ALL_REGIONS)
        gender_var.set(ALL_GENDERS)
        if app.blend_voice_var.get() not in ([NO_BLEND] + all_voices):
            app.blend_voice_var.set(NO_BLEND)
        apply_filters(prefer=DEFAULT_VOICE)

        male_count = sum(voice_meta(v)[1] == MALE for v in all_voices)
        female_count = sum(voice_meta(v)[1] == FEMALE for v in all_voices)
        app._append_log(
            f"Voice catalog: {len(all_voices)} voice · {male_count} nam · {female_count} nữ."
        )

    elif not current and all_voices:
        all_voices = []
        last_applied = ()
        blend_combo["values"] = [NO_BLEND]
        app.blend_voice_var.set(NO_BLEND)
        voice_info_var.set("Đang chờ danh sách voice…")

    app.after(250, watch_voice_catalog)


def auto_load() -> None:
    selected_model = Path(app.model_var.get()) if app.model_var.get() else model_path
    if selected_model.is_file() and VOICES_PATH.is_file():
        app.load_model()


app.after(150, watch_voice_catalog)
app.after(180, auto_load)
app.mainloop()
