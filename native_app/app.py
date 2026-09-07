from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
import onnxruntime as ort
import soundfile as sf
from kokoro_onnx import Kokoro


APP_BG = "#0b1020"
CARD_BG = "#111827"
CARD_ALT = "#172033"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
ACCENT = "#22c55e"
ACCENT_HOVER = "#16a34a"
BORDER = "#263248"
ENTRY_BG = "#0f172a"

AUTO_DEVICE = "Auto (GPU ưu tiên)"
CUDA_DEVICE = "NVIDIA CUDA"
DML_DEVICE = "Windows DirectML"
CPU_DEVICE = "CPU"


@dataclass
class Cue:
    index: int
    start: float
    end: float
    text: str


def parse_time(value: str) -> float:
    h, m, rest = value.strip().replace(".", ",").split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(path: Path) -> list[Cue]:
    text = path.read_text(encoding="utf-8-sig", errors="replace").replace("\r", "").strip()
    if not text:
        return []

    pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
        r"(\d{2}:\d{2}:\d{2}[,.]\d{3})"
    )
    cues: list[Cue] = []

    for fallback_index, block in enumerate(re.split(r"\n\s*\n", text), start=1):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        has_index = bool(re.fullmatch(r"\d+", lines[0]))
        time_pos = 1 if has_index else 0
        if len(lines) <= time_pos:
            continue

        match = pattern.search(lines[time_pos])
        if not match:
            continue

        subtitle = " ".join(lines[time_pos + 1:]).strip()
        subtitle = re.sub(r"<[^>]+>", "", subtitle)
        subtitle = re.sub(r"\{\\.*?\}", "", subtitle).strip()
        if not subtitle:
            continue

        cues.append(
            Cue(
                index=int(lines[0]) if has_index else fallback_index,
                start=parse_time(match.group(1)),
                end=parse_time(match.group(2)),
                text=subtitle,
            )
        )

    return cues


def resample_linear(samples: np.ndarray, target_length: int) -> np.ndarray:
    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    if target_length <= 0:
        return np.zeros(0, dtype=np.float32)
    if len(samples) == target_length:
        return samples
    if len(samples) <= 1:
        return np.zeros(target_length, dtype=np.float32)

    old_x = np.linspace(0.0, 1.0, len(samples), dtype=np.float64)
    new_x = np.linspace(0.0, 1.0, target_length, dtype=np.float64)
    return np.interp(new_x, old_x, samples).astype(np.float32)


def preload_ort_dlls() -> None:
    if not hasattr(ort, "preload_dlls"):
        return
    try:
        ort.preload_dlls(directory="")
    except Exception:
        pass


def available_providers() -> list[str]:
    preload_ort_dlls()
    try:
        return list(ort.get_available_providers())
    except Exception:
        return ["CPUExecutionProvider"]


def available_device_choices() -> list[str]:
    providers = set(available_providers())
    choices = [AUTO_DEVICE]
    if "CUDAExecutionProvider" in providers:
        choices.append(CUDA_DEVICE)
    if "DmlExecutionProvider" in providers:
        choices.append(DML_DEVICE)
    choices.append(CPU_DEVICE)
    return choices


def resolve_provider(device_name: str) -> str:
    providers = set(available_providers())

    if device_name == CUDA_DEVICE:
        if "CUDAExecutionProvider" not in providers:
            raise RuntimeError("CUDA chưa sẵn sàng. Chạy lại START_PORTABLE.bat để cài GPU runtime.")
        return "CUDAExecutionProvider"

    if device_name == DML_DEVICE:
        if "DmlExecutionProvider" not in providers:
            raise RuntimeError("DirectML chưa sẵn sàng trên máy này.")
        return "DmlExecutionProvider"

    if device_name == CPU_DEVICE:
        return "CPUExecutionProvider"

    if "CUDAExecutionProvider" in providers:
        return "CUDAExecutionProvider"
    if "DmlExecutionProvider" in providers:
        return "DmlExecutionProvider"
    return "CPUExecutionProvider"


def provider_label(provider: str) -> str:
    if provider == "CUDAExecutionProvider":
        return "GPU · NVIDIA CUDA"
    if provider == "DmlExecutionProvider":
        return "GPU · DirectML"
    return f"CPU · {os.cpu_count() or 1} threads"


