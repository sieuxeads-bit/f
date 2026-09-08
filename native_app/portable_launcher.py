from pathlib import Path
import os
import subprocess
import sys
import time
import tkinter as tk
from tkinter import ttk

import numpy as np
import soundfile as sf

from app import (
    AUTO_DEVICE,
    KokoroSrtApp,
    available_providers,
    make_kokoro,
    provider_label,
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

# prefix -> (display region/language, gender, phonemizer language)
# Current voices-v1.0.bin has US + UK. Extra mappings are ready for newer Kokoro bundles.
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


def meta(voice_id: str) -> tuple[str, str, str]:
    key = voice_id[:2].lower()
    if key in VOICE_PREFIXES:
        return VOICE_PREFIXES[key]
    gender = FEMALE if len(voice_id) > 1 and voice_id[1].lower() == "f" else MALE if len(voice_id) > 1 and voice_id[1].lower() == "m" else UNKNOWN
    return "🌐 Khác / không rõ", gender, "en-us"


class PortableKokoroSrtApp(KokoroSrtApp):
    """Portable wrapper with voice filters and per-scene dubbing export."""

    def option_add(self, pattern, value, priority=None):
        if pattern == "*Font" and value == "Segoe UI 10":
            value = "{Segoe UI} 10"
        if priority is None:
            return super().option_add(pattern, value)
        return super().option_add(pattern, value, priority)

    def start_generate(self) -> None:
        # Capture this on the Tk main thread. Every SRT gets its own standard
        # dubbing folder beside the subtitle file.
        srt_text = self.srt_var.get().strip()
        if srt_text:
            self._dubbing_dir = str(Path(srt_text).expanduser().parent / "2_Dubbing_Audio")
        else:
            self._dubbing_dir = ""
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
                self._loaded_signature = (str(model), str(voices), self._backend_provider)

            assert self._kokoro is not None
            provider = self._backend_provider or provider
            available = list(self._kokoro.get_voices())
            voice = requested_voice or (available[0] if available else "")
            if not voice:
                raise RuntimeError("Không tìm thấy voice trong voices .bin.")
            if available and voice not in available:
                raise RuntimeError(f"Voice không tồn tại: {voice}")

            voice_style = self._kokoro.get_voice_style(voice)
            started = time.perf_counter()
            sample_rate: int | None = None
            cursor_sample = 0
            chunks: list[tuple[int, np.ndarray]] = []
            generated_audio_samples = 0
            total = len(cues)

            dubbing_dir_text = getattr(self, "_dubbing_dir", "")
            dubbing_dir = Path(dubbing_dir_text) if dubbing_dir_text else output.parent / "2_Dubbing_Audio"
            dubbing_dir.mkdir(parents=True, exist_ok=True)

            # Remove only scene audio produced by this tool so rerunning with a
            # shorter SRT cannot leave stale scene_XXX_audio.wav files behind.
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
                    self._events.put(("status", f"Đang tạo scene {scene_index:03d} · {i}/{total}…"))

                samples, sr = self._kokoro.create(
                    cue.text,
                    voice=voice_style,
                    speed=speed,
                    lang=lang,
                    trim=True,
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

                assert sample_rate is not None

                # One clean audio file per SRT cue.
                scene_path = dubbing_dir / f"scene_{scene_index:03d}_audio.wav"
                sf.write(str(scene_path), samples, sample_rate, subtype="PCM_16")

                requested_start = max(0, int(round(cue.start * sample_rate)))
                start_sample = max(requested_start, cursor_sample)
                chunks.append((start_sample, samples))
                cursor_sample = start_sample + len(samples)
                generated_audio_samples += len(samples)

                if start_sample > requested_start and (i == 1 or i % 10 == 0):
                    delay = (start_sample - requested_start) / sample_rate
                    self._events.put(("log", f"Scene {scene_index:03d}: dời +{delay:.2f}s trong WAV tổng để tránh chồng giọng."))
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

            # Keep the mixed WAV as a convenient full-track preview/export.
            output.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output), timeline, sample_rate, subtype="PCM_16")

            elapsed = max(time.perf_counter() - started, 1e-6)
            generated_seconds = generated_audio_samples / sample_rate
            speed_x = generated_seconds / elapsed
            self._events.put(("log", f"Đã xuất {total} scene vào: {dubbing_dir}"))
            self._events.put(("done", {
                "output": str(output),
                "dubbing_dir": str(dubbing_dir),
                "elapsed": elapsed,
                "generated_seconds": generated_seconds,
                "speed_x": speed_x,
                "provider": provider,
                "cues": total,
            }))
        except Exception as exc:
            self._events.put(("error", f"Lỗi tạo voice: {exc}"))

    def open_output_folder(self) -> None:
        srt_text = self.srt_var.get().strip()
        if srt_text:
            folder = Path(srt_text).expanduser().parent / "2_Dubbing_Audio"
        else:
            output = self.output_var.get().strip()
            folder = Path(output).expanduser().parent / "2_Dubbing_Audio" if output else Path.cwd()
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
            from tkinter import messagebox
            messagebox.showerror("Không mở được thư mục", str(exc))


providers = set(available_providers())
has_gpu = "CUDAExecutionProvider" in providers or "DmlExecutionProvider" in providers
model_path = FP16_MODEL if has_gpu and FP16_MODEL.is_file() else INT8_MODEL

