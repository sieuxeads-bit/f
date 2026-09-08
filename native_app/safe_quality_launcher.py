from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CORE = BASE_DIR / "safe_quality_core.py"

# Build the stable Clean R2 + parallel core, then add the R3 Scene Workflow
# before entering Tk mainloop. Keeping this wrapper small makes future workflow
# changes independent from the tested clean renderer.
source = CORE.read_text(encoding="utf-8")
marker = "\napp.mainloop()"
if marker not in source:
    raise RuntimeError("safe_quality_core.py layout changed: app.mainloop() not found")
source = source.rsplit(marker, 1)[0] + "\n"
namespace: dict[str, object] = {
    "__file__": str(CORE),
    "__name__": "_kokoro_clean_core_embedded",
    "__package__": None,
}
exec(compile(source, str(CORE), "exec"), namespace)

app = namespace["app"]
quality_ns = namespace["ns"]
studio = quality_ns["studio"]

from scene_workflow import install_scene_workflow

install_scene_workflow(app, quality_ns, studio)

try:
    app.title("Kokoro SRT Studio · CLEAN R3 WORKFLOW")
except Exception:
    pass

app._append_log(
    "CLEAN R3 WORKFLOW: auto detect/retry rè · cache/resume · preview/regenerate scene · parallel 1–10."
)
app.mainloop()