def make_kokoro(model: Path, voices: Path, device_name: str) -> tuple[Kokoro, str]:
    preload_ort_dlls()
    provider = resolve_provider(device_name)

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.inter_op_num_threads = 1

    cpu_threads = max(1, os.cpu_count() or 4)
    if provider == "CPUExecutionProvider":
        options.intra_op_num_threads = cpu_threads
        providers: list[object] = ["CPUExecutionProvider"]
    elif provider == "CUDAExecutionProvider":
        options.intra_op_num_threads = 1
        providers = [
            (
                "CUDAExecutionProvider",
                {
                    "device_id": 0,
                    "arena_extend_strategy": "kSameAsRequested",
                    "cudnn_conv_algo_search": "DEFAULT",
                    "do_copy_in_default_stream": 1,
                },
            ),
            "CPUExecutionProvider",
        ]
    else:
        options.enable_mem_pattern = False
        options.intra_op_num_threads = 1
        providers = [("DmlExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"]

    session = ort.InferenceSession(str(model), sess_options=options, providers=providers)
    active = session.get_providers()[0] if session.get_providers() else provider
    kokoro = Kokoro.from_session(session, str(voices))
    return kokoro, active


class KokoroSrtApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Kokoro SRT Studio")
        self.geometry("1040x760")
        self.minsize(930, 680)
        self.configure(bg=APP_BG)
        self.option_add("*Font", "Segoe UI 10")

        self.model_var = tk.StringVar()
        self.voices_var = tk.StringVar()
        self.srt_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.voice_var = tk.StringVar()
        self.lang_var = tk.StringVar(value="en-us")
        self.speed_var = tk.DoubleVar(value=1.0)
        self.device_var = tk.StringVar(value=AUTO_DEVICE)
        self.status_var = tk.StringVar(value="Sẵn sàng. Chọn SRT rồi bấm Tạo voice.")
        self.progress_var = tk.DoubleVar(value=0)
        self.backend_var = tk.StringVar(value=self._initial_backend_text())
        self.perf_var = tk.StringVar(value="Chưa có benchmark")
        self.cue_var = tk.StringVar(value="0 cue")

        self._kokoro: Kokoro | None = None
        self._backend_provider: str | None = None
        self._loaded_signature: tuple[str, str, str] | None = None
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._busy = False
        self._cancel = threading.Event()

        self._configure_styles()
        self._build_ui()
        self.after(100, self._poll_events)

    def _initial_backend_text(self) -> str:
        try:
            return provider_label(resolve_provider(AUTO_DEVICE))
        except Exception:
            return "CPU"

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("Root.TFrame", background=APP_BG)
        style.configure("Header.TFrame", background=APP_BG)
        style.configure("Card.TFrame", background=CARD_BG)
        style.configure("CardAlt.TFrame", background=CARD_ALT)
        style.configure("TLabel", background=APP_BG, foreground=TEXT)
        style.configure("Title.TLabel", background=APP_BG, foreground=TEXT, font=("Segoe UI Semibold", 24))
        style.configure("Subtitle.TLabel", background=APP_BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background=CARD_BG, foreground=TEXT, font=("Segoe UI Semibold", 11))
        style.configure("CardText.TLabel", background=CARD_BG, foreground=MUTED)
        style.configure("CardValue.TLabel", background=CARD_BG, foreground=TEXT, font=("Segoe UI Semibold", 10))
        style.configure("Stat.TLabel", background=CARD_ALT, foreground=TEXT, font=("Segoe UI Semibold", 10))
        style.configure("StatMuted.TLabel", background=CARD_ALT, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Path.TLabel", background=CARD_BG, foreground=MUTED)

        style.configure("Modern.TEntry", fieldbackground=ENTRY_BG, foreground=TEXT, insertcolor=TEXT, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=8)
        style.configure("Modern.TCombobox", fieldbackground=ENTRY_BG, background=ENTRY_BG, foreground=TEXT, arrowcolor=TEXT, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=6)
        style.map("Modern.TCombobox", fieldbackground=[("readonly", ENTRY_BG)], foreground=[("readonly", TEXT)], selectbackground=[("readonly", ENTRY_BG)], selectforeground=[("readonly", TEXT)])

        style.configure("Accent.TButton", background=ACCENT, foreground="#04130a", borderwidth=0, padding=(16, 10), font=("Segoe UI Semibold", 10))
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", BORDER)])
        style.configure("Ghost.TButton", background=CARD_ALT, foreground=TEXT, borderwidth=0, padding=(12, 8))
        style.map("Ghost.TButton", background=[("active", BORDER)])
        style.configure("Danger.TButton", background="#3b1820", foreground="#fecaca", borderwidth=0, padding=(12, 8))
        style.map("Danger.TButton", background=[("active", "#541d28"), ("disabled", CARD_ALT)])
        style.configure("Green.Horizontal.TProgressbar", troughcolor=CARD_ALT, background=ACCENT, bordercolor=CARD_ALT, lightcolor=ACCENT, darkcolor=ACCENT, thickness=10)
        style.configure("Modern.Horizontal.TScale", background=CARD_BG, troughcolor=CARD_ALT, sliderthickness=18)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, style="Root.TFrame", padding=(24, 20, 24, 20))
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root, style="Header.TFrame")
        header.pack(fill="x")
        left = ttk.Frame(header, style="Header.TFrame")
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="Kokoro SRT Studio", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text="Local ONNX TTS · GPU tự nhận · dựng WAV theo timeline SRT", style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))

        badge = tk.Label(header, textvariable=self.backend_var, bg="#12321f", fg="#86efac", font=("Segoe UI Semibold", 9), padx=12, pady=7)
        badge.pack(side="right", anchor="n", pady=(4, 0))

        stats = ttk.Frame(root, style="Root.TFrame")
        stats.pack(fill="x", pady=(18, 12))
        self._stat_card(stats, "BACKEND", self.backend_var).pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._stat_card(stats, "HIỆU NĂNG", self.perf_var).pack(side="left", fill="x", expand=True, padx=6)
        self._stat_card(stats, "SUBTITLE", self.cue_var).pack(side="left", fill="x", expand=True, padx=(6, 0))

        files = self._card(root)
        files.pack(fill="x", pady=(0, 10))
        ttk.Label(files, text="File local", style="CardTitle.TLabel").pack(anchor="w", padx=16, pady=(14, 8))
        self._path_row(files, "Model ONNX", self.model_var, self._pick_model)
        self._path_row(files, "Voices", self.voices_var, self._pick_voices)
        self._path_row(files, "Subtitle SRT", self.srt_var, self._pick_srt)
        self._path_row(files, "Output WAV", self.output_var, self._pick_output)
        ttk.Frame(files, height=8, style="Card.TFrame").pack()

        settings = self._card(root)
        settings.pack(fill="x", pady=(0, 10))
        ttk.Label(settings, text="Thiết lập tạo giọng", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=7, sticky="w", padx=16, pady=(14, 8))
        settings.columnconfigure(1, weight=2)
        settings.columnconfigure(4, weight=1)

        ttk.Label(settings, text="Voice", style="CardText.TLabel").grid(row=1, column=0, sticky="w", padx=(16, 8), pady=6)
        self.voice_combo = ttk.Combobox(settings, textvariable=self.voice_var, state="readonly", style="Modern.TCombobox")
        self.voice_combo.grid(row=1, column=1, sticky="ew", pady=6)
        self.load_btn = ttk.Button(settings, text="Nạp model", style="Ghost.TButton", command=self.load_model)
        self.load_btn.grid(row=1, column=2, padx=10, pady=6)

        ttk.Label(settings, text="Thiết bị", style="CardText.TLabel").grid(row=1, column=3, sticky="e", padx=(6, 8), pady=6)
        self.device_combo = ttk.Combobox(settings, textvariable=self.device_var, values=available_device_choices(), state="readonly", style="Modern.TCombobox", width=20)
        self.device_combo.grid(row=1, column=4, sticky="ew", pady=6)
        self.device_combo.bind("<<ComboboxSelected>>", self._device_changed)

        ttk.Label(settings, text="Lang", style="CardText.TLabel").grid(row=1, column=5, sticky="e", padx=(8, 8), pady=6)
        ttk.Entry(settings, textvariable=self.lang_var, style="Modern.TEntry", width=10).grid(row=1, column=6, sticky="ew", padx=(0, 16), pady=6)

        ttk.Label(settings, text="Speed", style="CardText.TLabel").grid(row=2, column=0, sticky="w", padx=(16, 8), pady=(8, 16))
        speed_frame = ttk.Frame(settings, style="Card.TFrame")
        speed_frame.grid(row=2, column=1, columnspan=6, sticky="ew", padx=(0, 16), pady=(8, 16))
        speed_frame.columnconfigure(0, weight=1)
        ttk.Scale(speed_frame, from_=0.7, to=1.35, variable=self.speed_var, style="Modern.Horizontal.TScale").grid(row=0, column=0, sticky="ew")
        self.speed_label = ttk.Label(speed_frame, text="1.00x", width=7, style="CardValue.TLabel")
        self.speed_label.grid(row=0, column=1, padx=(10, 0))
        self.speed_var.trace_add("write", lambda *_: self.speed_label.configure(text=f"{self.speed_var.get():.2f}x"))

        actions = ttk.Frame(root, style="Root.TFrame")
        actions.pack(fill="x", pady=(2, 10))
        self.run_btn = ttk.Button(actions, text="▶  Tạo voice từ SRT", style="Accent.TButton", command=self.start_generate)
        self.run_btn.pack(side="left")
        self.stop_btn = ttk.Button(actions, text="■  Dừng", style="Danger.TButton", command=self.cancel_generate, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        ttk.Button(actions, text="Mở thư mục output", style="Ghost.TButton", command=self.open_output_folder).pack(side="right")

        progress_card = self._card(root)
        progress_card.pack(fill="x", pady=(0, 10))
        top = ttk.Frame(progress_card, style="Card.TFrame")
        top.pack(fill="x", padx=16, pady=(12, 7))
        ttk.Label(top, textvariable=self.status_var, style="CardValue.TLabel").pack(side="left", fill="x", expand=True)
        self.progress_label = ttk.Label(top, text="0%", style="CardText.TLabel")
        self.progress_label.pack(side="right")
        ttk.Progressbar(progress_card, variable=self.progress_var, maximum=100, style="Green.Horizontal.TProgressbar").pack(fill="x", padx=16, pady=(0, 14))

        log_card = self._card(root)
        log_card.pack(fill="both", expand=True)
        log_head = ttk.Frame(log_card, style="Card.TFrame")
        log_head.pack(fill="x", padx=16, pady=(12, 6))
        ttk.Label(log_head, text="Nhật ký", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(log_head, text="Xóa", style="Ghost.TButton", command=self._clear_log).pack(side="right")
        self.log = tk.Text(log_card, height=9, wrap="word", state="disabled", bg=ENTRY_BG, fg="#cbd5e1", insertbackground=TEXT, selectbackground=BORDER, relief="flat", bd=0, padx=12, pady=10, font=("Cascadia Mono", 9))
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def _card(self, parent) -> ttk.Frame:
        return ttk.Frame(parent, style="Card.TFrame")

    def _stat_card(self, parent, title: str, value_var: tk.StringVar) -> ttk.Frame:
        frame = ttk.Frame(parent, style="CardAlt.TFrame", padding=(14, 10))
        ttk.Label(frame, text=title, style="StatMuted.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=value_var, style="Stat.TLabel").pack(anchor="w", pady=(2, 0))
        return frame

    def _path_row(self, parent, label: str, var: tk.StringVar, command) -> None:
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", padx=16, pady=4)
        ttk.Label(row, text=label, width=14, style="Path.TLabel").pack(side="left")
        ttk.Entry(row, textvariable=var, style="Modern.TEntry").pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(row, text="Chọn…", style="Ghost.TButton", command=command, width=9).pack(side="right")

    def _pick_model(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("ONNX model", "*.onnx"), ("All files", "*.*")])
        if path:
            self.model_var.set(path)
            self._invalidate_model()

    def _pick_voices(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Kokoro voices", "*.bin"), ("All files", "*.*")])
        if path:
            self.voices_var.set(path)
            self._invalidate_model()

    def _pick_srt(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("SubRip subtitle", "*.srt"), ("All files", "*.*")])
        if path:
            self.srt_var.set(path)
            p = Path(path)
            self.output_var.set(str(p.with_name(p.stem + "_kokoro.wav")))
            try:
                cues = parse_srt(p)
                self.cue_var.set(f"{len(cues)} cue · {cues[-1].end:.1f}s" if cues else "0 cue")
            except Exception:
                self.cue_var.set("SRT lỗi")

    def _pick_output(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV audio", "*.wav")])
        if path:
            self.output_var.set(path)

    def _device_changed(self, _event=None) -> None:
        try:
            provider = resolve_provider(self.device_var.get())
            self.backend_var.set(provider_label(provider))
            self._switch_default_model_for_provider(provider)
        except Exception as exc:
            self.backend_var.set("Provider chưa sẵn sàng")
            self._append_log(str(exc))
        self._invalidate_model(keep_voice=False)

    def _switch_default_model_for_provider(self, provider: str) -> None:
        model_dir = os.environ.get("KOKORO_MODEL_DIR", "").strip()
        if not model_dir:
            return
        folder = Path(model_dir)
        int8_model = folder / "kokoro-v1.0.int8.onnx"
        fp16_model = folder / "kokoro-v1.0.fp16.onnx"
        current = Path(self.model_var.get()).name.lower() if self.model_var.get() else ""
        default_names = {"kokoro-v1.0.int8.onnx", "kokoro-v1.0.fp16.onnx"}
        if current and current not in default_names:
            return
        if provider in {"CUDAExecutionProvider", "DmlExecutionProvider"} and fp16_model.is_file():
            self.model_var.set(str(fp16_model))
        elif int8_model.is_file():
            self.model_var.set(str(int8_model))

    def _invalidate_model(self, keep_voice: bool = False) -> None:
        self._kokoro = None
        self._backend_provider = None
        self._loaded_signature = None
        if not keep_voice:
            self.voice_combo["values"] = ()
            self.voice_var.set("")

    def _validate_model_paths(self) -> tuple[Path, Path]:
        model = Path(self.model_var.get()).expanduser()
        voices = Path(self.voices_var.get()).expanduser()
        if not model.is_file():
            raise FileNotFoundError("Chưa chọn file model .onnx hợp lệ.")
        if not voices.is_file():
            raise FileNotFoundError("Chưa chọn file voices .bin hợp lệ.")
        return model, voices

    def load_model(self) -> None:
        if self._busy:
            return
        try:
            model, voices = self._validate_model_paths()
            device = self.device_var.get()
        except Exception as exc:
            messagebox.showerror("Thiếu file", str(exc))
            return
        self._set_busy(True, can_cancel=False)
        self.status_var.set("Đang nạp và tối ưu ONNX session…")
        threading.Thread(target=self._load_model_worker, args=(model, voices, device), daemon=True).start()

    def _load_model_worker(self, model: Path, voices: Path, device: str) -> None:
        try:
            started = time.perf_counter()
            kokoro, provider = make_kokoro(model, voices, device)
            available = sorted(kokoro.get_voices())
            elapsed = time.perf_counter() - started
            self._events.put(("model_loaded", (kokoro, available, str(model), str(voices), provider, elapsed)))
        except Exception as exc:
            self._events.put(("error", f"Lỗi nạp model: {exc}"))

    def start_generate(self) -> None:
        if self._busy:
            return
        try:
            model, voices = self._validate_model_paths()
            srt = Path(self.srt_var.get()).expanduser()
            output = Path(self.output_var.get()).expanduser()
            if not srt.is_file():
                raise FileNotFoundError("Chưa chọn file .srt hợp lệ.")
            if not output.name:
                raise ValueError("Chưa chọn file output WAV.")
            cues = parse_srt(srt)
            if not cues:
                raise ValueError("Không đọc được cue hợp lệ trong file SRT.")
            requested_voice = self.voice_var.get().strip()
            speed = float(self.speed_var.get())
            lang = self.lang_var.get().strip() or "en-us"
            device = self.device_var.get()
        except Exception as exc:
            messagebox.showerror("Không thể chạy", str(exc))
            return

        self._cancel.clear()
        self._set_busy(True, can_cancel=True)
        self.progress_var.set(0)
        self.progress_label.configure(text="0%")
        self.cue_var.set(f"{len(cues)} cue · {cues[-1].end:.1f}s")
        self.perf_var.set("Đang đo tốc độ…")
        threading.Thread(target=self._generate_worker, args=(model, voices, cues, output, requested_voice, speed, lang, device), daemon=True).start()

    def cancel_generate(self) -> None:
        if self._busy:
            self._cancel.set()
            self.status_var.set("Đang dừng sau cue hiện tại…")
            self.stop_btn.configure(state="disabled")

    def _generate_worker(self, model: Path, voices: Path, cues: list[Cue], output: Path, requested_voice: str, speed: float, lang: str, device: str) -> None:
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

            for i, cue in enumerate(cues, start=1):
                if self._cancel.is_set():
                    self._events.put(("cancelled", None))
                    return
                if i == 1 or i == total or i % 5 == 0:
                    self._events.put(("status", f"Đang tạo cue {i}/{total}…"))

                samples, sr = self._kokoro.create(cue.text, voice=voice_style, speed=speed, lang=lang, trim=True)
                samples = np.asarray(samples, dtype=np.float32).reshape(-1)
                sr = int(sr)
                if sample_rate is None:
                    sample_rate = sr
                elif sr != sample_rate:
                    samples = resample_linear(samples, round(len(samples) * sample_rate / sr))

                assert sample_rate is not None
                requested_start = max(0, int(round(cue.start * sample_rate)))
                start_sample = max(requested_start, cursor_sample)
                chunks.append((start_sample, samples))
                cursor_sample = start_sample + len(samples)
                generated_audio_samples += len(samples)

                if start_sample > requested_start and (i == 1 or i % 10 == 0):
                    delay = (start_sample - requested_start) / sample_rate
                    self._events.put(("log", f"Cue {cue.index}: dời +{delay:.2f}s để tránh chồng giọng."))
                self._events.put(("progress", i * 100.0 / total))

            assert sample_rate is not None
            final_length = max(cursor_sample, int(round(max(cue.end for cue in cues) * sample_rate)), 1)
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
            self._events.put(("done", {"output": str(output), "elapsed": elapsed, "generated_seconds": generated_seconds, "speed_x": speed_x, "provider": provider, "cues": total}))
        except Exception as exc:
            self._events.put(("error", f"Lỗi tạo voice: {exc}"))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "status":
                    self.status_var.set(str(payload))
                elif kind == "log":
                    self._append_log(str(payload))
                elif kind == "progress":
                    value = float(payload)
                    self.progress_var.set(value)
                    self.progress_label.configure(text=f"{value:.0f}%")
                elif kind == "model_loaded":
                    kokoro, voices, model, voice_file, provider, elapsed = payload  # type: ignore[misc]
                    self._kokoro = kokoro
                    self._backend_provider = provider
                    self._loaded_signature = (model, voice_file, provider)
                    self.voice_combo["values"] = voices
                    if voices and self.voice_var.get() not in voices:
                        self.voice_var.set("am_michael" if "am_michael" in voices else voices[0])
                    self.backend_var.set(provider_label(provider))
                    self.status_var.set(f"Model sẵn sàng · {len(voices)} voices · nạp {elapsed:.1f}s")
                    self._append_log(self.status_var.get())
                    self._set_busy(False)
                elif kind == "done":
                    info = payload  # type: ignore[assignment]
                    self.progress_var.set(100)
                    self.progress_label.configure(text="100%")
                    self.backend_var.set(provider_label(info["provider"]))
                    self.perf_var.set(f"{info['speed_x']:.2f}× realtime · {info['elapsed']:.1f}s")
                    self.status_var.set(f"Hoàn tất · {info['cues']} cue · {info['output']}")
                    self._append_log(f"Hoàn tất: {info['generated_seconds']:.1f}s audio trong {info['elapsed']:.1f}s ({info['speed_x']:.2f}× realtime).")
                    self._set_busy(False)
                    messagebox.showinfo("Hoàn tất", f"Đã tạo WAV:\n{info['output']}\n\nTốc độ: {info['speed_x']:.2f}× realtime")
                elif kind == "cancelled":
                    self.status_var.set("Đã dừng.")
                    self._append_log("Đã dừng theo yêu cầu.")
                    self._set_busy(False)
                elif kind == "error":
                    self.status_var.set(str(payload))
                    self._append_log(str(payload))
                    self._set_busy(False)
                    messagebox.showerror("Lỗi", str(payload))
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _set_busy(self, busy: bool, can_cancel: bool = False) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.run_btn.configure(state=state)
        self.load_btn.configure(state=state)
        self.device_combo.configure(state="disabled" if busy else "readonly")
        self.stop_btn.configure(state="normal" if busy and can_cancel else "disabled")

    def open_output_folder(self) -> None:
        output = self.output_var.get().strip()
        folder = Path(output).expanduser().parent if output else Path.cwd()
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror("Không mở được thư mục", str(exc))


if __name__ == "__main__":
    KokoroSrtApp().mainloop()
