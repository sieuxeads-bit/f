from __future__ import annotations

import json
import os
import re
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk


BASE_DIR = Path(__file__).resolve().parent
STUDIO_LAUNCHER = BASE_DIR / "studio_launcher.py"

# Run the existing Studio launcher but take over the final Tk mainloop so this
# wrapper can add persistent profile controls without duplicating the TTS code.
source = STUDIO_LAUNCHER.read_text(encoding="utf-8")
marker = "\napp.mainloop()"
if marker not in source:
    raise RuntimeError("studio_launcher.py layout changed: app.mainloop() not found")
source = source.rsplit(marker, 1)[0] + "\n"
namespace: dict[str, object] = {
    "__file__": str(STUDIO_LAUNCHER),
    "__name__": "_kokoro_studio_embedded",
    "__package__": None,
}
exec(compile(source, str(STUDIO_LAUNCHER), "exec"), namespace)

app = namespace["app"]
studio = namespace["studio"]
region_var = namespace["region_var"]
gender_var = namespace["gender_var"]
region_combo = namespace["region_combo"]
gender_combo = namespace["gender_combo"]
NO_BLEND = namespace["NO_BLEND"]
ALL_REGIONS = namespace["ALL_REGIONS"]
ALL_GENDERS = namespace["ALL_GENDERS"]

LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
PROFILE_DIR = LOCALAPPDATA / "KokoroSRT" / "profiles"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
LAST_FILE = PROFILE_DIR / "_last_session.json"

profile_var = tk.StringVar(value="")
_profile_paths: dict[str, Path] = {}
_profile_loading = False
_autosave_enabled = False
_autosave_job: str | None = None


def current_state(name: str = "") -> dict[str, object]:
    return {
        "version": 1,
        "name": name,
        "region": region_var.get(),
        "gender": gender_var.get(),
        "voice": app.voice_var.get().strip(),
        "preset": app.preset_var.get().strip() or "Natural",
        "blend_voice": app.blend_voice_var.get().strip(),
        "blend_percent": float(app.blend_percent_var.get()),
        "speed": float(app.speed_var.get()),
        "sentence_pause": float(app.sentence_pause_var.get()),
        "clause_pause": float(app.clause_pause_var.get()),
        "normalize": bool(app.normalize_var.get()),
        "device": app.device_var.get().strip(),
        "lang": app.lang_var.get().strip(),
    }


