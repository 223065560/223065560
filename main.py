import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import datetime

OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "GeoSight_Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Light palette ─────────────────────────────────────────────────────────────
C = {
    "bg":         "#f0f4f8",
    "panel":      "#ffffff",
    "panel2":     "#f8fafc",
    "border":     "#cbd5e1",
    "accent":     "#0891b2",
    "accent2":    "#16a34a",
    "warn":       "#dc2626",
    "blue":       "#2563eb",
    "text":       "#1e293b",
    "subtext":    "#64748b",
    "input_bg":   "#f8fafc",
    "btn":        "#e2e8f0",
    "btn_hov":    "#cbd5e1",
    "run_bg":     "#0891b2",
    "run_hov":    "#0e7490",
    "tag_veg":    "#dcfce7",  "tag_veg_t":   "#166534",
    "tag_built":  "#fee2e2",  "tag_built_t": "#991b1b",
    "tag_water":  "#dbeafe",  "tag_water_t": "#1e40af",
    "tag_bare":   "#fef3c7",  "tag_bare_t":  "#92400e",
    "purple":     "#7c3aed",
}

MONO = "Consolas"
SANS = "Segoe UI"
LOG_FONT   = (MONO, 10)
INPUT_FONT = (MONO, 10)
BTN_FONT   = (SANS, 10, "bold")
LABEL_FONT = (SANS, 10)
TITLE_FONT = (MONO, 11, "bold")


class HoverBtn(tk.Button):
    def __init__(self, parent, bg_n, bg_h, fg_n=None, fg_h=None, **kw):
        fg_n = fg_n or C["text"]; fg_h = fg_h or C["accent"]
        super().__init__(parent, bg=bg_n, fg=fg_n,
                         activebackground=bg_h, activeforeground=fg_h,
                         relief="flat", bd=0, **kw)
        self.bind("<Enter>", lambda e: self.config(bg=bg_h, fg=fg_h))
        self.bind("<Leave>", lambda e: self.config(bg=bg_n, fg=fg_n))


class Sep(tk.Frame):
    def __init__(self, p, **kw):
        super().__init__(p, height=1, bg=C["border"], **kw)


