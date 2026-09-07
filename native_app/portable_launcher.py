from pathlib import Path
import os
import tkinter as tk
from tkinter import ttk

from app import AUTO_DEVICE, KokoroSrtApp, available_providers


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
    """Portable wrapper with a Tcl-safe default font declaration on Windows."""

    def option_add(self, pattern, value, priority=None):
        if pattern == "*Font" and value == "Segoe UI 10":
            value = "{Segoe UI} 10"
        if priority is None:
            return super().option_add(pattern, value)
        return super().option_add(pattern, value, priority)


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