def write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def read_json(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def safe_profile_filename(name: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip(" ._")
    clean = re.sub(r"\s+", " ", clean)
    return (clean or "profile")[:80] + ".json"


def refresh_profile_list() -> None:
    global _profile_paths
    entries: list[tuple[str, Path]] = []
    for path in PROFILE_DIR.glob("*.json"):
        if path.name.startswith("_"):
            continue
        data = read_json(path)
        display = str((data or {}).get("name") or path.stem)
        entries.append((display, path))
    entries.sort(key=lambda item: item[0].lower())
    _profile_paths = dict(entries)
    profile_combo["values"] = [name for name, _ in entries]
    if profile_var.get() not in _profile_paths:
        profile_var.set("")


def all_voices() -> list[str]:
    voices = namespace.get("all_voices", [])
    return list(voices) if isinstance(voices, list) else []


def apply_state(data: dict[str, object], *, announce: bool, retries: int = 100) -> None:
    global _profile_loading, _autosave_enabled
    _profile_loading = True

    try:
        desired_device = str(data.get("device") or app.device_var.get())
        device_values = list(app.device_combo["values"])
        if desired_device in device_values and desired_device != app.device_var.get():
            app.device_var.set(desired_device)
            app._device_changed()
            auto_load = namespace.get("auto_load")
            if callable(auto_load):
                app.after(80, auto_load)

        app.preset_var.set(str(data.get("preset") or "Natural"))
        app.speed_var.set(float(data.get("speed", 1.0)))
        app.blend_percent_var.set(float(data.get("blend_percent", 0.0)))
        app.sentence_pause_var.set(float(data.get("sentence_pause", 0.25)))
        app.clause_pause_var.set(float(data.get("clause_pause", 0.10)))
        app.normalize_var.set(bool(data.get("normalize", True)))
    except (TypeError, ValueError, tk.TclError):
        pass

    voices = all_voices()
    if not voices and retries > 0:
        app.after(250, lambda: apply_state(data, announce=announce, retries=retries - 1))
        return

    try:
        region = str(data.get("region") or ALL_REGIONS)
        gender = str(data.get("gender") or ALL_GENDERS)
        region_values = list(region_combo["values"])
        gender_values = list(gender_combo["values"])
        region_var.set(region if region in region_values else ALL_REGIONS)
        gender_var.set(gender if gender in gender_values else ALL_GENDERS)

        desired_voice = str(data.get("voice") or "")
        apply_filters = namespace.get("apply_filters")
        if callable(apply_filters):
            apply_filters(prefer=desired_voice or None)
        if desired_voice in voices and desired_voice in list(app.voice_combo["values"]):
            app.voice_var.set(desired_voice)

        desired_blend = str(data.get("blend_voice") or NO_BLEND)
        blend_values = list(namespace["blend_combo"]["values"])
        app.blend_voice_var.set(desired_blend if desired_blend in blend_values else NO_BLEND)

        update_voice_info = namespace.get("update_voice_info")
        if callable(update_voice_info):
            update_voice_info()
        saved_lang = str(data.get("lang") or "").strip()
        if saved_lang:
            app.lang_var.set(saved_lang)

        if announce:
            app._append_log(
                f"Đã tải profile: {data.get('name') or profile_var.get() or 'voice settings'}"
            )
    finally:
        _profile_loading = False
        _autosave_enabled = True
        save_last_session()


def save_last_session() -> None:
    if _profile_loading:
        return
    try:
        write_json(LAST_FILE, current_state("Last session"))
    except OSError:
        pass


def schedule_autosave(*_args) -> None:
    global _autosave_job
    if not _autosave_enabled or _profile_loading:
        return
    if _autosave_job is not None:
        try:
            app.after_cancel(_autosave_job)
        except tk.TclError:
            pass
    _autosave_job = app.after(600, save_last_session)


def save_profile() -> None:
    suggested = " ".join(
        part for part in (app.voice_var.get().strip(), app.preset_var.get().strip()) if part
    ) or "Voice profile"
    name = simpledialog.askstring(
        "Lưu Voice Profile",
        "Tên profile:",
        initialvalue=suggested,
        parent=app,
    )
    if not name or not name.strip():
        return
    name = name.strip()
    path = PROFILE_DIR / safe_profile_filename(name)
    if path.exists() and not messagebox.askyesno(
        "Ghi đè profile?",
        f"Profile '{name}' đã tồn tại. Ghi đè?",
        parent=app,
    ):
        return
    try:
        write_json(path, current_state(name))
        profile_var.set(name)
        refresh_profile_list()
        profile_var.set(name)
        save_last_session()
        app._append_log(f"Đã lưu profile: {name}")
    except OSError as exc:
        messagebox.showerror("Không lưu được profile", str(exc), parent=app)


def load_selected_profile() -> None:
    name = profile_var.get().strip()
    path = _profile_paths.get(name)
    if path is None:
        messagebox.showinfo("Voice Profile", "Chọn một profile đã lưu trước.", parent=app)
        return
    data = read_json(path)
    if data is None:
        messagebox.showerror("Voice Profile", "Profile bị lỗi hoặc không đọc được.", parent=app)
        return
    apply_state(data, announce=True)


def delete_selected_profile() -> None:
    name = profile_var.get().strip()
    path = _profile_paths.get(name)
    if path is None:
        return
    if not messagebox.askyesno(
        "Xóa profile?",
        f"Xóa profile '{name}'?",
        parent=app,
    ):
        return
    try:
        path.unlink(missing_ok=True)
        profile_var.set("")
        refresh_profile_list()
        app._append_log(f"Đã xóa profile: {name}")
    except OSError as exc:
        messagebox.showerror("Không xóa được profile", str(exc), parent=app)


# Add profile controls as the final row of VOICE STUDIO.
profile_row = ttk.Frame(studio, style="Card.TFrame")
profile_row.grid(row=4, column=0, columnspan=6, sticky="ew", padx=16, pady=(0, 12))
profile_row.columnconfigure(1, weight=1)

ttk.Label(profile_row, text="Profile", style="CardText.TLabel").grid(
    row=0, column=0, sticky="w", padx=(0, 8)
)
profile_combo = ttk.Combobox(
    profile_row,
    textvariable=profile_var,
    values=[],
    state="readonly",
    style="Modern.TCombobox",
)
profile_combo.grid(row=0, column=1, sticky="ew")

ttk.Button(
    profile_row,
    text="Lưu profile",
    style="Accent.TButton",
    command=save_profile,
).grid(row=0, column=2, padx=(10, 6))
ttk.Button(
    profile_row,
    text="Tải",
    style="Ghost.TButton",
    command=load_selected_profile,
).grid(row=0, column=3, padx=6)
ttk.Button(
    profile_row,
    text="Xóa",
    style="Ghost.TButton",
    command=delete_selected_profile,
).grid(row=0, column=4, padx=(6, 0))
profile_combo.bind("<<ComboboxSelected>>", lambda _event: load_selected_profile())

refresh_profile_list()

# Remember all voice-studio changes between app launches.
tracked_vars = [
    region_var,
    gender_var,
    app.voice_var,
    app.preset_var,
    app.blend_voice_var,
    app.blend_percent_var,
    app.speed_var,
    app.sentence_pause_var,
    app.clause_pause_var,
    app.normalize_var,
    app.device_var,
    app.lang_var,
]
for variable in tracked_vars:
    variable.trace_add("write", schedule_autosave)


def restore_last_session(retries: int = 100) -> None:
    global _autosave_enabled
    data = read_json(LAST_FILE)
    if data is None:
        _autosave_enabled = True
        return
    if not all_voices() and retries > 0:
        app.after(250, lambda: restore_last_session(retries - 1))
        return
    apply_state(data, announce=False)


def on_close() -> None:
    save_last_session()
    app.destroy()


app.protocol("WM_DELETE_WINDOW", on_close)
app.after(300, restore_last_session)
app.mainloop()
