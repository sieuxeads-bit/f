from __future__ import annotations

import queue
import re
import threading
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro


@dataclass
class Cue:
    index: int
    start: float
    end: float
    text: str


def parse_time(value: str) -> float:
    h, m, rest = value.strip().replace('.', ',').split(':')
    s, ms = rest.split(',')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(path: Path) -> list[Cue]:
    text = path.read_text(encoding='utf-8-sig', errors='replace').replace('\r', '').strip()
    if not text:
        return []

    cues: list[Cue] = []
    blocks = re.split(r'\n\s*\n', text)
    pattern = re.compile(
        r'(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*'
        r'(\d{2}:\d{2}:\d{2}[,.]\d{3})'
    )

    for fallback_index, block in enumerate(blocks, start=1):
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if not lines:
            continue

        has_index = bool(re.fullmatch(r'\d+', lines[0]))
        time_line_pos = 1 if has_index else 0
        if len(lines) <= time_line_pos:
            continue

        match = pattern.search(lines[time_line_pos])
        if not match:
            continue

        start = parse_time(match.group(1))
        end = parse_time(match.group(2))
        subtitle = ' '.join(lines[time_line_pos + 1:]).strip()
        subtitle = re.sub(r'<[^>]+>', '', subtitle)
        subtitle = re.sub(r'\{\\.*?\}', '', subtitle).strip()
        if not subtitle:
            continue

        cues.append(
            Cue(
                index=int(lines[0]) if has_index else fallback_index,
                start=start,
                end=end,
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


def mix_into_timeline(timeline: np.ndarray, start_sample: int, samples: np.ndarray) -> None:
    if start_sample >= len(timeline):
        return
    count = min(len(samples), len(timeline) - start_sample)
    if count <= 0:
        return
    region = timeline[start_sample:start_sample + count]
    region += samples[:count]
    np.clip(region, -1.0, 1.0, out=region)


class KokoroSrtApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title('Kokoro SRT Local')
        self.geometry('900x680')
        self.minsize(820, 600)

        self.model_var = tk.StringVar()
        self.voices_var = tk.StringVar()
        self.srt_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.voice_var = tk.StringVar()
        self.lang_var = tk.StringVar(value='en-us')
        self.speed_var = tk.DoubleVar(value=1.0)
        self.fit_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value='Chọn model ONNX + voices + SRT để bắt đầu.')
        self.progress_var = tk.DoubleVar(value=0)

        self._kokoro: Kokoro | None = None
        self._loaded_signature: tuple[str, str] | None = None
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._busy = False

        self._build_ui()
        self.after(100, self._poll_events)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill='both', expand=True)

        ttk.Label(root, text='Kokoro SRT Local', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(
            root,
            text='Native ONNX Runtime — chọn model như Piper, đọc SRT và xuất WAV theo timeline.'
        ).pack(anchor='w', pady=(2, 16))

        files = ttk.LabelFrame(root, text='1. File local', padding=12)
        files.pack(fill='x')
        self._path_row(files, 'Model .onnx', self.model_var, self._pick_model)
        self._path_row(files, 'Voices .bin', self.voices_var, self._pick_voices)
        self._path_row(files, 'Subtitle .srt', self.srt_var, self._pick_srt)
        self._path_row(files, 'Output .wav', self.output_var, self._pick_output)

        settings = ttk.LabelFrame(root, text='2. Thiết lập', padding=12)
        settings.pack(fill='x', pady=(12, 0))
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)

        ttk.Label(settings, text='Voice').grid(row=0, column=0, sticky='w', padx=(0, 8), pady=5)
        self.voice_combo = ttk.Combobox(settings, textvariable=self.voice_var, state='readonly')
        self.voice_combo.grid(row=0, column=1, sticky='ew', pady=5)
        ttk.Button(settings, text='Nạp voices', command=self.load_model).grid(row=0, column=2, padx=8, pady=5)

        ttk.Label(settings, text='Language').grid(row=0, column=3, sticky='e', padx=(8, 6), pady=5)
        ttk.Entry(settings, textvariable=self.lang_var, width=12).grid(row=0, column=4, sticky='ew', pady=5)

        ttk.Label(settings, text='Speed').grid(row=1, column=0, sticky='w', padx=(0, 8), pady=5)
        speed_frame = ttk.Frame(settings)
        speed_frame.grid(row=1, column=1, columnspan=2, sticky='ew', pady=5)
        speed_frame.columnconfigure(0, weight=1)
        ttk.Scale(speed_frame, from_=0.7, to=1.3, variable=self.speed_var).grid(row=0, column=0, sticky='ew')
        self.speed_label = ttk.Label(speed_frame, text='1.00x', width=7)
        self.speed_label.grid(row=0, column=1, padx=(8, 0))
        self.speed_var.trace_add('write', lambda *_: self.speed_label.configure(text=f'{self.speed_var.get():.2f}x'))

        ttk.Checkbutton(
            settings,
            text='Fit câu dài vào đúng ô thời gian SRT',
            variable=self.fit_var,
        ).grid(row=1, column=3, columnspan=2, sticky='w', padx=(8, 0), pady=5)

        actions = ttk.Frame(root)
        actions.pack(fill='x', pady=14)
        self.run_btn = ttk.Button(actions, text='Tạo voice từ SRT', command=self.start_generate)
        self.run_btn.pack(side='left')
        ttk.Button(actions, text='Mở thư mục output', command=self.open_output_folder).pack(side='left', padx=8)

        ttk.Progressbar(root, variable=self.progress_var, maximum=100).pack(fill='x')
        ttk.Label(root, textvariable=self.status_var, wraplength=850).pack(fill='x', pady=(8, 0))

        log_box = ttk.LabelFrame(root, text='Log', padding=8)
        log_box.pack(fill='both', expand=True, pady=(12, 0))
        self.log = tk.Text(log_box, height=14, wrap='word', state='disabled')
        self.log.pack(fill='both', expand=True)

    def _path_row(self, parent: ttk.Frame, label: str, var: tk.StringVar, command) -> None:
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=4)
        ttk.Label(row, text=label, width=14).pack(side='left')
        ttk.Entry(row, textvariable=var).pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(row, text='Chọn...', command=command, width=10).pack(side='right')

    def _pick_model(self) -> None:
        path = filedialog.askopenfilename(filetypes=[('ONNX model', '*.onnx'), ('All files', '*.*')])
        if path:
            self.model_var.set(path)
            self._invalidate_model()

    def _pick_voices(self) -> None:
        path = filedialog.askopenfilename(filetypes=[('Kokoro voices', '*.bin'), ('All files', '*.*')])
        if path:
            self.voices_var.set(path)
            self._invalidate_model()

    def _pick_srt(self) -> None:
        path = filedialog.askopenfilename(filetypes=[('SubRip subtitle', '*.srt'), ('All files', '*.*')])
        if path:
            self.srt_var.set(path)
            if not self.output_var.get():
                self.output_var.set(str(Path(path).with_name(Path(path).stem + '_kokoro.wav')))

    def _pick_output(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension='.wav', filetypes=[('WAV audio', '*.wav')])
        if path:
            self.output_var.set(path)

    def _invalidate_model(self) -> None:
        self._kokoro = None
        self._loaded_signature = None
        self.voice_combo['values'] = ()
        self.voice_var.set('')

    def _validate_model_paths(self) -> tuple[Path, Path]:
        model = Path(self.model_var.get()).expanduser()
        voices = Path(self.voices_var.get()).expanduser()
        if not model.is_file():
            raise FileNotFoundError('Chưa chọn file model .onnx hợp lệ.')
        if not voices.is_file():
            raise FileNotFoundError('Chưa chọn file voices .bin hợp lệ.')
        return model, voices

    def load_model(self) -> None:
        if self._busy:
            return
        try:
            model, voices = self._validate_model_paths()
        except Exception as exc:
            messagebox.showerror('Thiếu file', str(exc))
            return

        self._set_busy(True)
        self.status_var.set('Đang nạp ONNX model...')
        threading.Thread(target=self._load_model_worker, args=(model, voices), daemon=True).start()

    def _load_model_worker(self, model: Path, voices: Path) -> None:
        try:
            kokoro = Kokoro(str(model), str(voices))
            available = list(kokoro.get_voices())
            self._events.put(('model_loaded', (kokoro, available, str(model), str(voices))))
        except Exception as exc:
            self._events.put(('error', f'Lỗi nạp model: {exc}'))

    def start_generate(self) -> None:
        if self._busy:
            return
        try:
            model, voices = self._validate_model_paths()
            srt = Path(self.srt_var.get()).expanduser()
            output = Path(self.output_var.get()).expanduser()
            if not srt.is_file():
                raise FileNotFoundError('Chưa chọn file .srt hợp lệ.')
            if not output.name:
                raise ValueError('Chưa chọn file output WAV.')
            cues = parse_srt(srt)
            if not cues:
                raise ValueError('Không đọc được cue hợp lệ trong file SRT.')

            requested_voice = self.voice_var.get().strip()
            speed = float(self.speed_var.get())
            lang = self.lang_var.get().strip() or 'en-us'
            fit = bool(self.fit_var.get())
        except Exception as exc:
            messagebox.showerror('Không thể chạy', str(exc))
            return

        self._set_busy(True)
        self.progress_var.set(0)
        threading.Thread(
            target=self._generate_worker,
            args=(model, voices, cues, output, requested_voice, speed, lang, fit),
            daemon=True,
        ).start()

    def _generate_worker(
        self,
        model: Path,
        voices: Path,
        cues: list[Cue],
        output: Path,
        requested_voice: str,
        speed: float,
        lang: str,
        fit: bool,
    ) -> None:
        try:
            signature = (str(model), str(voices))
            if self._kokoro is None or self._loaded_signature != signature:
                self._events.put(('status', 'Đang nạp model ONNX...'))
                self._kokoro = Kokoro(str(model), str(voices))
                self._loaded_signature = signature

            available = list(self._kokoro.get_voices())
            voice = requested_voice or (available[0] if available else '')
            if not voice:
                raise RuntimeError('Không tìm thấy voice trong voices .bin.')
            if available and voice not in available:
                raise RuntimeError(f'Voice không tồn tại: {voice}')

            total_seconds = max(cue.end for cue in cues) + 0.25
            sample_rate: int | None = None
            timeline: np.ndarray | None = None

            for i, cue in enumerate(cues, start=1):
                self._events.put(('status', f'[{i}/{len(cues)}] {cue.text[:80]}'))
                samples, sr = self._kokoro.create(cue.text, voice=voice, speed=speed, lang=lang)
                samples = np.asarray(samples, dtype=np.float32).reshape(-1)
                sr = int(sr)

                if sample_rate is None:
                    sample_rate = sr
                    timeline = np.zeros(int(np.ceil(total_seconds * sr)), dtype=np.float32)
                elif sr != sample_rate:
                    samples = resample_linear(samples, round(len(samples) * sample_rate / sr))

                assert timeline is not None and sample_rate is not None
                slot_len = max(1, int(round((cue.end - cue.start) * sample_rate)))
                if fit and len(samples) > slot_len:
                    samples = resample_linear(samples, slot_len)

                start_sample = max(0, int(round(cue.start * sample_rate)))
                needed = start_sample + len(samples)
                if needed > len(timeline):
                    timeline = np.pad(timeline, (0, needed - len(timeline)))
                mix_into_timeline(timeline, start_sample, samples)
                self._events.put(('progress', i * 100.0 / len(cues)))

            assert timeline is not None and sample_rate is not None
            output.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output), timeline, sample_rate, subtype='PCM_16')
            self._events.put(('done', str(output)))
        except Exception as exc:
            self._events.put(('error', f'Lỗi tạo voice: {exc}'))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == 'status':
                    self.status_var.set(str(payload))
                    self._append_log(str(payload))
                elif kind == 'progress':
                    self.progress_var.set(float(payload))
                elif kind == 'model_loaded':
                    kokoro, voices, model, voice_file = payload  # type: ignore[misc]
                    self._kokoro = kokoro
                    self._loaded_signature = (model, voice_file)
                    self.voice_combo['values'] = voices
                    if voices:
                        self.voice_var.set(voices[0])
                    self.status_var.set(f'Model sẵn sàng — {len(voices)} voices.')
                    self._append_log(self.status_var.get())
                    self._set_busy(False)
                elif kind == 'done':
                    self.progress_var.set(100)
                    self.status_var.set(f'Hoàn tất: {payload}')
                    self._append_log(self.status_var.get())
                    self._set_busy(False)
                    messagebox.showinfo('Hoàn tất', f'Đã tạo WAV:\n{payload}')
                elif kind == 'error':
                    self.status_var.set(str(payload))
                    self._append_log(str(payload))
                    self._set_busy(False)
                    messagebox.showerror('Lỗi', str(payload))
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _append_log(self, text: str) -> None:
        self.log.configure(state='normal')
        self.log.insert('end', text + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.run_btn.configure(state='disabled' if busy else 'normal')

    def open_output_folder(self) -> None:
        output = self.output_var.get().strip()
        folder = Path(output).expanduser().parent if output else Path.cwd()
        try:
            import os
            import subprocess
            import sys
            if sys.platform.startswith('win'):
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(folder)])
            else:
                subprocess.Popen(['xdg-open', str(folder)])
        except Exception as exc:
            messagebox.showerror('Không mở được thư mục', str(exc))


if __name__ == '__main__':
    KokoroSrtApp().mainloop()
