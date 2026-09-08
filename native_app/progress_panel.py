from __future__ import annotations


def install_progress_panel(app, ns: dict[str, object], studio) -> None:
    """Add an always-visible render status/progress panel below SCENE TOOLS.

    This mirrors the app's existing status_var/progress_var, so it does not
    change the synthesis worker or cache logic.
    """

    tk = ns["tk"]
    ttk = ns["ttk"]

    app.render_percent_var = tk.StringVar(value="0%")
    app.render_detail_var = tk.StringVar(value="Sẵn sàng")

    panel = ttk.Frame(studio, style="CardAlt.TFrame")
    panel.grid(row=8, column=0, columnspan=6, sticky="ew", padx=16, pady=(0, 14))
    panel.columnconfigure(0, weight=1)

    top = ttk.Frame(panel, style="CardAlt.TFrame")
    top.grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 5))
    top.columnconfigure(0, weight=1)

    status_label = ttk.Label(
        top,
        textvariable=app.status_var,
        style="Stat.TLabel",
        anchor="w",
    )
    status_label.grid(row=0, column=0, sticky="ew")

    percent_label = ttk.Label(
        top,
        textvariable=app.render_percent_var,
        style="Stat.TLabel",
        width=7,
        anchor="e",
    )
    percent_label.grid(row=0, column=1, padx=(12, 0), sticky="e")

    bar = ttk.Progressbar(
        panel,
        variable=app.progress_var,
        maximum=100.0,
        style="Green.Horizontal.TProgressbar",
    )
    bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 5))

    detail = ttk.Label(
        panel,
        textvariable=app.render_detail_var,
        style="StatMuted.TLabel",
        anchor="w",
    )
    detail.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 9))

    last_progress = -1.0
    last_busy = None

    def refresh() -> None:
        nonlocal last_progress, last_busy
        try:
            value = max(0.0, min(100.0, float(app.progress_var.get())))
        except Exception:
            value = 0.0
        busy = bool(getattr(app, "_busy", False))
        workers = max(1, min(10, int(getattr(app, "_parallel_workers", 1) or 1)))

        app.render_percent_var.set(f"{value:.0f}%")

        # Keep a compact second line so the user can instantly tell whether
        # generation is active even when the main status text is long.
        cache_text = ""
        cache_var = getattr(app, "scene_cache_status_var", None)
        if cache_var is not None:
            try:
                cache_text = str(cache_var.get()).strip()
            except Exception:
                cache_text = ""

        if busy:
            detail_text = f"Đang render · {workers} luồng"
            if cache_text:
                detail_text += f" · {cache_text}"
        elif value >= 99.9:
            detail_text = "Hoàn tất"
            if cache_text:
                detail_text += f" · {cache_text}"
        else:
            detail_text = cache_text or "Sẵn sàng"
        app.render_detail_var.set(detail_text)

        # Force a visual repaint only when state changes; avoids unnecessary Tk work.
        if value != last_progress or busy != last_busy:
            try:
                panel.update_idletasks()
            except Exception:
                pass
            last_progress = value
            last_busy = busy

        app.after(120, refresh)

    refresh()
    app._append_log("Progress panel READY · luôn hiển thị trạng thái, %, cache và số luồng render.")