app = PortableKokoroSrtApp()
app.speed_var.set(1.0)
app.device_var.set(AUTO_DEVICE)

if model_path.is_file():
    app.model_var.set(str(model_path))
if VOICES_PATH.is_file():
    app.voices_var.set(str(VOICES_PATH))

app._device_changed()

# Add a country/gender filter card without changing Kokoro's actual voice IDs.
root = app.winfo_children()[0]
children = root.winfo_children()
before_widget = children[4] if len(children) > 4 else None
filter_card = ttk.Frame(root, style="Card.TFrame")
pack_args = {"fill": "x", "pady": (0, 10)}
if before_widget is not None:
    pack_args["before"] = before_widget
filter_card.pack(**pack_args)

region_var = tk.StringVar(value=ALL_REGIONS)
gender_var = tk.StringVar(value=ALL_GENDERS)
voice_info_var = tk.StringVar(value="Đang chờ danh sách voice…")

ttk.Label(filter_card, text="Lọc voice", style="CardTitle.TLabel").grid(
    row=0, column=0, columnspan=6, sticky="w", padx=16, pady=(12, 7)
)
filter_card.columnconfigure(1, weight=1)
filter_card.columnconfigure(3, weight=1)
filter_card.columnconfigure(5, weight=2)

ttk.Label(filter_card, text="Quốc gia / accent", style="CardText.TLabel").grid(
    row=1, column=0, sticky="w", padx=(16, 8), pady=5
)
region_combo = ttk.Combobox(
    filter_card,
    textvariable=region_var,
    values=[ALL_REGIONS],
    state="readonly",
    style="Modern.TCombobox",
)
region_combo.grid(row=1, column=1, sticky="ew", pady=5)

ttk.Label(filter_card, text="Giới tính", style="CardText.TLabel").grid(
    row=1, column=2, sticky="e", padx=(14, 8), pady=5
)
gender_combo = ttk.Combobox(
    filter_card,
    textvariable=gender_var,
    values=[ALL_GENDERS, MALE, FEMALE],
    state="readonly",
    style="Modern.TCombobox",
)
gender_combo.grid(row=1, column=3, sticky="ew", pady=5)

ttk.Label(filter_card, text="Voice đang chọn", style="CardText.TLabel").grid(
    row=1, column=4, sticky="e", padx=(14, 8), pady=5
)
ttk.Label(filter_card, textvariable=voice_info_var, style="CardValue.TLabel").grid(
    row=1, column=5, sticky="w", padx=(0, 16), pady=5
)
ttk.Label(
    filter_card,
    text="♂ = Nam · ♀ = Nữ. Chọn quốc gia sẽ tự đổi Language phù hợp.",
    style="CardText.TLabel",
).grid(row=2, column=0, columnspan=6, sticky="w", padx=16, pady=(3, 12))

all_voices: list[str] = []
last_applied: tuple[str, ...] = ()


def update_voice_info(_event=None) -> None:
    voice = app.voice_var.get().strip()
    if not voice:
        voice_info_var.set("Không có voice phù hợp")
        return
    region, gender, lang = meta(voice)
    voice_info_var.set(f"{gender} · {region} · {voice}")
    app.lang_var.set(lang)


def apply_filters(prefer: str | None = None) -> None:
    global last_applied
    region = region_var.get()
    gender = gender_var.get()
    filtered = [
        v for v in all_voices
        if (region == ALL_REGIONS or meta(v)[0] == region)
        and (gender == ALL_GENDERS or meta(v)[1] == gender)
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


def filter_changed(_event=None) -> None:
    apply_filters()


region_combo.bind("<<ComboboxSelected>>", filter_changed)
gender_combo.bind("<<ComboboxSelected>>", filter_changed)
app.voice_combo.bind("<<ComboboxSelected>>", update_voice_info, add="+")


def watch_voice_catalog() -> None:
    global all_voices, last_applied
    current = tuple(app.voice_combo["values"])

    if current and current != last_applied and current != tuple(all_voices):
        all_voices = list(current)
        regions = sorted({meta(v)[0] for v in all_voices})
        genders = [g for g in (MALE, FEMALE, UNKNOWN) if any(meta(v)[1] == g for v in all_voices)]
        region_combo["values"] = [ALL_REGIONS] + regions
        gender_combo["values"] = [ALL_GENDERS] + genders
        region_var.set(ALL_REGIONS)
        gender_var.set(ALL_GENDERS)
        apply_filters(prefer=DEFAULT_VOICE)

        male_count = sum(meta(v)[1] == MALE for v in all_voices)
        female_count = sum(meta(v)[1] == FEMALE for v in all_voices)
        voice_info_var.set(
            f"{len(all_voices)} voice · ♂ {male_count} nam · ♀ {female_count} nữ"
        )
        app.after(900, update_voice_info)

    elif not current and all_voices:
        all_voices = []
        last_applied = ()
        voice_info_var.set("Đang chờ danh sách voice…")

    app.after(250, watch_voice_catalog)


def auto_load() -> None:
    selected_model = Path(app.model_var.get()) if app.model_var.get() else model_path
    if selected_model.is_file() and VOICES_PATH.is_file():
        app.load_model()


app.after(150, watch_voice_catalog)
app.after(180, auto_load)
app.mainloop()
