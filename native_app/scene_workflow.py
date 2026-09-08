from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import hashlib
import json
import os
import queue
import threading
import time
import types

import numpy as np
import soundfile as sf

from app import parse_srt


WORKFLOW_VERSION = "scene-workflow-r1"
CACHE_FILENAME = ".kokoro_scene_cache.json"


def install_scene_workflow(app, ns: dict[str, object], studio) -> None:
    """Add static auto-retry, scene cache/resume, preview and single-scene regenerate."""

    tk = ns["tk"]
    ttk = ns["ttk"]
    messagebox = ns["messagebox"]

    resolve_provider = ns["resolve_provider"]
    make_kokoro = ns["make_kokoro"]
    prepare_cue_text = ns["prepare_cue_text"]
    adaptive_speed = ns["adaptive_speed"]
    adaptive_pauses = ns["adaptive_pauses"]
    resample_linear = ns["resample_linear"]
    no_blend = ns["NO_BLEND"]

    # ------------------------------------------------------------------
    # Scene tools UI
    # ------------------------------------------------------------------
    app.scene_tool_var = tk.StringVar(value="0")
    app.scene_cache_status_var = tk.StringVar(value="Cache/Resume: sẵn sàng")
    scene_events: queue.Queue[tuple[str, object]] = queue.Queue()

    tools = ttk.Frame(studio, style="Card.TFrame")
    tools.grid(row=7, column=0, columnspan=6, sticky="ew", padx=16, pady=(0, 12))
    tools.columnconfigure(6, weight=1)

    ttk.Label(tools, text="SCENE TOOLS", style="CardTitle.TLabel").grid(
        row=0, column=0, padx=(0, 12), sticky="w"
    )
    ttk.Label(tools, text="Scene #", style="CardText.TLabel").grid(
        row=0, column=1, padx=(0, 6), sticky="e"
    )
    scene_entry = ttk.Entry(
        tools,
        textvariable=app.scene_tool_var,
        width=8,
        style="Modern.TEntry",
    )
    scene_entry.grid(row=0, column=2, padx=(0, 8), sticky="w")

    preview_btn = ttk.Button(tools, text="▶ Nghe", style="Ghost.TButton")
    preview_btn.grid(row=0, column=3, padx=(0, 8))
    regen_btn = ttk.Button(tools, text="↻ Tạo lại scene", style="Accent.TButton")
    regen_btn.grid(row=0, column=4, padx=(0, 8))
    clear_cache_btn = ttk.Button(tools, text="Xóa cache", style="Ghost.TButton")
    clear_cache_btn.grid(row=0, column=5, padx=(0, 10))
    ttk.Label(
        tools,
        textvariable=app.scene_cache_status_var,
        style="CardValue.TLabel",
    ).grid(row=0, column=6, sticky="e")

    try:
        app.geometry("1180x930")
        app.minsize(1030, 800)
    except Exception:
        pass

    def dubbing_dir_for_current() -> Path:
        saved = str(getattr(app, "_dubbing_dir", "") or "").strip()
        if saved:
            return Path(saved)
        srt_text = app.srt_var.get().strip()
        if srt_text:
            return Path(srt_text).expanduser().parent / "2_Dubbing_Audio"
        output_text = app.output_var.get().strip()
        if output_text:
            return Path(output_text).expanduser().parent / "2_Dubbing_Audio"
        return Path.cwd() / "2_Dubbing_Audio"

    def cache_path_for(folder: Path) -> Path:
        return folder / CACHE_FILENAME

    def read_manifest(folder: Path) -> dict:
        path = cache_path_for(folder)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("scenes", {}), dict):
                return data
        except (OSError, ValueError, TypeError):
            pass
        return {"version": WORKFLOW_VERSION, "scenes": {}}

    def write_manifest(folder: Path, manifest: dict) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        path = cache_path_for(folder)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)

    def file_identity(path: Path) -> dict:
        try:
            stat = path.stat()
            return {
                "name": path.name,
                "size": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
            }
        except OSError:
            return {"name": path.name, "size": 0, "mtime_ns": 0}

    def scene_fingerprint(
        scene_index: int,
        prepared_text: str,
        model: Path,
        voices: Path,
        voice: str,
        blend_voice: str,
        blend_percent: float,
        speed: float,
        sentence_pause: float,
        clause_pause: float,
        normalize: bool,
        preset: str,
        lang: str,
        smart_text: bool,
        adaptive_expression: bool,
        natural_edges: bool,
        emotion_strength: float,
        quality_mode: str,
    ) -> str:
        payload = {
            "workflow": WORKFLOW_VERSION,
            "scene": int(scene_index),
            "text": prepared_text,
            "model": file_identity(model),
            "voices": file_identity(voices),
            "voice": voice,
            "blend_voice": blend_voice,
            "blend_percent": round(float(blend_percent), 4),
            "speed": round(float(speed), 5),
            "sentence_pause": round(float(sentence_pause), 5),
            "clause_pause": round(float(clause_pause), 5),
            "normalize": bool(normalize),
            "preset": preset,
            "lang": lang,
            "smart_text": bool(smart_text),
            "adaptive_expression": bool(adaptive_expression),
            "natural_edges": bool(natural_edges),
            "emotion_strength": round(float(emotion_strength), 4),
            "quality_mode": quality_mode,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def valid_cached_scene(path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            info = sf.info(str(path))
            return int(info.frames) > 32 and int(info.samplerate) > 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Audio quality detector
    # ------------------------------------------------------------------
    def artifact_metrics(audio: np.ndarray, sr: int) -> dict[str, float]:
        data = np.asarray(audio, dtype=np.float32).reshape(-1)
        if data.size < max(256, int(sr * 0.05)) or sr <= 0:
            return {"score": 0.0, "hf_p99": 0.0, "hf_burst": 0.0, "diff_ratio": 0.0}

        data = data - np.float32(np.mean(data, dtype=np.float64))
        overall_rms = float(np.sqrt(np.mean(data.astype(np.float64) ** 2) + 1e-12))
        if overall_rms < 1e-5:
            return {"score": 0.0, "hf_p99": 0.0, "hf_burst": 0.0, "diff_ratio": 0.0}

        # 40 ms windows catch short static bursts without treating a whole
        # sibilant consonant as a defect.
        win = max(512, int(round(sr * 0.040)))
        win = min(win, max(512, data.size))
        hop = max(128, win // 4)
        window = np.hanning(win).astype(np.float32)
        freqs = np.fft.rfftfreq(win, 1.0 / float(sr))
        high_mask = (freqs >= 8000.0) & (freqs <= min(11800.0, sr * 0.49))
        body_mask = (freqs >= 250.0) & (freqs < 8000.0)

        ratios: list[float] = []
        local_rms: list[float] = []
        for start in range(0, max(1, data.size - win + 1), hop):
            chunk = data[start : start + win]
            if chunk.size != win:
                break
            rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2) + 1e-12))
            if rms < max(0.003, overall_rms * 0.08):
                continue
            spectrum = np.fft.rfft(chunk * window)
            energy = np.abs(spectrum) ** 2
            high = float(np.sum(energy[high_mask])) if np.any(high_mask) else 0.0
            body = float(np.sum(energy[body_mask])) if np.any(body_mask) else 0.0
            ratios.append(high / (high + body + 1e-12))
            local_rms.append(rms)

        if not ratios:
            return {"score": 0.0, "hf_p99": 0.0, "hf_burst": 0.0, "diff_ratio": 0.0}

        ratio_arr = np.asarray(ratios, dtype=np.float64)
        hf_p99 = float(np.quantile(ratio_arr, 0.99))
        hf_median = float(np.quantile(ratio_arr, 0.50))
        hf_burst = max(0.0, hf_p99 - hf_median)

        diff = np.diff(data.astype(np.float64))
        diff_rms = float(np.sqrt(np.mean(diff * diff) + 1e-12))
        diff_ratio = diff_rms / (overall_rms + 1e-12)

        # Conservative detector: a scene is retried only when the upper-band
        # burst is strong AND the waveform has unusually rapid sample changes.
        high_term = max(0.0, (hf_p99 - 0.54) / 0.18)
        burst_term = max(0.0, (hf_burst - 0.46) / 0.20)
        diff_term = max(0.0, (diff_ratio - 1.30) / 0.30)
        score = high_term * 0.45 + burst_term * 0.35 + diff_term * 0.20

        peak = float(np.max(np.abs(data)))
        if peak >= 0.999:
            score += 0.35

        return {
            "score": float(score),
            "hf_p99": hf_p99,
            "hf_burst": hf_burst,
            "diff_ratio": float(diff_ratio),
        }

    def is_suspicious(metrics: dict[str, float]) -> bool:
        # Require multiple signs of static, not just natural /s/ and /sh/.
        return (
            metrics["score"] >= 0.70
            and metrics["hf_p99"] >= 0.56
            and (metrics["hf_burst"] >= 0.46 or metrics["diff_ratio"] >= 1.36)
        )

    def choose_best_candidate(candidates):
        return min(candidates, key=lambda item: float(item[3]["score"]))

    # ------------------------------------------------------------------
    # Shared render helpers
    # ------------------------------------------------------------------
    def capture_settings(model, voices, requested_voice, speed, lang, device):
        provider = resolve_provider(device)
        signature = (str(model), str(voices), provider)
        if app._kokoro is None or app._loaded_signature != signature:
            app._events.put(("status", "Đang nạp ONNX session Clean Workflow…"))
            app._kokoro, app._backend_provider = make_kokoro(model, voices, device)
            app._loaded_signature = (str(model), str(voices), app._backend_provider)

        kokoro = app._kokoro
        if kokoro is None:
            raise RuntimeError("Không nạp được Kokoro session.")
        provider = app._backend_provider or provider

        available = list(kokoro.get_voices())
        voice = requested_voice or (available[0] if available else "")
        if not voice or voice not in available:
            raise RuntimeError(f"Voice không tồn tại: {voice or '(trống)'}")

        fx = getattr(app, "_voice_fx", {})
        blend_voice = str(fx.get("blend_voice", no_blend))
        blend_percent = max(0.0, min(100.0, float(fx.get("blend_percent", 0.0))))
        sentence_pause = max(0.0, min(1.5, float(fx.get("sentence_pause", 0.25))))
        clause_pause = max(0.0, min(1.0, float(fx.get("clause_pause", 0.10))))
        normalize = bool(fx.get("normalize", True))
        preset = str(fx.get("preset", "Natural"))

        qfx = getattr(app, "_quality_fx", {})
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

        return {
            "kokoro": kokoro,
            "provider": provider,
            "voice": voice,
            "voice_style": voice_style,
            "blend_voice": blend_voice,
            "blend_percent": actual_blend,
            "sentence_pause": sentence_pause,
            "clause_pause": clause_pause,
            "normalize": normalize,
            "preset": preset,
            "smart_text": smart_text,
            "adaptive_expression": adaptive_expression,
            "natural_edges": natural_edges,
            "emotion_strength": emotion_strength,
            "quality_mode": quality_mode,
            "speed": float(speed),
            "lang": lang,
        }

    def phonemize_serial(kokoro, texts: list[str], indices: list[int], lang: str) -> dict[int, str]:
        result: dict[int, str] = {}
        for scene_index in indices:
            if app._cancel.is_set():
                break
            ph = kokoro.tokenizer.phonemize(texts[scene_index], lang)
            ph = " ".join(str(ph).split())
            if not ph:
                raise RuntimeError(f"Scene {scene_index:03d} không tạo được phoneme")
            result[scene_index] = ph
        return result

    def render_candidate(
        kokoro,
        phoneme: str,
        voice_style,
        local_speed: float,
        lang: str,
        sentence_pause: float,
        clause_pause: float,
        attempt: int,
    ):
        # Tiny speed offsets make retries numerically different while remaining
        # inaudible as a deliberate speed change.
        retry_factor = (1.0, 0.997, 1.003)[min(attempt, 2)]
        samples, sr = kokoro.create(
            phoneme,
            voice=voice_style,
            speed=max(0.5, min(2.0, local_speed * retry_factor)),
            lang=lang,
            is_phonemes=True,
            trim=True,
            sentence_pause=sentence_pause,
            clause_pause=clause_pause,
            continuous=False,
        )
        audio = np.asarray(samples, dtype=np.float32).reshape(-1)
        sr = int(sr)
        metrics = artifact_metrics(audio, sr)
        return audio, sr, attempt, metrics

    def synth_best(
        scene_index: int,
        prepared: list[str],
        phonemes: dict[int, str],
        settings: dict,
    ):
        text = prepared[scene_index]
        base_speed = settings["speed"]
        emotion_strength = settings["emotion_strength"]
        adaptive_expression = settings["adaptive_expression"]
        local_speed = (
            adaptive_speed(base_speed, text, emotion_strength)
            if adaptive_expression
            else base_speed
        )
        local_sentence, local_clause = (
            adaptive_pauses(
                settings["sentence_pause"],
                settings["clause_pause"],
                text,
                emotion_strength,
            )
            if adaptive_expression
            else (settings["sentence_pause"], settings["clause_pause"])
        )

        candidates = []
        first = render_candidate(
            settings["kokoro"],
            phonemes[scene_index],
            settings["voice_style"],
            local_speed,
            settings["lang"],
            local_sentence,
            local_clause,
            0,
        )
        candidates.append(first)

        if is_suspicious(first[3]):
            for attempt in (1, 2):
                if app._cancel.is_set():
                    break
                candidates.append(
                    render_candidate(
                        settings["kokoro"],
                        phonemes[scene_index],
                        settings["voice_style"],
                        local_speed,
                        settings["lang"],
                        local_sentence,
                        local_clause,
                        attempt,
                    )
                )

        best = choose_best_candidate(candidates)
        return scene_index, best, len(candidates)

    def rebuild_master(cues, dubbing_dir: Path, output: Path) -> tuple[int, int]:
        if not cues:
            raise RuntimeError("Không có cue để dựng WAV tổng.")
        scene_paths = [dubbing_dir / f"scene_{i:03d}_audio.wav" for i in range(len(cues))]
        missing = [p.name for p in scene_paths if not p.is_file()]
        if missing:
            raise RuntimeError(f"Thiếu {len(missing)} scene để dựng WAV tổng.")

        sample_rate = int(sf.info(str(scene_paths[0])).samplerate)
        chunks: list[tuple[int, np.ndarray]] = []
        cursor_sample = 0
        total_samples = 0
        for scene_index, scene_path in enumerate(scene_paths):
            audio, sr = sf.read(str(scene_path), dtype="float32", always_2d=False)
            audio = np.asarray(audio, dtype=np.float32)
            if audio.ndim > 1:
                audio = np.mean(audio, axis=1, dtype=np.float32)
            audio = audio.reshape(-1)
            if int(sr) != sample_rate:
                audio = resample_linear(
                    audio,
                    round(len(audio) * sample_rate / int(sr)),
                )
            requested_start = max(0, int(round(float(cues[scene_index].start) * sample_rate)))
            start_sample = max(requested_start, cursor_sample)
            chunks.append((start_sample, audio))
            cursor_sample = start_sample + len(audio)
            total_samples += len(audio)

        final_length = max(
            cursor_sample,
            int(round(max(float(c.end) for c in cues) * sample_rate)),
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
        return sample_rate, total_samples

    # ------------------------------------------------------------------
    # Full project worker: cache/resume + auto anti-static retry
    # ------------------------------------------------------------------
    def workflow_generate_worker(
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
        try:
            workers = max(1, min(10, int(getattr(self, "_parallel_workers", 1))))
            settings = capture_settings(model, voices, requested_voice, speed, lang, device)
            kokoro = settings["kokoro"]

            prepared = [
                prepare_cue_text(cues, i, lang, settings["smart_text"])
                for i in range(len(cues))
            ]
            total = len(cues)
            if total <= 0:
                raise RuntimeError("SRT không có cue để tạo voice.")

            dubbing_dir = dubbing_dir_for_current()
            dubbing_dir.mkdir(parents=True, exist_ok=True)
            manifest = read_manifest(dubbing_dir)
            manifest["version"] = WORKFLOW_VERSION
            manifest.setdefault("scenes", {})
            manifest["project"] = {
                "srt": str(self.srt_var.get()),
                "updated": time.time(),
            }

            fingerprints: dict[int, str] = {}
            cached: set[int] = set()
            for i in range(total):
                fingerprints[i] = scene_fingerprint(
                    i,
                    prepared[i],
                    model,
                    voices,
                    settings["voice"],
                    settings["blend_voice"],
                    settings["blend_percent"],
                    settings["speed"],
                    settings["sentence_pause"],
                    settings["clause_pause"],
                    settings["normalize"],
                    settings["preset"],
                    settings["lang"],
                    settings["smart_text"],
                    settings["adaptive_expression"],
                    settings["natural_edges"],
                    settings["emotion_strength"],
                    settings["quality_mode"],
                )
                scene_path = dubbing_dir / f"scene_{i:03d}_audio.wav"
                entry = manifest["scenes"].get(str(i), {})
                if (
                    isinstance(entry, dict)
                    and entry.get("fingerprint") == fingerprints[i]
                    and valid_cached_scene(scene_path)
                ):
                    cached.add(i)

            pending = [i for i in range(total) if i not in cached]
            completed = len(cached)
            self._events.put(
                (
                    "log",
                    f"Cache/Resume: dùng lại {len(cached)}/{total} scene · cần tạo {len(pending)} scene.",
                )
            )
            self._events.put(("progress", completed * 100.0 / total))
            self._events.put(
                (
                    "status",
                    f"Cache {len(cached)}/{total} · chuẩn bị {len(pending)} scene mới…",
                )
            )

            # Only uncached scenes need phonemization. Keep it serial for espeak safety.
            phonemes = phonemize_serial(kokoro, prepared, pending, lang)
            if self._cancel.is_set():
                self._events.put(("cancelled", None))
                return

            studio_finish = ns["studio_finish"]
            started = time.perf_counter()
            regenerated_static = 0
            clean_first_try = 0
            generated_samples = 0

            if pending:
                executor = ThreadPoolExecutor(
                    max_workers=min(workers, len(pending)),
                    thread_name_prefix="kokoro-workflow",
                )
                futures = {
                    executor.submit(synth_best, i, prepared, phonemes, settings): i
                    for i in pending
                }
                try:
                    for future in as_completed(futures):
                        if self._cancel.is_set():
                            for pending_future in futures:
                                pending_future.cancel()
                            self._events.put(("cancelled", None))
                            return

                        scene_index, best, attempts = future.result()
                        raw_audio, sr, chosen_attempt, metrics = best
                        if attempts > 1:
                            regenerated_static += 1
                            self._events.put(
                                (
                                    "log",
                                    f"Scene {scene_index:03d}: nghi rè/static → thử {attempts} lần, "
                                    f"chọn score {metrics['score']:.2f}.",
                                )
                            )
                        else:
                            clean_first_try += 1

                        final_audio = studio_finish(
                            raw_audio,
                            int(sr),
                            settings["normalize"],
                            settings["natural_edges"],
                        )
                        scene_path = dubbing_dir / f"scene_{scene_index:03d}_audio.wav"
                        sf.write(str(scene_path), final_audio, int(sr), subtype="PCM_16")
                        generated_samples += len(final_audio)

                        manifest["scenes"][str(scene_index)] = {
                            "fingerprint": fingerprints[scene_index],
                            "file": scene_path.name,
                            "text": prepared[scene_index],
                            "sample_rate": int(sr),
                            "frames": int(len(final_audio)),
                            "artifact_score": round(float(metrics["score"]), 4),
                            "attempts": int(attempts),
                            "updated": time.time(),
                        }
                        write_manifest(dubbing_dir, manifest)

                        completed += 1
                        self._events.put(("progress", completed * 100.0 / total))
                        self._events.put(
                            (
                                "status",
                                f"Đã xong {completed}/{total} · cache {len(cached)} · "
                                f"auto-rerender {regenerated_static}",
                            )
                        )
                finally:
                    executor.shutdown(wait=True, cancel_futures=True)

            # Remove only stale scenes after a successful complete render.
            valid_names = {f"scene_{i:03d}_audio.wav" for i in range(total)}
            for old_scene in dubbing_dir.glob("scene_*_audio.wav"):
                if old_scene.name not in valid_names:
                    try:
                        old_scene.unlink()
                    except OSError:
                        pass
            for key in list(manifest["scenes"]):
                try:
                    idx = int(key)
                except (TypeError, ValueError):
                    manifest["scenes"].pop(key, None)
                    continue
                if idx < 0 or idx >= total:
                    manifest["scenes"].pop(key, None)

            sample_rate, total_audio_samples = rebuild_master(cues, dubbing_dir, output)
            manifest["complete"] = True
            manifest["updated"] = time.time()
            write_manifest(dubbing_dir, manifest)

            elapsed = max(time.perf_counter() - started, 1e-6)
            generated_seconds = total_audio_samples / sample_rate
            speed_x = generated_seconds / elapsed

            self._events.put(
                (
                    "log",
                    f"Workflow hoàn tất · cache {len(cached)} · render mới {len(pending)} · "
                    f"scene tự thử lại vì nghi rè {regenerated_static}.",
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
                        "provider": settings["provider"],
                        "cues": total,
                    },
                )
            )
        except Exception as exc:
            self._events.put(("error", f"Lỗi Scene Workflow: {exc}"))

    app._generate_worker = types.MethodType(workflow_generate_worker, app)

    # ------------------------------------------------------------------
    # Single scene regenerate / preview
    # ------------------------------------------------------------------
    def selected_scene_index() -> int:
        try:
            value = int(str(app.scene_tool_var.get()).strip())
        except (TypeError, ValueError):
            raise ValueError("Scene phải là số, ví dụ 0 hoặc 23.")
        if value < 0:
            raise ValueError("Scene phải >= 0.")
        return value

    def current_cues():
        srt_text = app.srt_var.get().strip()
        if not srt_text:
            raise FileNotFoundError("Chưa chọn SRT.")
        srt_path = Path(srt_text).expanduser()
        if not srt_path.is_file():
            raise FileNotFoundError("File SRT không tồn tại.")
        cues = parse_srt(srt_path)
        if not cues:
            raise ValueError("SRT không có cue hợp lệ.")
        return cues

    def preview_scene() -> None:
        try:
            index = selected_scene_index()
            cues = current_cues()
            if index >= len(cues):
                raise IndexError(f"SRT chỉ có scene 0–{len(cues)-1}.")
            scene_path = dubbing_dir_for_current() / f"scene_{index:03d}_audio.wav"
            if not scene_path.is_file():
                raise FileNotFoundError(
                    f"Chưa có {scene_path.name}. Bấm 'Tạo lại scene' trước."
                )

            if os.name == "nt":
                import winsound

                winsound.PlaySound(
                    str(scene_path),
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                )
            else:
                # Best-effort fallback for non-Windows development.
                import subprocess
                import sys

                if sys.platform == "darwin":
                    subprocess.Popen(["afplay", str(scene_path)])
                else:
                    subprocess.Popen(["xdg-open", str(scene_path)])
            app._append_log(f"Nghe preview: {scene_path.name}")
        except Exception as exc:
            messagebox.showerror("Không nghe được scene", str(exc), parent=app)

    def regenerate_scene() -> None:
        if getattr(app, "_busy", False):
            messagebox.showinfo(
                "Đang render",
                "Đợi render hiện tại xong rồi hãy tạo lại scene riêng.",
                parent=app,
            )
            return
        try:
            index = selected_scene_index()
            cues = current_cues()
            if index >= len(cues):
                raise IndexError(f"SRT chỉ có scene 0–{len(cues)-1}.")
            model, voices = app._validate_model_paths()
            requested_voice = app.voice_var.get().strip()
            speed = float(app.speed_var.get())
            lang = app.lang_var.get().strip() or "en-us"
            device = app.device_var.get()
            # Capture current Studio settings exactly like a normal render.
            srt_text = app.srt_var.get().strip()
            app._dubbing_dir = str(Path(srt_text).expanduser().parent / "2_Dubbing_Audio")
            app._voice_fx = {
                "blend_voice": app.blend_voice_var.get().strip(),
                "blend_percent": float(app.blend_percent_var.get()),
                "sentence_pause": float(app.sentence_pause_var.get()),
                "clause_pause": float(app.clause_pause_var.get()),
                "normalize": bool(app.normalize_var.get()),
                "preset": app.preset_var.get().strip() or "Natural",
            }
            app._quality_fx = {
                "mode": app.quality_mode_var.get(),
                "context_cues": 1,
                "smart_text": bool(app.smart_text_var.get()),
                "adaptive_expression": bool(app.adaptive_expression_var.get()),
                "natural_edges": bool(app.natural_edges_var.get()),
                "emotion_strength": float(app.emotion_strength_var.get()),
            }
        except Exception as exc:
            messagebox.showerror("Không thể tạo lại scene", str(exc), parent=app)
            return

        app._set_busy(True, can_cancel=False)
        app.status_var.set(f"Đang tạo lại scene {index:03d}…")
        app.scene_cache_status_var.set(f"Scene {index:03d}: đang render…")

        def worker() -> None:
            try:
                settings = capture_settings(
                    model, voices, requested_voice, speed, lang, device
                )
                prepared = [
                    prepare_cue_text(cues, i, lang, settings["smart_text"])
                    for i in range(len(cues))
                ]
                phonemes = phonemize_serial(settings["kokoro"], prepared, [index], lang)
                result_index, best, attempts = synth_best(
                    index, prepared, phonemes, settings
                )
                raw_audio, sr, chosen_attempt, metrics = best
                final_audio = ns["studio_finish"](
                    raw_audio,
                    int(sr),
                    settings["normalize"],
                    settings["natural_edges"],
                )
                folder = dubbing_dir_for_current()
                folder.mkdir(parents=True, exist_ok=True)
                scene_path = folder / f"scene_{index:03d}_audio.wav"
                sf.write(str(scene_path), final_audio, int(sr), subtype="PCM_16")

                fingerprint = scene_fingerprint(
                    index,
                    prepared[index],
                    model,
                    voices,
                    settings["voice"],
                    settings["blend_voice"],
                    settings["blend_percent"],
                    settings["speed"],
                    settings["sentence_pause"],
                    settings["clause_pause"],
                    settings["normalize"],
                    settings["preset"],
                    settings["lang"],
                    settings["smart_text"],
                    settings["adaptive_expression"],
                    settings["natural_edges"],
                    settings["emotion_strength"],
                    settings["quality_mode"],
                )
                manifest = read_manifest(folder)
                manifest["version"] = WORKFLOW_VERSION
                manifest.setdefault("scenes", {})
                manifest["scenes"][str(index)] = {
                    "fingerprint": fingerprint,
                    "file": scene_path.name,
                    "text": prepared[index],
                    "sample_rate": int(sr),
                    "frames": int(len(final_audio)),
                    "artifact_score": round(float(metrics["score"]), 4),
                    "attempts": int(attempts),
                    "updated": time.time(),
                }
                write_manifest(folder, manifest)

                # If all scene files are present, refresh the listening/master WAV.
                output = Path(app.output_var.get()).expanduser()
                try:
                    rebuild_master(cues, folder, output)
                    master_updated = True
                except Exception:
                    master_updated = False

                scene_events.put(
                    (
                        "scene_regenerated",
                        {
                            "index": result_index,
                            "path": str(scene_path),
                            "attempts": attempts,
                            "score": float(metrics["score"]),
                            "master_updated": master_updated,
                        },
                    )
                )
            except Exception as exc:
                scene_events.put(("scene_regen_error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    # Dedicated scene-event queue avoids racing the base app event poller.
    def custom_event_poll() -> None:
        try:
            while True:
                kind, payload = scene_events.get_nowait()
                if kind == "scene_regenerated":
                    info = payload
                    app._set_busy(False)
                    app.status_var.set(
                        f"Đã tạo lại scene {info['index']:03d} · score {info['score']:.2f}"
                    )
                    app.scene_cache_status_var.set(
                        f"Scene {info['index']:03d}: OK · {info['attempts']} attempt"
                    )
                    app._append_log(
                        f"Scene {info['index']:03d} đã tạo lại: {info['path']} · "
                        f"attempt {info['attempts']} · artifact score {info['score']:.2f}"
                        + (" · WAV tổng đã cập nhật" if info["master_updated"] else "")
                    )
                elif kind == "scene_regen_error":
                    app._set_busy(False)
                    app.status_var.set(f"Lỗi tạo lại scene: {payload}")
                    app.scene_cache_status_var.set("Regenerate lỗi")
                    messagebox.showerror(
                        "Lỗi tạo lại scene", str(payload), parent=app
                    )
        except queue.Empty:
            pass
        app.after(60, custom_event_poll)

    def clear_cache() -> None:
        folder = dubbing_dir_for_current()
        path = cache_path_for(folder)
        try:
            if path.exists():
                path.unlink()
            app.scene_cache_status_var.set("Cache đã xóa · WAV scene vẫn giữ")
            app._append_log("Đã xóa metadata cache; không xóa các file scene WAV.")
        except OSError as exc:
            messagebox.showerror("Không xóa được cache", str(exc), parent=app)

    preview_btn.configure(command=preview_scene)
    regen_btn.configure(command=regenerate_scene)
    clear_cache_btn.configure(command=clear_cache)
    app.after(60, custom_event_poll)

    app._append_log(
        "Scene Workflow READY · auto detect rè/static + retry · cache/resume · "
        "preview/regenerate từng scene."
    )
