from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SAFE_LAUNCHER = BASE_DIR / "safe_quality_launcher.py"

# Build the existing Clean R2 + parallel-render app, but take over its final
# mainloop so Scene Workflow can add cache/resume, auto static retry and
# per-scene preview/regenerate without duplicating the stable UI/backend layers.
source = SAFE_LAUNCHER.read_text(encoding="utf-8")
marker = "\napp.mainloop()"
if marker not in source:
    raise RuntimeError("safe_quality_launcher.py layout changed: app.mainloop() not found")
source = source.rsplit(marker, 1)[0] + "\n"
namespace: dict[str, object] = {
    "__file__": str(SAFE_LAUNCHER),
    "__name__": "_kokoro_safe_embedded",
    "__package__": None,
}
exec(compile(source, str(SAFE_LAUNCHER), "exec"), namespace)

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
