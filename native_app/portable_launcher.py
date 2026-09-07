import os
from pathlib import Path

from app import KokoroSrtApp


BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get("KOKORO_MODEL_DIR", str(BASE_DIR / "models")))
MODEL_PATH = MODEL_DIR / "kokoro-v1.0.int8.onnx"
VOICES_PATH = MODEL_DIR / "voices-v1.0.bin"
DEFAULT_VOICE = "am_michael"


app = KokoroSrtApp()

# Natural speech speed. No SRT compression is used.
app.speed_var.set(1.0)

if MODEL_PATH.is_file():
    app.model_var.set(str(MODEL_PATH))
if VOICES_PATH.is_file():
    app.voices_var.set(str(VOICES_PATH))


def select_default_voice() -> None:
    values = list(app.voice_combo["values"])
    if values:
        if DEFAULT_VOICE in values:
            app.voice_var.set(DEFAULT_VOICE)
        return
    app.after(250, select_default_voice)


def auto_load() -> None:
    if MODEL_PATH.is_file() and VOICES_PATH.is_file():
        app.load_model()
        app.after(250, select_default_voice)


app.after(150, auto_load)
app.mainloop()
