from __future__ import annotations

import types
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
QUALITY_LAUNCHER = BASE_DIR / "quality_launcher.py"

# Build the full Quality/Profile UI but take over the final mainloop.  The
# experimental multi-cue context renderer sounded expressive, but splitting a
# synthesized paragraph back into independent dubbing scenes can introduce
# rough/stuttered artifacts.  The default renderer below keeps the expressive
# text/pause/speed controls while synthesizing every SRT cue independently.
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

CLEAN_MODE = "Clean Emotional (khuyên dùng)"

# Any mode other than QUALITY_HIGH uses the stable per-scene path inside the
# quality worker.  It still applies Smart Text, pronunciation rules, adaptive
# expression, voice blend, pause controls, normalization and natural edges.
quality_combo["values"] = [CLEAN_MODE, QUALITY_BALANCED]
context_combo["values"] = [1]
app.quality_mode_var.set(CLEAN_MODE)
app.context_cues_var.set(1)

_original_start_generate = app.start_generate


def clean_start_generate(self) -> None:
    # Never let an older profile silently restore multi-cue context right before
    # rendering.  This is the important quality fix: one cue -> one model pass ->
    # one scene WAV.  No phoneme-boundary slicing and no sliding-window joins.
    if self.quality_mode_var.get() == CLEAN_MODE:
        self.context_cues_var.set(1)
    _original_start_generate()


app.start_generate = types.MethodType(clean_start_generate, app)
app.run_btn.configure(command=app.start_generate)


def restore_clean_default() -> None:
    # profile_launcher restores the previous session shortly after startup.  A
    # profile made with the experimental High Prosody mode may therefore put the
    # old value back.  Convert that startup state to the clean renderer once.
    current = str(app.quality_mode_var.get())
    if current not in (CLEAN_MODE, QUALITY_BALANCED):
        app.quality_mode_var.set(CLEAN_MODE)
    app.context_cues_var.set(1)


app.after(1400, restore_clean_default)
app._append_log(
    "Clean Emotional: mỗi cue synth độc lập · context split OFF · continuous OFF · cảm xúc/Smart Text vẫn ON."
)
app.mainloop()
