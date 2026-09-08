from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import time
import types

import numpy as np
import soundfile as sf


def install_parallel_render(app, ns: dict[str, object], context_combo, studio) -> None:
    """Turn the visible Context control into a safe 1..10 render-worker control.

    Clean mode always keeps the real context_cues_var at 1. Raw text is
    phonemized serially because espeak-ng uses process-global state; only the
    ONNX synthesis stage runs concurrently, using is_phonemes=True. Each cue is
    still exported as its own scene_XXX_audio.wav file.
    """

    tk = ns["tk"]
    ttk = ns["ttk"]
    quality_dir = Path(ns["QUALITY_DIR"])
    workers_file = quality_dir / "render_workers.txt"

    try:
        saved_workers = int(workers_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        saved_workers = 1
    saved_workers = max(1, min(10, saved_workers))

    app.render_workers_var = tk.IntVar(value=saved_workers)

    # Reuse the exact UI position the user pointed at. The internal context
    # variable remains locked to 1 by safe_quality_launcher.
    try:
        for widget in studio.grid_slaves(row=5, column=2):
            try:
                if str(widget.cget("text")) == "Context cue":
                    widget.configure(text="Luồng render")
            except Exception:
                pass
        context_combo.configure(
            textvariable=app.render_workers_var,
            values=list(range(1, 11)),
            state="readonly",
        )
    except Exception:
        pass

    def save_workers(*_args) -> None:
        try:
            value = max(1, min(10, int(app.render_workers_var.get())))
            quality_dir.mkdir(parents=True, exist_ok=True)
            workers_file.write_text(str(value), encoding="utf-8")
        except (OSError, ValueError, TypeError):
            pass

    app.render_workers_var.trace_add("write", save_workers)

    previous_start_generate = app.start_generate

    def start_with_parallel_workers(self) -> None:
        try:
            workers = max(1, min(10, int(self.render_workers_var.get())))
        except (ValueError, TypeError):
            workers = 1
            self.render_workers_var.set(1)
        self._parallel_workers = workers
        # This is a render-concurrency control, not multi-cue prosody context.
        self.context_cues_var.set(1)
        self._append_log(
            f"Luồng render: {workers} · mỗi scene vẫn độc lập"
            + (" · phonemize tuần tự + ONNX song song" if workers > 1 else "")
        )
        previous_start_generate()

    app.start_generate = types.MethodType(start_with_parallel_workers, app)
    app.run_btn.configure(command=app.start_generate)

    original_worker = app._generate_worker

    resolve_provider = ns["resolve_provider"]
    make_kokoro = ns["make_kokoro"]
    prepare_cue_text = ns["prepare_cue_text"]
    adaptive_speed = ns["adaptive_speed"]
    adaptive_pauses = ns["adaptive_pauses"]
    resample_linear = ns["resample_linear"]
    no_blend = ns["NO_BLEND"]

    def parallel_generate_worker(
        self,
        model: Path,
        voices: Path,
        cues,
        output: Path,
        requested_voice: str,
        speed: float,
        lang: str,
        device: str,
    ) -> None:
        workers = max(1, min(10, int(getattr(self, "_parallel_workers", 1))))
        if workers <= 1:
            original_worker(model, voices, cues, output, requested_voice, speed, lang, device)
            return

        try:
            provider = resolve_provider(device)
            signature = (str(model), str(voices), provider)
            if self._kokoro is None or self._loaded_signature != signature:
                self._events.put(("status", "Đang nạp ONNX session cho render song song…"))
                self._kokoro, self._backend_provider = make_kokoro(model, voices, device)
                self._loaded_signature = (str(model), str(voices), self._backend_provider)

            kokoro = self._kokoro
            assert kokoro is not None
            provider = self._backend_provider or provider

            available = list(kokoro.get_voices())
            voice = requested_voice or (available[0] if available else "")
            if not voice or voice not in available:
                raise RuntimeError(f"Voice không tồn tại: {voice or '(trống)'}")

            fx = getattr(self, "_voice_fx", {})
            blend_voice = str(fx.get("blend_voice", no_blend))
            blend_percent = max(0.0, min(100.0, float(fx.get("blend_percent", 0.0))))
            sentence_pause = max(0.0, min(1.5, float(fx.get("sentence_pause", 0.25))))
            clause_pause = max(0.0, min(1.0, float(fx.get("clause_pause", 0.10))))
            normalize = bool(fx.get("normalize", True))
            preset = str(fx.get("preset", "Natural"))

            qfx = getattr(self, "_quality_fx", {})
            smart_text = bool(qfx.get("smart_text", True))
            adaptive_expression = bool(qfx.get("adaptive_expression", True))
            natural_edges = bool(qfx.get("natural_edges", True))
            emotion_strength = max(0.0, min(100.0, float(qfx.get("emotion_strength", 35.0))))
            quality_mode = str(qfx.get("mode", "Clean"))

            primary_style = kokoro.get_voice_style(voice)
            voice_style = primary_style
            actual_blend = 0.0
            if (
                blend_voice
                and blend_voice != no_blend
                and blend_voice in available
                and blend_voice != voice
                and blend_percent > 0
            ):
                secondary_style = kokoro.get_voice_style(blend_voice)
                ratio = np.float32(blend_percent / 100.0)
                voice_style = (
                    np.asarray(primary_style, dtype=np.float32) * (np.float32(1.0) - ratio)
                    + np.asarray(secondary_style, dtype=np.float32) * ratio
                ).astype(np.float32, copy=False)
                actual_blend = blend_percent

            prepared = [prepare_cue_text(cues, i, lang, smart_text) for i in range(len(cues))]
            total = len(cues)
            if total <= 0:
                raise RuntimeError("SRT không có cue để tạo voice")

            # IMPORTANT: espeak-ng/phonemizer is not thread-safe. Do all raw-text
            # phonemization here, on this one worker thread, before launching any
            # concurrent ONNX inference. The futures receive phonemes only.
            self._events.put(
                (
                    "status",
                    f"Đang chuẩn bị phát âm {total} scene trước khi chạy {workers} luồng…",
                )
            )
            phonemes: list[str] = []
            for index, text in enumerate(prepared):
                if self._cancel.is_set():
                    self._events.put(("cancelled", None))
                    return
                ph = kokoro.tokenizer.phonemize(text, lang)
                ph = " ".join(str(ph).split())
                if not ph:
                    raise RuntimeError(f"Scene {index:03d} không tạo được phoneme")
                phonemes.append(ph)

            self._events.put(
                (
                    "log",
                    f"Parallel render SAFE: {workers} luồng · phonemize tuần tự · "
                    "ONNX is_phonemes=True · mỗi scene 1 file riêng.",
                )
            )
            self._events.put(
                (
                    "log",
                    f"Voice: {preset} · {voice}"
                    + (f" + {blend_voice} {actual_blend:.0f}%" if actual_blend else "")
                    + f" · speed {speed:.2f}x · quality {quality_mode}",
                )
            )

            dubbing_dir_text = getattr(self, "_dubbing_dir", "")
            dubbing_dir = Path(dubbing_dir_text) if dubbing_dir_text else output.parent / "2_Dubbing_Audio"
            dubbing_dir.mkdir(parents=True, exist_ok=True)
            for old_scene in dubbing_dir.glob("scene_*_audio.wav"):
                try:
                    old_scene.unlink()
                except OSError:
                    pass

            started = time.perf_counter()
            completed = 0
            scene_rates: dict[int, int] = {}
            generated_audio_samples = 0
            studio_finish = ns["studio_finish"]

            def synth_task(scene_index: int):
                text = prepared[scene_index]
                local_speed = (
                    adaptive_speed(speed, text, emotion_strength)
                    if adaptive_expression
                    else speed
                )
                local_sentence, local_clause = (
                    adaptive_pauses(sentence_pause, clause_pause, text, emotion_strength)
                    if adaptive_expression
                    else (sentence_pause, clause_pause)
                )
                samples, sr = kokoro.create(
                    phonemes[scene_index],
                    voice=voice_style,
                    speed=local_speed,
                    lang=lang,
                    is_phonemes=True,
                    trim=True,
                    sentence_pause=local_sentence,
                    clause_pause=local_clause,
                    continuous=False,
                )
                return scene_index, np.asarray(samples, dtype=np.float32).reshape(-1), int(sr)

            executor = ThreadPoolExecutor(max_workers=min(workers, total), thread_name_prefix="kokoro-scene")
            futures = {executor.submit(synth_task, i): i for i in range(total)}
            try:
                for future in as_completed(futures):
                    if self._cancel.is_set():
                        for pending in futures:
                            pending.cancel()
                        self._events.put(("cancelled", None))
                        return

                    scene_index, audio, sr = future.result()
                    audio = studio_finish(audio, sr, normalize, natural_edges)
                    scene_path = dubbing_dir / f"scene_{scene_index:03d}_audio.wav"
                    sf.write(str(scene_path), audio, sr, subtype="PCM_16")
                    scene_rates[scene_index] = sr
                    generated_audio_samples += len(audio)
                    completed += 1
                    self._events.put(("progress", completed * 100.0 / total))
                    self._events.put(
                        (
                            "status",
                            f"Đã tạo {completed}/{total} scene · {workers} luồng đang chạy…",
                        )
                    )
            finally:
                executor.shutdown(wait=True, cancel_futures=True)

            if len(scene_rates) != total:
                raise RuntimeError(f"Chỉ tạo được {len(scene_rates)}/{total} scene")

            # Rebuild the listening/master WAV in SRT order. Parallel completion
            # order never changes scene filenames or the natural no-overlap timing.
            sample_rate = scene_rates[0]
            chunks: list[tuple[int, np.ndarray]] = []
            cursor_sample = 0
            for scene_index in range(total):
                scene_path = dubbing_dir / f"scene_{scene_index:03d}_audio.wav"
                audio, sr = sf.read(str(scene_path), dtype="float32", always_2d=False)
                audio = np.asarray(audio, dtype=np.float32).reshape(-1)
                if int(sr) != sample_rate:
                    audio = resample_linear(audio, round(len(audio) * sample_rate / int(sr)))
                requested_start = max(0, int(round(float(cues[scene_index].start) * sample_rate)))
                start_sample = max(requested_start, cursor_sample)
                chunks.append((start_sample, audio))
                cursor_sample = start_sample + len(audio)

            final_length = max(
                cursor_sample,
                int(round(max(float(cue.end) for cue in cues) * sample_rate)),
                1,
            )
            timeline = np.zeros(final_length, dtype=np.float32)
            for start_sample, audio in chunks:
                end = min(start_sample + len(audio), final_length)
                if end > start_sample:
                    timeline[start_sample:end] += audio[: end - start_sample]
            np.clip(timeline, -1.0, 1.0, out=timeline)

            output.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output), timeline, sample_rate, subtype="PCM_16")

            elapsed = max(time.perf_counter() - started, 1e-6)
            generated_seconds = generated_audio_samples / sample_rate
            speed_x = generated_seconds / elapsed
            self._events.put(
                (
                    "log",
                    f"Đã xuất {total} scene riêng bằng {workers} luồng vào: {dubbing_dir}",
                )
            )
            self._events.put(
                (
                    "done",
                    {
                        "output": str(output),
                        "dubbing_dir": str(dubbing_dir),
                        "elapsed": elapsed,
                        "generated_seconds": generated_seconds,
                        "speed_x": speed_x,
                        "provider": provider,
                        "cues": total,
                    },
                )
            )
        except Exception as exc:
            self._events.put(("error", f"Lỗi render song song: {exc}"))

    app._generate_worker = types.MethodType(parallel_generate_worker, app)
    app._append_log(
        f"Parallel scene render READY · chọn 1–10 luồng · hiện tại {saved_workers} · output vẫn từng scene riêng."
    )