class ScrollableSidebar(tk.Frame):
    """
    Reliable scrollable sidebar.
    Usage: sidebar = ScrollableSidebar(parent, bg=colour, width=px)
           sidebar.pack(side="left", fill="y")
           # put widgets inside sidebar.inner
    """
    def __init__(self, parent, bg, width, **kw):
        # Outer container — fixed width, never shrinks
        super().__init__(parent, bg=bg, width=width, **kw)
        self.pack_propagate(False)

        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self._sb     = ttk.Scrollbar(self, orient="vertical",
                                     command=self._canvas.yview)
        self.inner   = tk.Frame(self._canvas, bg=bg)

        self._win = self._canvas.create_window(
            (0, 0), window=self.inner, anchor="nw")

        # Resize inner frame width when canvas resizes
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        # Update scrollregion when inner frame content changes
        self.inner.bind("<Configure>", self._on_inner_resize)

        self._canvas.configure(yscrollcommand=self._sb.set)
        self._sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        # Mousewheel — bind to canvas and inner frame
        for widget in (self._canvas, self.inner):
            widget.bind("<MouseWheel>",    self._on_mousewheel)
            widget.bind("<Button-4>",      self._on_mousewheel)  # Linux
            widget.bind("<Button-5>",      self._on_mousewheel)  # Linux

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._win, width=event.width)

    def _on_inner_resize(self, event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_mousewheel(self, event):
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            self._canvas.yview_scroll(int(-1*(event.delta/120)), "units")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GeoSight — Land Cover Analysis")
        self.geometry("1180x800")
        self.minsize(1000, 680)
        self.configure(bg=C["bg"])

        self.img1_path   = tk.StringVar()
        self.img2_path   = tk.StringVar()
        self.year1       = tk.StringVar(value="1994")
        self.year2       = tk.StringVar(value="2024")
        self.pixel_size  = tk.StringVar(value="900")
        self.area_name   = tk.StringVar(value="")
        self.do_preproc  = tk.BooleanVar(value=False)
        self.do_accuracy = tk.BooleanVar(value=True)
        self.gcp_path    = tk.StringVar(value="")
        self._running    = False

        self._setup_styles()
        self._build()

    def _setup_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Teal.Horizontal.TProgressbar",
                    troughcolor=C["border"], background=C["accent2"],
                    bordercolor=C["border"], thickness=4)
        s.configure("TScrollbar",
                    background=C["btn"], troughcolor=C["panel"],
                    bordercolor=C["border"], arrowcolor=C["subtext"])
        s.configure("TCheckbutton",
                    background=C["panel2"], foreground=C["text"],
                    font=LABEL_FONT)
        s.map("TCheckbutton",
              background=[("active", C["panel2"])],
              foreground=[("active", C["accent"])])

    def _build(self):
        self._topbar()
        content = tk.Frame(self, bg=C["bg"])
        content.pack(fill="both", expand=True)

        # Sidebar: fixed-width scrollable panel
        self._sb_widget = ScrollableSidebar(content, bg=C["panel"], width=360)
        self._sb_widget.pack(side="left", fill="y")
        Sep(content).pack(side="left", fill="y")

        main = tk.Frame(content, bg=C["bg"])
        main.pack(side="right", fill="both", expand=True)

        self._sidebar(self._sb_widget.inner)
        self._main_panel(main)

        Sep(self).pack(fill="x", side="bottom")
        self._statusbar()

    # ── Top bar ───────────────────────────────────────────────────────────────
    def _topbar(self):
        bar = tk.Frame(self, bg=C["panel"], height=60)
        bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Frame(bar, bg=C["accent"], width=6).pack(side="left", fill="y")
        tk.Label(bar, text="GeoSight", bg=C["panel"], fg=C["accent"],
                 font=(MONO, 18, "bold")).pack(side="left", padx=(16,4), pady=10)
        tk.Label(bar, text="Land Cover Analysis Platform",
                 bg=C["panel"], fg=C["subtext"],
                 font=(SANS, 10)).pack(side="left", pady=10)
        right = tk.Frame(bar, bg=C["panel"])
        right.pack(side="right", padx=16)
        for txt, col in [("RF Classifier", C["accent"]), ("v5.1", C["subtext"])]:
            tk.Label(right, text=f" {txt} ", bg=C["btn"], fg=col,
                     font=(MONO, 8), padx=6, pady=3).pack(side="right", padx=4)

    # ── Status bar ────────────────────────────────────────────────────────────
    def _statusbar(self):
        bar = tk.Frame(self, bg=C["panel"], height=28)
        bar.pack(fill="x", side="bottom"); bar.pack_propagate(False)
        self.status_var = tk.StringVar(value="Ready  ·  Load two images to begin")
        tk.Label(bar, textvariable=self.status_var,
                 bg=C["panel"], fg=C["subtext"],
                 font=(MONO, 9), anchor="w").pack(side="left", padx=12, fill="y")
        self.progress = ttk.Progressbar(bar, mode="indeterminate",
                                         style="Teal.Horizontal.TProgressbar",
                                         length=110)
        self.progress.pack(side="right", padx=12, pady=7)

    # ── Sidebar content ───────────────────────────────────────────────────────
    def _sidebar(self, p):
        px = 14   # horizontal padding

        # Study area
        self._sh(p, "◉  STUDY AREA", px)
        self._entry(p, self.area_name, placeholder="e.g. Rundu, Namibia", px=px)
        self._gap(p, 10)

        # Image 1
        self._sh(p, "◉  IMAGE 1  —  Base Year", px)
        self._file_picker(p, self.img1_path, self.year1, hint="e.g. 1994", px=px)
        self._gap(p, 10)

        # Image 2
        self._sh(p, "◉  IMAGE 2  —  Analysis Year", px)
        self._file_picker(p, self.img2_path, self.year2, hint="e.g. 2024", px=px)
        self._gap(p, 10)

        # Settings
        self._sh(p, "◉  SETTINGS", px)

        srow = tk.Frame(p, bg=C["panel"])
        srow.pack(fill="x", padx=px, pady=(0,3))
        tk.Label(srow, text="Pixel area (m²)", bg=C["panel"],
                 fg=C["text"], font=LABEL_FONT).pack(side="left")
        tk.Entry(srow, textvariable=self.pixel_size,
                 bg=C["input_bg"], fg=C["accent"],
                 insertbackground=C["accent"],
                 relief="solid", bd=1,
                 font=INPUT_FONT, width=7).pack(side="right", ipady=4)

        tk.Label(p, text="  Landsat 30 m = 900  |  Sentinel 10 m = 100",
                 bg=C["panel"], fg=C["subtext"],
                 font=(SANS, 8)).pack(anchor="w", padx=px, pady=(0,8))

        # Preprocessing toggle
        self._toggle_card(p, px,
            var=self.do_preproc,
            icon="⚙", label="Preprocess images",
            desc="Auto-scales bands & computes NDVI/NDBI.\nUse for raw Landsat/Sentinel exports.")

        # Accuracy assessment toggle
        self._toggle_card(p, px,
            var=self.do_accuracy,
            icon="✓", label="Run accuracy assessment",
            desc="Computes OA, Kappa, PA/UA/F1 per class\nand confusion matrix (~30 s extra).")

        # GCP file picker
        self._sh(p, "◉  GROUND CONTROL POINTS  (optional)", px)
        self._gcp_picker(p, px)
        self._gap(p, 8)

        Sep(p).pack(fill="x", padx=px)
        self._gap(p, 10)

        # Run button
        self.run_btn = HoverBtn(p, bg_n=C["run_bg"], bg_h=C["run_hov"],
                                fg_n="white", fg_h="white",
                                text="▶   RUN ANALYSIS",
                                font=(MONO, 12, "bold"),
                                cursor="hand2", pady=13,
                                command=self._run)
        self.run_btn.pack(fill="x", padx=px, pady=(0,6))

        HoverBtn(p, bg_n=C["btn"], bg_h=C["btn_hov"],
                 fg_n=C["subtext"], fg_h=C["accent"],
                 text="📁  Open Output Folder",
                 font=BTN_FONT, cursor="hand2", pady=8,
                 command=self._open_output).pack(fill="x", padx=px, pady=(0,14))

        # Classification scheme
        Sep(p).pack(fill="x", padx=px)
        self._gap(p, 10)
        self._sh(p, "◉  CLASSIFICATION SCHEME", px)

        scheme = tk.Frame(p, bg=C["panel2"], bd=1, relief="solid",
                          highlightbackground=C["border"])
        scheme.pack(fill="x", padx=px, pady=(0,16))

        for name, dot_col, bg_col, fg_col in [
            ("Vegetation", "#16a34a", C["tag_veg"],   C["tag_veg_t"]),
            ("Built-up",   "#dc2626", C["tag_built"],  C["tag_built_t"]),
            ("Water",      "#2563eb", C["tag_water"],  C["tag_water_t"]),
            ("Bare Land",  "#d97706", C["tag_bare"],   C["tag_bare_t"]),
        ]:
            row = tk.Frame(scheme, bg=bg_col)
            row.pack(fill="x", padx=6, pady=3)
            tk.Label(row, text="●", bg=bg_col, fg=dot_col,
                     font=(MONO, 13), padx=6, pady=5).pack(side="left")
            tk.Label(row, text=name, bg=bg_col, fg=fg_col,
                     font=(SANS, 10, "bold"), pady=5).pack(side="left")

        self._gap(p, 8)

    # ── Main log panel ────────────────────────────────────────────────────────
    def _main_panel(self, parent):
        hdr = tk.Frame(parent, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(hdr, text="Analysis Log", bg=C["bg"], fg=C["text"],
                 font=(MONO, 12, "bold")).pack(side="left")
        HoverBtn(hdr, bg_n=C["btn"], bg_h=C["btn_hov"],
                 fg_n=C["subtext"], fg_h=C["warn"],
                 text="Clear", font=(SANS, 9),
                 cursor="hand2", padx=10, pady=4,
                 command=self._clear_log).pack(side="right")
        Sep(parent).pack(fill="x", pady=(10, 0))

        log_frame = tk.Frame(parent, bg=C["bg"])
        log_frame.pack(fill="both", expand=True, padx=2, pady=2)
        self.log = tk.Text(log_frame, bg=C["bg"], fg=C["text"],
                           font=LOG_FONT, relief="flat",
                           state="disabled", wrap="word",
                           insertbackground=C["accent"],
                           selectbackground=C["border"],
                           padx=18, pady=14, spacing1=2, spacing3=2)
        self.log.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(log_frame, command=self.log.yview)
        vsb.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=vsb.set)

        self.log.tag_configure("head",   foreground=C["accent"],  font=(MONO, 10, "bold"))
        self.log.tag_configure("ok",     foreground=C["accent2"])
        self.log.tag_configure("warn",   foreground=C["warn"])
        self.log.tag_configure("sub",    foreground=C["subtext"])
        self.log.tag_configure("normal", foreground=C["text"])
        self.log.tag_configure("blue",   foreground=C["blue"])
        self.log.tag_configure("acc",    foreground=C["purple"])
        self.log.tag_configure("gcp",    foreground="#d97706")

        self._log("  ╔══════════════════════════════════════════╗", "head")
        self._log("  ║   GeoSight  —  Land Cover Analysis  v5.1║", "head")
        self._log("  ║   RF Classifier + Accuracy Assessment    ║", "head")
        self._log("  ╚══════════════════════════════════════════╝\n", "head")
        self._log("  Load two images and click ▶ RUN ANALYSIS.", "sub")
        self._log("  Optionally add a GCP CSV for real ground-truth validation.\n", "sub")

    # ── Widget helpers ────────────────────────────────────────────────────────
    def _sh(self, p, text, px=14):
        tk.Label(p, text=text, bg=C["panel"], fg=C["accent"],
                 font=TITLE_FONT, anchor="w").pack(fill="x", pady=(12,5), padx=px)

    def _gap(self, p, h=8):
        tk.Frame(p, bg=C["panel"], height=h).pack(fill="x")

    def _entry(self, p, var, placeholder="", px=14):
        e = tk.Entry(p, textvariable=var, bg=C["input_bg"], fg=C["text"],
                     insertbackground=C["accent"], relief="solid", bd=1,
                     font=INPUT_FONT)
        e.pack(fill="x", ipady=6, padx=px, pady=(0,4))
        if placeholder and not var.get():
            e.insert(0, placeholder); e.config(fg=C["subtext"])
            e.bind("<FocusIn>",  lambda ev: (e.delete(0,"end"), e.config(fg=C["text"]))
                                 if e.get()==placeholder else None)
            e.bind("<FocusOut>", lambda ev: (e.insert(0, placeholder), e.config(fg=C["subtext"]))
                                 if not e.get() else None)

    def _file_picker(self, p, path_var, year_var, hint="", px=14):
        frow = tk.Frame(p, bg=C["panel"])
        frow.pack(fill="x", padx=px, pady=(0,4))
        tk.Entry(frow, textvariable=path_var, bg=C["input_bg"], fg=C["subtext"],
                 insertbackground=C["accent"], relief="solid", bd=1,
                 font=(MONO, 9)).pack(side="left", fill="x", expand=True,
                                      ipady=6, padx=(0,6))
        HoverBtn(frow, bg_n=C["btn"], bg_h=C["btn_hov"],
                 fg_n=C["text"], fg_h=C["accent"],
                 text="Browse", font=BTN_FONT, cursor="hand2",
                 padx=10, pady=6,
                 command=lambda: self._browse(path_var)).pack(side="right")
        yrow = tk.Frame(p, bg=C["panel"])
        yrow.pack(fill="x", padx=px, pady=(0,2))
        tk.Label(yrow, text="Year:", bg=C["panel"], fg=C["subtext"],
                 font=LABEL_FONT, width=5, anchor="w").pack(side="left")
        tk.Entry(yrow, textvariable=year_var, bg=C["input_bg"], fg=C["accent"],
                 insertbackground=C["accent"], relief="solid", bd=1,
                 font=INPUT_FONT, width=8).pack(side="left", ipady=4, padx=(4,8))
        tk.Label(yrow, text=hint, bg=C["panel"], fg=C["subtext"],
                 font=(SANS, 8)).pack(side="left")

    def _toggle_card(self, p, px, var, icon, label, desc):
        card = tk.Frame(p, bg=C["panel2"], bd=1, relief="solid",
                        highlightbackground=C["border"])
        card.pack(fill="x", padx=px, pady=(0,6))
        ttk.Checkbutton(card, text=f"  {icon}  {label}",
                        variable=var).pack(anchor="w", padx=8, pady=(6,2))
        tk.Label(card, text=desc, bg=C["panel2"], fg=C["subtext"],
                 font=(SANS, 8), justify="left",
                 wraplength=300).pack(anchor="w", padx=28, pady=(0,6))

    def _gcp_picker(self, p, px):
        """
        CSV/TXT with columns: longitude, latitude, class_id
        class_id: 1=Vegetation 2=Built-up 3=Water 4=Bare Land
        """
        card = tk.Frame(p, bg=C["panel2"], bd=1, relief="solid",
                        highlightbackground=C["border"])
        card.pack(fill="x", padx=px, pady=(0,6))

        # Info label
        tk.Label(card,
                 text="Load a CSV with your collected field points.\n"
                      "Required columns: longitude, latitude, class_id\n"
                      "class_id: 1=Vegetation  2=Built-up  3=Water  4=Bare Land",
                 bg=C["panel2"], fg=C["subtext"],
                 font=(SANS, 8), justify="left",
                 wraplength=300).pack(anchor="w", padx=10, pady=(8,4))

        frow = tk.Frame(card, bg=C["panel2"])
        frow.pack(fill="x", padx=10, pady=(0,8))
        tk.Entry(frow, textvariable=self.gcp_path,
                 bg=C["input_bg"], fg=C["subtext"],
                 insertbackground=C["accent"], relief="solid", bd=1,
                 font=(MONO, 8)).pack(side="left", fill="x", expand=True,
                                      ipady=5, padx=(0,6))
        HoverBtn(frow, bg_n=C["btn"], bg_h=C["btn_hov"],
                 fg_n=C["text"], fg_h=C["accent"],
                 text="Browse", font=BTN_FONT, cursor="hand2",
                 padx=8, pady=5,
                 command=self._browse_gcp).pack(side="right")

        # Template download hint
        tk.Label(card,
                 text="No GCPs? The self-consistency assessment runs automatically.",
                 bg=C["panel2"], fg=C["accent"],
                 font=(SANS, 8), justify="left",
                 wraplength=300).pack(anchor="w", padx=10, pady=(0,6))

    # ── Log / status ──────────────────────────────────────────────────────────
    def _log(self, msg, tag="normal"):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n", tag)
        self.log.configure(state="disabled")
        self.log.see("end")
        self.update_idletasks()

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _status(self, msg):
        self.status_var.set(msg)
        self.update_idletasks()

    def _browse(self, var):
        p = filedialog.askopenfilename(
            filetypes=[("GeoTIFF", "*.tif *.tiff"), ("All", "*.*")])
        if p: var.set(p)

    def _browse_gcp(self):
        p = filedialog.askopenfilename(
            filetypes=[("CSV/TXT", "*.csv *.txt"), ("All", "*.*")])
        if p: self.gcp_path.set(p)

    def _open_output(self):
        if sys.platform   == "win32":  os.startfile(OUTPUT_DIR)
        elif sys.platform == "darwin": os.system(f"open '{OUTPUT_DIR}'")
        else:                          os.system(f"xdg-open '{OUTPUT_DIR}'")

    # ── Analysis ──────────────────────────────────────────────────────────────
    def _run(self):
        if not self.img1_path.get() or not self.img2_path.get():
            messagebox.showerror("Missing Input",
                                  "Please select both satellite image files.")
            return
        if self._running: return
        self._running = True
        self.run_btn.config(state="disabled", text="⏳  Running…")
        self.progress.start(12)
        threading.Thread(target=self._analyse, daemon=True).start()

    def _done(self):
        self._running = False
        self.run_btn.config(state="normal", text="▶   RUN ANALYSIS")
        self.progress.stop()

    def _analyse(self):
        try:
            from classify import classify_file
            from change   import detect_change, change_summary
            from areas    import calculate_areas, save_csv
            from export   import (save_classification_map, save_change_map,
                                   save_side_by_side, save_area_chart,
                                   save_confidence_map, save_accuracy_report)

            px   = float(self.pixel_size.get())
            y1   = self.year1.get() or "Year1"
            y2   = self.year2.get() or "Year2"
            name = self.area_name.get().strip() or "StudyArea"
            ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out  = os.path.join(OUTPUT_DIR, f"{name.replace(' ','_')}_{ts}")
            os.makedirs(out, exist_ok=True)

            p1 = self.img1_path.get()
            p2 = self.img2_path.get()
            gcp_file = self.gcp_path.get().strip() or None

            self._log(f"\n{'─'*54}", "sub")
            self._log(f"  ANALYSIS STARTED  ·  {name}", "head")
            self._log(f"  {y1}  →  {y2}  ·  pixel area: {px} m²", "sub")
            if gcp_file:
                self._log(f"  GCPs: {os.path.basename(gcp_file)}", "gcp")
            self._log(f"{'─'*54}\n", "sub")

            # Step 0: Preprocess
            if self.do_preproc.get():
                from preprocess import preprocess
                self._log("[0/7]  Preprocessing images…", "head")
                self._status("Preprocessing…")
                pp1 = os.path.join(out, f"preprocessed_{y1}.tif")
                pp2 = os.path.join(out, f"preprocessed_{y2}.tif")
                preprocess(p1, pp1, log_fn=lambda m: self._log(m, "sub"))
                preprocess(p2, pp2, log_fn=lambda m: self._log(m, "sub"))
                p1, p2 = pp1, pp2
                self._log("       ✓ Both images preprocessed", "ok")
            else:
                self._log("[0/7]  Preprocessing: skipped", "sub")

            # Steps 1 & 2: Classify
            self._status(f"Classifying {y1}…")
            self._log(f"\n[1/7]  Classifying  {y1}…", "head")
            c1, conf1, profile, nd1 = classify_file(
                p1, log_fn=lambda m: self._log(m, "sub"))
            transform = profile.get("transform")
            crs       = profile.get("crs")
            self._log(f"       ✓  {y1} classification complete", "ok")

            self._status(f"Classifying {y2}…")
            self._log(f"\n[2/7]  Classifying  {y2}…", "head")
            c2, conf2, _, nd2 = classify_file(
                p2, log_fn=lambda m: self._log(m, "sub"))
            self._log(f"       ✓  {y2} classification complete", "ok")

            # Step 3: Accuracy
            if self.do_accuracy.get():
                from accuracy import run_accuracy_assessment
                self._log(f"\n[3/7]  Accuracy Assessment…", "acc")
                self._status("Accuracy assessment…")

                # GCP-based if file provided, else self-consistency
                if gcp_file:
                    self._log("       Using ground control points for validation", "gcp")
                    from accuracy import run_gcp_assessment
                    acc1 = run_gcp_assessment(
                        p1, gcp_file, profile,
                        log_fn=lambda m: self._log(m, "gcp"))
                    acc2 = run_gcp_assessment(
                        p2, gcp_file, profile,
                        log_fn=lambda m: self._log(m, "gcp"))
                else:
                    self._log("       No GCPs — running self-consistency assessment", "acc")
                    acc1 = run_accuracy_assessment(
                        p1, log_fn=lambda m: self._log(m, "acc"))
                    acc2 = run_accuracy_assessment(
                        p2, log_fn=lambda m: self._log(m, "acc"))

                save_accuracy_report(acc1,
                    os.path.join(out, f"accuracy_{y1}.png"), y1)
                save_accuracy_report(acc2,
                    os.path.join(out, f"accuracy_{y2}.png"), y2)
                self._log("       ✓  Accuracy reports saved", "ok")
            else:
                self._log(f"\n[3/7]  Accuracy Assessment: skipped", "sub")
                acc1 = acc2 = None

            # Step 4: Change detection
            self._status("Change detection…")
            self._log(f"\n[4/7]  Change detection…", "head")
            c2, change_map = detect_change(c1, c2, nd1, nd2)
            transitions = change_summary(c1, c2, px)
            self._log("       ✓  Transitions detected:", "ok")
            for k, v in transitions.items():
                self._log(f"          {k}  :  {v} km²", "blue")

            # Step 5: Areas
            self._status("Calculating areas…")
            self._log(f"\n[5/7]  Area statistics…", "head")
            df = calculate_areas(c1, c2, px)
            self._log("\n" + df.to_string(index=False) + "\n", "normal")
            save_csv(df, os.path.join(out, f"area_stats_{y1}_{y2}.csv"))
            self._log("       ✓  CSV saved", "ok")

            # Step 6: Maps
            self._status("Generating maps…")
            self._log(f"\n[6/7]  Generating maps…", "head")
            save_classification_map(c1,
                os.path.join(out, f"classification_{y1}.png"),
                f"{name}  —  Land Cover  ({y1})", transform, crs)
            save_classification_map(c2,
                os.path.join(out, f"classification_{y2}.png"),
                f"{name}  —  Land Cover  ({y2})", transform, crs)
            save_side_by_side(c1, c2,
                os.path.join(out, f"comparison_{y1}_{y2}.png"),
                y1, y2, transform, crs)
            save_change_map(change_map,
                os.path.join(out, f"change_map_{y1}_{y2}.png"),
                y1, y2, transform, crs)
            save_area_chart(df,
                os.path.join(out, f"area_chart_{y1}_{y2}.png"), y1, y2)
            save_confidence_map(conf1, nd1,
                os.path.join(out, f"confidence_{y1}.png"),
                f"Classification Confidence  —  {y1}")
            save_confidence_map(conf2, nd2,
                os.path.join(out, f"confidence_{y2}.png"),
                f"Classification Confidence  —  {y2}")
            self._log("       ✓  All maps saved", "ok")

            # Step 7: Summary
            self._log(f"\n[7/7]  Summary", "head")
            if acc1:
                method = "GCP validation" if gcp_file else "Self-consistency"
                self._log(f"       Method: {method}", "acc")
                self._log(f"       {y1}  OA={acc1['overall_accuracy']}%  κ={acc1['kappa']}", "acc")
                self._log(f"       {y2}  OA={acc2['overall_accuracy']}%  κ={acc2['kappa']}", "acc")

            self._log(f"\n{'─'*54}", "sub")
            self._log(f"  ✅  ANALYSIS COMPLETE", "head")
            self._log(f"  Output: {out}", "ok")
            self._log(f"{'─'*54}\n", "sub")
            self._status(f"✅  Complete  ·  {out}")

        except Exception as e:
            import traceback
            self._log(f"\n❌  ERROR: {e}", "warn")
            self._log(traceback.format_exc(), "sub")
            self._status("❌  Error — see log for details")
        finally:
            self.after(0, self._done)


if __name__ == "__main__":
    app = App()
    app.mainloop()
