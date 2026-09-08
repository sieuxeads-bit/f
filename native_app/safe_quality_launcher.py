from __future__ import annotations

import os
import types
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
QUALITY_LAUNCHER = BASE_DIR / "quality_launcher.py"

# Build the full Quality/Profile UI but take over the final mainloop.  The
# expressive controls remain, but Clean Emotional deliberately uses one SRT cue
# per model pass and the full-precision Kokoro model to avoid FP16 static/noise.
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

CLEAN_MODE = "Clean Emotional FP32 (khuyên dùng)"
FAST_MODE = "Fast Emotional FP16"

# Both modes synthesize each scene independently.  Clean mode forces FP32; Fast
# mode lets the existing launcher/provider choose FP16/INT8 for speed.
quality_combo["values"] = [CLEAN_MODE, FAST_MODE, QUALITY_BALANCED]
context_combo["values"] = [1]
app.quality_mode_var.set(CLEAN_MODE)
app.context_cues_var.set(1)

_original_start_generate = app.start_generate


def clean_start_generate(self) -> None:
    self.context_cues_var.set(1)
    mode = str(self.quality_mode_var.get())
    if mode == CLEAN_MODE:
        if not FULL_PRECISION_MODEL.is_file():
            from tkinter import messagebox

            messagebox.showerror(
                "Thiếu model FP32",
                "Chưa có Kokoro FP32 clean model. Đóng app rồi chạy lại START_PORTABLE.bat để tải model khoảng 326 MB.",
                parent=self,
            )
            return
        # Force full precision right before rendering so an older profile cannot
        # silently restore the FP16 model path.  The worker signature notices the
        # changed path and reloads the ONNX session automatically.
        self.model_var.set(str(FULL_PRECISION_MODEL))
    _original_start_generate()


app.start_generate = types.MethodType(clean_start_generate, app)
app.run_btn.configure(command=app.start_generate)


def restore_clean_default() -> None:
    # profile_launcher restores the previous session shortly after startup.
    current = str(app.quality_mode_var.get())
    if current not in (CLEAN_MODE, FAST_MODE, QUALITY_BALANCED):
        app.quality_mode_var.set(CLEAN_MODE)
    app.context_cues_var.set(1)


app.after(1400, restore_clean_default)
app._append_log(
    "Clean Emotional FP32: mỗi cue synth độc lập · context/continuous OFF · full precision model · cảm xúc/Smart Text vẫn ON."
)
app.mainloop()
