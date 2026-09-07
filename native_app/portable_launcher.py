from pathlib import Path
import os

from app import AUTO_DEVICE, KokoroSrtApp, available_providers


BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get("KOKORO_MODEL_DIR", BASE_DIR / "models"))
INT8_MODEL = MODEL_DIR / "kokoro-v1.0.int8.onnx"
FP16_MODEL = MODEL_DIR / "kokoro-v1.0.fp16.onnx"
VOICES_PATH = MODEL_DIR / "voices-v1.0.bin"
DEFAULT_VOICE = "am_michael"


providers = set(available_providers())
has_gpu = "CUDAExecutionProvider" in providers or "DmlExecutionProvider" in providers
model_path = FP16_MODEL if has_gpu and FP16_MODEL.is_file() else INT8_MODEL

app = KokoroSrtApp()
app.speed_var.set(1.0)
app.device_var.set(AUTO_DEVICE)

if model_path.is_file():
    app.model_var.set(str(model_path))
if VOICES_PATH.is_file():
    app.voices_var.set(str(VOICES_PATH))

app._device_changed()


def select_default_voice() -> None:
    values = list(app.voice_combo["values"])
    if values:
        if DEFAULT_VOICE in values:
            app.voice_var.set(DEFAULT_VOICE)
        return
    app.after(250, select_default_voice)


def auto_load() -> None:
    selected_model = Path(app.model_var.get()) if app.model_var.get() else model_path
    if selected_model.is_file() and VOICES_PATH.is_file():
        app.load_model()
        app.after(250, select_default_voice)


app.after(180, auto_load)
app.mainloop()
