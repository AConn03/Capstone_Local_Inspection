import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import json
import os
import threading
import queue
import traceback
import sys
from PIL import Image, ImageTk

# --- Force PyTorch to report hardware crashes instead of silently dying ---
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"

from engine import RustInferenceEngine

# --- CUSTOM WIDGETS FOR A SLEEK UI ---
class SleekButton(tk.Canvas):
    """A custom rounded button with hover effects."""
    def __init__(self, parent, text, command, bg_color="#34495e", hover_color="#2c3e50", fg_color="white", width=200, height=40, radius=8, **kwargs):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, **kwargs)
        self.command = command
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.fg_color = fg_color
        self.radius = radius
        self.text = text
        self.rect = None
        self.text_id = None
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        self.bind("<ButtonRelease-1>", self.on_release)
        
        self.draw_button(self.bg_color)

    def draw_button(self, color):
        self.delete("all")
        x1, y1, x2, y2 = 0, 0, self.winfo_reqwidth(), self.winfo_reqheight()
        self.rect = self.create_polygon(
            x1+self.radius, y1, x2-self.radius, y1,
            x2, y1, x2, y1+self.radius,
            x2, y2-self.radius, x2, y2,
            x2-self.radius, y2, x1+self.radius, y2,
            x1, y2, x1, y2-self.radius,
            x1, y1+self.radius, x1, y1,
            fill=color, smooth=True
        )
        self.text_id = self.create_text(x2//2, y2//2, text=self.text, fill=self.fg_color, font=("Segoe UI", 11, "bold"))

    def on_enter(self, event): self.draw_button(self.hover_color)
    def on_leave(self, event): self.draw_button(self.bg_color)
    def on_click(self, event): self.draw_button(self.bg_color)
    def on_release(self, event): 
        self.draw_button(self.hover_color)
        if self.command: self.command()

class ToggleSwitch(tk.Canvas):
    """A modern iOS-style toggle switch."""
    def __init__(self, parent, variable, command=None, bg_off="#7f8c8d", bg_on="#27ae60", width=44, height=24, **kwargs):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, **kwargs)
        self.variable = variable
        self.command = command
        self.bg_off = bg_off
        self.bg_on = bg_on
        self.width = width
        self.height = height
        self.radius = height // 2
        
        self.bind("<Button-1>", self.toggle)
        self.variable.trace_add("write", self._on_var_change)
        self.draw_switch()

    def _on_var_change(self, *args):
        self.draw_switch()

    def draw_switch(self):
        self.delete("all")
        is_on = self.variable.get()
        color = self.bg_on if is_on else self.bg_off
        
        self.create_polygon(
            self.radius, 0, self.width-self.radius, 0,
            self.width, 0, self.width, self.radius,
            self.width, self.height-self.radius, self.width, self.height,
            self.width-self.radius, self.height, self.radius, self.height,
            0, self.height, 0, self.height-self.radius,
            0, self.radius, 0, 0,
            fill=color, smooth=True
        )
        
        knob_r = self.radius - 2
        knob_x = self.width - self.radius if is_on else self.radius
        knob_y = self.radius
        self.create_oval(knob_x-knob_r, knob_y-knob_r, knob_x+knob_r, knob_y+knob_r, fill="white", outline="")

    def toggle(self, event):
        self.variable.set(not self.variable.get())
        if self.command: self.command()

class SleekSlider(tk.Canvas):
    """A highly readable, custom-drawn canvas slider (Replaces ugly ttk.Scale)."""
    def __init__(self, parent, variable, from_, to, label_text, command=None, width=280, height=55, **kwargs):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, **kwargs)
        self.variable = variable
        self.from_ = from_
        self.to = to
        self.label_text = label_text
        self.command = command

        self.track_color = "#3f4254"
        self.fill_color = "#3498db"
        self.knob_color = "white"

        self.bind("<Button-1>", self.click)
        self.bind("<B1-Motion>", self.drag)
        self.bind("<ButtonRelease-1>", self.release)
        self.variable.trace_add("write", self.update_visuals)

        self.update_visuals()

    def get_x_for_val(self, val):
        percent = (val - self.from_) / (self.to - self.from_)
        return 15 + percent * (self.winfo_reqwidth() - 30)

    def get_val_for_x(self, x):
        percent = (x - 15) / (self.winfo_reqwidth() - 30)
        percent = max(0.0, min(1.0, percent))
        return self.from_ + percent * (self.to - self.from_)

    def update_visuals(self, *args):
        self.delete("all")
        val = self.variable.get()

        # Text Labels
        self.create_text(10, 15, text=self.label_text, fill="#ecf0f1", font=("Segoe UI", 10), anchor="w")
        display_val = int(round(val)) if val.is_integer() or self.to > 10 else round(val, 1)
        self.create_text(self.winfo_reqwidth()-10, 15, text=str(display_val), fill="#bdc3c7", font=("Segoe UI", 11, "bold"), anchor="e")

        # Track
        y = 40
        self.create_line(15, y, self.winfo_reqwidth()-15, y, fill=self.track_color, width=6, capstyle=tk.ROUND)

        # Fill
        x = self.get_x_for_val(val)
        self.create_line(15, y, x, y, fill=self.fill_color, width=6, capstyle=tk.ROUND)

        # Knob
        self.create_oval(x-8, y-8, x+8, y+8, fill=self.knob_color, outline="")

    def click(self, event):
        self.drag(event)

    def drag(self, event):
        val = self.get_val_for_x(event.x)
        self.variable.set(val)

    def release(self, event):
        val = int(round(self.variable.get()))
        self.variable.set(val)
        if self.command: self.command()

# --- MAIN APPLICATION ---
class RustApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Rust & Crack Detection System")
        self.root.geometry("1400x850")
        self.root.configure(bg="#0f1115") 
        
        # Hijack the window's top-right "X" button to route through our clean quit protocol
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        
        self.root.bind("<Escape>", self.toggle_fullscreen)
        self.root.bind("<F11>", self.toggle_fullscreen)
        
        self.engine = None 
        self.current_mode = "Idle"
        self.current_image_bgr = None 
        
        # Dual-Thread Async Architecture
        self.is_processing = False
        self.camera_thread = None
        self.ai_thread = None
        
        self.frame_queue = queue.Queue(maxsize=1) 
        self.ai_frame_queue = queue.Queue(maxsize=1) 
        
        self.overlay_lock = threading.Lock() 
        self.current_overlay_data = [] 
        
        self.current_cam_fps = 0.0
        self.current_ai_fps = 0.0
        
        self.is_loading = False
        self.is_loading_engine = False
        self.loading_angle = 0
        
        self.load_config()
        self.setup_ui()
        self.build_settings_panels()
        self.update_ui_loop()
        
        self.apply_window_state()

    def quit_app(self):
        """Cleanly shuts down all threads and exits to prove it didn't crash."""
        print("\n========================================================")
        print("[DEBUG] User initiated manual quit. Shutting down cleanly...")
        print("========================================================\n")
        self.stop_all()
        self.root.quit()
        self.root.destroy()
        sys.exit(0)

    def load_config(self):
        try:
            with open("settings.json", "r") as f:
                self.cfg = json.load(f)
        except FileNotFoundError:
            print("[WARNING] settings.json not found. Creating default.")
            self.cfg = {
                "USE_GPU": True,
                "APP_FULLSCREEN": False,
                "APP_BORDERLESS": False,
                "KEEP_ASPECT_RATIO": True, 
                "MODEL_VERSION": "rust_crack_multilabel_fast224_2026-04-15",
                "RESIZE_MODE": "Crop to Fit",
                "EDGE_ENHANCE_MODE": "None",
                "DEEP_SEARCH_MODE": False,
                "USE_8X_TTA": False,
                "GRID_SIZE": 7, 
                "MIN_RUST_CONFIDENCE": 98, 
                "MIN_CRACK_CONFIDENCE": 96,
                "SHOW_PERCENT": True, 
                "SHOW_COLORED_OVERLAY": True,
                "VIEW_EDGE_MAP_ONLY": False,
                "MAX_VIDEO_FPS": 15, 
                "INPUT_DIR": "./input_images", 
                "OUTPUT_DIR": "./output_images",
                "MODELS_DIR": "./models"
            }
            self.save_config()

    def save_config(self):
        with open("settings.json", "w") as f:
            json.dump(self.cfg, f, indent=4)
            
        if self.engine:
            self.engine.cfg.update(self.cfg)
            self.engine.cfg["MIN_RUST_CONFIDENCE"] = 0
            self.engine.cfg["MIN_CRACK_CONFIDENCE"] = 0

    def apply_window_state(self):
        fs = self.cfg.get("APP_FULLSCREEN", False)
        bl = self.cfg.get("APP_BORDERLESS", False)
        
        if fs:
            self.root.attributes("-fullscreen", True)
        else:
            self.root.attributes("-fullscreen", False)
            self.root.overrideredirect(bl) 
            
    def toggle_fullscreen(self, event=None):
        fs_var = self.setting_vars.get("APP_FULLSCREEN")
        if fs_var:
            current = fs_var[1].get()
            fs_var[1].set(not current)
            self.apply_settings_instant()

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam') 
        style.configure("TNotebook", background="#1a1c23", borderwidth=0)
        style.configure("TNotebook.Tab", background="#282a36", foreground="#bdc3c7", padding=[15, 8], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#3f4254")], foreground=[("selected", "white")])
        style.configure("TCombobox", fieldbackground="#282a36", background="#282a36", foreground="white", borderwidth=0)
        style.configure("Vertical.TScrollbar", background="#282a36", troughcolor="#1a1c23", bordercolor="#1a1c23", arrowcolor="white")

        # --- Sidebar ---
        self.sidebar = tk.Frame(self.root, width=240, bg="#1a1c23")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        title_frame = tk.Frame(self.sidebar, bg="#1a1c23")
        title_frame.pack(fill="x", pady=20)
        tk.Label(title_frame, text="RUST & CRACK", fg="white", bg="#1a1c23", font=("Segoe UI", 16, "bold")).pack()
        tk.Label(title_frame, text="VISION SYSTEM", fg="#3498db", bg="#1a1c23", font=("Segoe UI", 10, "bold")).pack()
        
        cam_frame = tk.Frame(self.sidebar, bg="#1a1c23")
        cam_frame.pack(fill="x", padx=15, pady=(10, 5))
        tk.Label(cam_frame, text="Source:", fg="#95a5a6", bg="#1a1c23", font=("Segoe UI", 9)).pack(side="left")
        self.cam_var = tk.StringVar(value="0")
        cam_combo = ttk.Combobox(cam_frame, textvariable=self.cam_var, values=["0", "1", "2", "3", "4"], width=8)
        cam_combo.pack(side="right")
        
        actions_frame = tk.Frame(self.sidebar, bg="#1a1c23")
        actions_frame.pack(fill="x", padx=15, pady=10)
        
        SleekButton(actions_frame, text="Preview Camera", command=self.start_preview, bg_color="#2c3e50", hover_color="#34495e").pack(fill="x", pady=5)
        SleekButton(actions_frame, text="Live AI Mode", command=self.start_live, bg_color="#27ae60", hover_color="#2ecc71").pack(fill="x", pady=5)
        SleekButton(actions_frame, text="Process Video", command=self.start_video, bg_color="#8e44ad", hover_color="#9b59b6").pack(fill="x", pady=5)
        SleekButton(actions_frame, text="Process Image", command=self.start_image, bg_color="#d35400", hover_color="#e67e22").pack(fill="x", pady=5)
        
        tk.Frame(self.sidebar, height=1, bg="#282a36").pack(fill="x", padx=15, pady=(20, 10))
        
        # Re-colored buttons and added Quit
        SleekButton(self.sidebar, text="Stop / Clear", command=self.stop_all, bg_color="#e67e22", hover_color="#d35400").pack(fill="x", padx=15, pady=5)
        SleekButton(self.sidebar, text="Quit Application", command=self.quit_app, bg_color="#c0392b", hover_color="#e74c3c").pack(fill="x", padx=15, pady=5)

        status_frame = tk.Frame(self.sidebar, bg="#1a1c23")
        status_frame.pack(side="bottom", fill="x", pady=20)
        
        self.status_label = tk.Label(status_frame, text="● Offline", fg="#e74c3c", bg="#1a1c23", font=("Segoe UI", 10, "bold"))
        self.status_label.pack(pady=5)
        
        fps_frame = tk.Frame(status_frame, bg="#1a1c23")
        fps_frame.pack(fill="x")
        self.cam_fps_label = tk.Label(fps_frame, text="CAM: 0.0", fg="#bdc3c7", bg="#1a1c23", font=("Segoe UI", 9))
        self.cam_fps_label.pack(side="left", padx=15)
        self.ai_fps_label = tk.Label(fps_frame, text="AI: 0.0", fg="#f1c40f", bg="#1a1c23", font=("Segoe UI", 9))
        self.ai_fps_label.pack(side="right", padx=15)

        # --- Right Settings Panel ---
        self.settings_panel = tk.Frame(self.root, width=320, bg="#1a1c23")
        self.settings_panel.pack(side="right", fill="y")
        self.settings_panel.pack_propagate(False)

        # --- Center Viewer ---
        self.center_frame = tk.Frame(self.root, bg="#0f1115")
        self.center_frame.pack(side="left", expand=True, fill="both", padx=2, pady=2)

        self.canvas = tk.Canvas(self.center_frame, bg="#0f1115", highlightthickness=0)
        self.canvas.pack(expand=True, fill="both")
        
        self.root.update_idletasks()
        self.canvas.create_text(self.canvas.winfo_width()//2, self.canvas.winfo_height()//2, 
                                text="READY", fill="#282a36", font=("Segoe UI", 48, "bold"), justify="center", tags="msg")
        self.canvas.bind("<Configure>", self.on_canvas_resize)

    def on_canvas_resize(self, event):
        cx, cy = event.width // 2, event.height // 2
        self.canvas.coords("msg", cx, cy)

    # ==========================================
    # MODERN SETTINGS PANEL
    # ==========================================
    def get_available_models(self):
        models_dir = self.cfg.get("MODELS_DIR", "./models")
        available_models = []
        if os.path.exists(models_dir):
            try: available_models = [d for d in os.listdir(models_dir) if os.path.isdir(os.path.join(models_dir, d))]
            except Exception: pass
        if not available_models:
            available_models = [self.cfg.get("MODEL_VERSION", "rust_crack_multilabel_fast224_2026-04-15")]
        return available_models

    def build_settings_panels(self):
        self.setting_vars = {}
        
        notebook = ttk.Notebook(self.settings_panel)
        notebook.pack(expand=True, fill="both", padx=5, pady=5)
        
        tab_model = tk.Frame(notebook, bg="#1a1c23")
        tab_app = tk.Frame(notebook, bg="#1a1c23")
        
        notebook.add(tab_model, text="Model")
        notebook.add(tab_app, text="App")
        
        self._build_scrollable_tab(tab_model, self._populate_model_settings)
        self._build_scrollable_tab(tab_app, self._populate_app_settings)

    def _build_scrollable_tab(self, parent, populate_func):
        canvas = tk.Canvas(parent, bg="#1a1c23", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#1a1c23")

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=parent.winfo_width())
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(canvas.find_withtag("all")[0], width=e.width))
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        populate_func(scrollable_frame)

    def apply_settings_instant(self, event=None, key_changed=None):
        try:
            for key, (v_type, var) in self.setting_vars.items():
                if v_type == "text":
                    val = var.get()
                    if val.replace('.','',1).isdigit():
                        self.cfg[key] = float(val) if '.' in val else int(val)
                    else: self.cfg[key] = val
                else: self.cfg[key] = var.get()
            
            # STRICT TYPE CASTING TO PREVENT AI ENGINE CRASHES
            self.cfg["GRID_SIZE"] = int(round(float(self.cfg.get("GRID_SIZE", 7))))
            self.cfg["MIN_RUST_CONFIDENCE"] = int(round(float(self.cfg.get("MIN_RUST_CONFIDENCE", 98))))
            self.cfg["MIN_CRACK_CONFIDENCE"] = int(round(float(self.cfg.get("MIN_CRACK_CONFIDENCE", 96))))
                
            self.save_config()
            self.apply_window_state() 

            # --- DYNAMIC GPU SWITCHING ---
            if key_changed == "USE_GPU" and self.engine is not None:
                import torch
                wants_gpu = self.cfg.get("USE_GPU", True)
                
                if wants_gpu and torch.cuda.is_available():
                    new_device = torch.device("cuda")
                else:
                    new_device = torch.device("cpu")
                    if wants_gpu:
                        messagebox.showwarning("Hardware Notice", "A CUDA-compatible GPU was not found. Defaulting to CPU processing.", parent=self.root)
                        # Force the toggle visually back off
                        self.setting_vars["USE_GPU"][1].set(False) 
                        self.cfg["USE_GPU"] = False
                        self.save_config()
                
                # Move the model dynamically
                self.engine.device = new_device
                self.engine.model = self.engine.model.to(new_device)
                print(f"[DEBUG] Model dynamically shifted to: {new_device}")
            
            # --- FAST REDRAW LOGIC ---
            if self.current_mode == "Image" and self.current_image_bgr is not None:
                fast_update_keys = ["MIN_RUST_CONFIDENCE", "MIN_CRACK_CONFIDENCE", "SHOW_COLORED_OVERLAY", "SHOW_PERCENT", "VIEW_EDGE_MAP_ONLY", "KEEP_ASPECT_RATIO"]
                
                if key_changed in fast_update_keys:
                    self.redraw_current_image_fast()
                else:
                    if hasattr(self, '_reprocess_timer'): self.root.after_cancel(self._reprocess_timer)
                    self._reprocess_timer = self.root.after(300, self.reprocess_current_image)
                    
        except ValueError:
            pass 

    # --- UI Helpers for Settings ---
    def _add_section(self, parent, title):
        tk.Frame(parent, height=1, bg="#3f4254").pack(fill="x", pady=(20, 10))
        tk.Label(parent, text=title, bg="#1a1c23", fg="#3498db", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10)

    def _add_toggle(self, parent, key, label):
        frame = tk.Frame(parent, bg="#1a1c23")
        frame.pack(fill="x", padx=15, pady=6)
        tk.Label(frame, text=label, bg="#1a1c23", fg="#ecf0f1", font=("Segoe UI", 10)).pack(side="left")
        var = tk.BooleanVar(value=self.cfg.get(key, False))
        ToggleSwitch(frame, var, command=lambda k=key: self.apply_settings_instant(key_changed=k)).pack(side="right")
        self.setting_vars[key] = ("bool", var)

    def _add_slider(self, parent, key, label, from_, to):
        frame = tk.Frame(parent, bg="#1a1c23")
        frame.pack(fill="x", padx=15, pady=6)
        var = tk.DoubleVar(value=self.cfg.get(key, from_))
        SleekSlider(frame, var, from_, to, label, command=lambda k=key: self.apply_settings_instant(key_changed=k)).pack(fill="x")
        self.setting_vars[key] = ("float", var)

    def _add_dropdown(self, parent, key, label, options):
        frame = tk.Frame(parent, bg="#1a1c23")
        frame.pack(fill="x", padx=15, pady=6)
        tk.Label(frame, text=label, bg="#1a1c23", fg="#ecf0f1", font=("Segoe UI", 10)).pack(anchor="w")
        current_val = self.cfg.get(key, options[0])
        if current_val not in options: options.append(current_val)
        var = tk.StringVar(value=current_val)
        cb = ttk.Combobox(frame, textvariable=var, values=options, state="readonly")
        cb.pack(fill="x", pady=(4,0))
        cb.bind("<<ComboboxSelected>>", lambda e, k=key: self.apply_settings_instant(key_changed=k))
        self.setting_vars[key] = ("string", var)
        
    def _add_text(self, parent, key, label):
        frame = tk.Frame(parent, bg="#1a1c23")
        frame.pack(fill="x", padx=15, pady=6)
        tk.Label(frame, text=label, bg="#1a1c23", fg="#ecf0f1", font=("Segoe UI", 10)).pack(anchor="w")
        var = tk.StringVar(value=str(self.cfg.get(key, "")))
        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(fill="x", pady=(4,0))
        entry.bind("<FocusOut>", lambda e, k=key: self.apply_settings_instant(key_changed=k))
        entry.bind("<Return>", lambda e, k=key: self.apply_settings_instant(key_changed=k))
        self.setting_vars[key] = ("text", var)

    def _populate_model_settings(self, parent):
        self._add_section(parent, "MODEL SELECTION")
        dynamic_models = self.get_available_models()
        self._add_dropdown(parent, "MODEL_VERSION", "Active Model", dynamic_models)
        self._add_toggle(parent, "USE_GPU", "Use GPU Processing (CUDA)")
        
        self._add_section(parent, "INFERENCE THRESHOLDS")
        self._add_slider(parent, "MIN_RUST_CONFIDENCE", "Min Rust Conf (%)", 0, 100)
        self._add_slider(parent, "MIN_CRACK_CONFIDENCE", "Min Crack Conf (%)", 0, 100)
        self._add_slider(parent, "GRID_SIZE", "Grid Size", 1, 20)
        
        self._add_section(parent, "ADVANCED PROCESSING")
        self._add_dropdown(parent, "RESIZE_MODE", "Resize Mode", ["Stretch (Current)", "Crop to Fit", "Pad to Fit"])
        self._add_dropdown(parent, "EDGE_ENHANCE_MODE", "Edge Enhance", ["None", "Single", "Dual"])
        self._add_toggle(parent, "DEEP_SEARCH_MODE", "Deep Search Mode")
        self._add_toggle(parent, "USE_8X_TTA", "8x TTA (Slow)")
        
        self._add_section(parent, "VISUALS")
        self._add_toggle(parent, "SHOW_COLORED_OVERLAY", "Colored Cell Overlay")
        self._add_toggle(parent, "SHOW_PERCENT", "Show Labels & %")
        self._add_toggle(parent, "VIEW_EDGE_MAP_ONLY", "View Edge Map Only")
        # Spacer
        tk.Label(parent, bg="#1a1c23").pack(pady=20)

    def _populate_app_settings(self, parent):
        self._add_section(parent, "WINDOW STATE")
        self._add_toggle(parent, "APP_FULLSCREEN", "Fullscreen Mode")
        self._add_toggle(parent, "APP_BORDERLESS", "Borderless Window")
        self._add_toggle(parent, "KEEP_ASPECT_RATIO", "Keep Aspect Ratio")
        
        self._add_section(parent, "DIRECTORIES")
        self._add_text(parent, "INPUT_DIR", "Input Directory")
        self._add_text(parent, "OUTPUT_DIR", "Output Directory")
        self._add_text(parent, "MODELS_DIR", "Models Directory")
        # Spacer
        tk.Label(parent, bg="#1a1c23").pack(pady=20)

    # ==========================================
    # ASYNC ENGINE LOADING
    # ==========================================
    def animate_loading(self, text, r=40):
        if not self.is_loading:
            self.canvas.delete("loading")
            return

        self.canvas.delete("loading")
        cx, cy = self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2
        if cx <= 10: cx, cy = 500, 350 
        
        self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline="#1a1c23", width=4, tags="loading")
        start = self.loading_angle
        self.canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=start, extent=120, outline="#3498db", width=4, style=tk.ARC, tags="loading")
        
        self.canvas.create_text(cx, cy + 60, text=text, fill="#ecf0f1", font=("Segoe UI", 12), justify="center", tags="loading")

        self.loading_angle = (self.loading_angle + 8) % 360
        self.root.after(20, lambda: self.animate_loading(text, r))

    def ensure_engine_loaded_async(self, on_success):
        if self.engine is not None:
            on_success()
            return
        if self.is_loading_engine: return
            
        self.stop_all()
        self.is_loading_engine = True
        self.is_loading = True
        self.animate_loading("Warming up Neural Engine...")

        def load_task():
            try:
                engine = RustInferenceEngine()
                self.root.after(0, lambda: self._on_engine_loaded(engine, on_success))
            except Exception as e:
                err_msg = traceback.format_exc()
                print(f"[CRITICAL ERROR] Engine load failed.\n{err_msg}")
                self.root.after(0, lambda: self._on_engine_load_failed(e, err_msg))

        threading.Thread(target=load_task, daemon=True).start()

    def _on_engine_loaded(self, engine, on_success):
        try:
            self.engine = engine
            self.engine.refresh_settings = lambda: None
            self.save_config() 
            
            self.is_loading_engine = False
            self.is_loading = False
            self.status_label.config(text="● Engine Active", fg="#2ecc71")
            self.canvas.delete("loading")
            
            print("[DEBUG] Engine successfully initialized. Firing success callback.")
            on_success()
        except Exception as e:
            print(f"[CRITICAL ERROR] Failed during engine post-load setup: {e}")
            traceback.print_exc()

    def _on_engine_load_failed(self, e, trace):
        self.is_loading_engine = False
        self.is_loading = False
        self.canvas.delete("loading")
        messagebox.showerror("Engine Error", f"Failed to load model:\n{str(e)}", parent=self.root)

    # ==========================================
    # INFERENCE & DRAWING (Dynamic Filtering)
    # ==========================================
    def draw_overlay_on_frame(self, frame, overlay_data):
        use_overlay = self.cfg.get("SHOW_COLORED_OVERLAY", False)
        overlay = frame.copy() if use_overlay else None
        
        min_rust = self.cfg.get("MIN_RUST_CONFIDENCE", 50) / 100.0
        min_crack = self.cfg.get("MIN_CRACK_CONFIDENCE", 50) / 100.0
        
        for cell in overlay_data:
            l, t, r, b = cell["box"]
            
            valid_detections = []
            for d in cell["detections"]:
                thresh = min_rust if 'rust' in d["label"].lower() else min_crack
                if d["score"] >= thresh:
                    valid_detections.append(d)
            
            if valid_detections:
                is_crack = any("crack" in d["label"].lower() for d in valid_detections)
                color = (255, 60, 0) if is_crack else (0, 0, 230) 
                
                cv2.rectangle(frame, (l, t), (r, b), color, 2)
                if overlay is not None:
                    cv2.rectangle(overlay, (l, t), (r, b), color, -1)
                    
                if self.cfg.get("SHOW_PERCENT", True):
                    labels = ", ".join([f"{d['label']} {int(d['score']*100)}%" for d in valid_detections])
                    (tw, th), _ = cv2.getTextSize(labels, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
                    cv2.rectangle(frame, (l, t), (l+tw+10, t+25), (0,0,0), -1)
                    cv2.putText(frame, labels, (l+5, t+18), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
        
        if overlay is not None:
            cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)
            
        return frame

    def redraw_current_image_fast(self):
        if self.current_image_bgr is None: return
        frame = self.current_image_bgr.copy()
        
        with self.overlay_lock:
            overlay_data = list(self.current_overlay_data)
        
        frame = self.draw_overlay_on_frame(frame, overlay_data)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(frame_rgb)
        
        if not self.frame_queue.empty():
            try: self.frame_queue.get_nowait()
            except queue.Empty: pass
        self.frame_queue.put(pil_img)

    # ==========================================
    # THREADS
    # ==========================================
    def worker_camera_reader(self, source, use_ai=True):
        print(f"[DEBUG] Attempting to open camera source: {source}")
        
        if isinstance(source, int):
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
            if not cap.isOpened():
                print(f"[DEBUG] CAP_DSHOW failed, falling back to default for camera {source}")
                cap = cv2.VideoCapture(source)
        else:
            cap = cv2.VideoCapture(source)

        if not cap.isOpened():
            print(f"[ERROR] Failed to open camera source: {source}")
            self.is_processing = False
            return

        print(f"[DEBUG] Camera {source} successfully opened.")
        last_time = time.time()
        
        while self.is_processing and cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame is None: 
                print("[WARNING] Frame read failed. Did the camera disconnect?")
                break

            curr_time = time.time()
            self.current_cam_fps = 1.0 / (curr_time - last_time) if curr_time - last_time > 0 else 0
            last_time = curr_time
            
            if use_ai:
                if self.ai_frame_queue.empty(): self.ai_frame_queue.put(frame.copy())
                with self.overlay_lock: current_overlay = list(self.current_overlay_data)
                frame = self.draw_overlay_on_frame(frame, current_overlay)
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)
            
            if not self.frame_queue.empty():
                try: self.frame_queue.get_nowait()
                except queue.Empty: pass
            self.frame_queue.put(pil_img)
            
        cap.release()
        print("[DEBUG] Camera worker thread ended.")

    def worker_ai_inference(self):
        last_time = time.time()
        while self.is_processing:
            try: frame = self.ai_frame_queue.get(timeout=0.5) 
            except queue.Empty: continue 
                
            try:
                results = self.engine.analyze_frame(frame)
                with self.overlay_lock: self.current_overlay_data = results
                
                curr_time = time.time()
                self.current_ai_fps = 1.0 / (curr_time - last_time) if curr_time - last_time > 0 else 0
                last_time = curr_time
            except Exception as e:
                print(f"[ERROR] AI Inference failed: {e}")
                traceback.print_exc()

    def worker_process_single_image(self):
        if self.current_image_bgr is None: return
        frame = self.current_image_bgr.copy()
        try:
            print("[DEBUG] Handing frame to RustInferenceEngine...")
            results = self.engine.analyze_frame(frame)
            print("[DEBUG] Engine successfully returned results!")
            with self.overlay_lock:
                self.current_overlay_data = results
                
            frame = self.draw_overlay_on_frame(frame, results)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)
            
            if not self.frame_queue.empty():
                try: self.frame_queue.get_nowait()
                except queue.Empty: pass
            self.frame_queue.put(pil_img)
        except Exception as e:
            print(f"[ERROR] Single image inference failed: {e}")
            traceback.print_exc()
        finally:
            self.is_loading = False

    # ==========================================
    # MODES
    # ==========================================
    def start_preview(self):
        self.stop_all()
        try: cam_idx = int(self.cam_var.get())
        except ValueError: cam_idx = 0

        self.current_mode = "Preview"
        self.is_processing = True
        self.camera_thread = threading.Thread(target=self.worker_camera_reader, args=(cam_idx, False), daemon=True)
        self.camera_thread.start()

    def start_live(self):
        self.stop_all()
        def on_ready():
            print("[DEBUG] on_ready triggered for Live Mode!")
            try: cam_idx = int(self.cam_var.get())
            except ValueError: cam_idx = 0

            self.current_mode = "Live"
            self.is_processing = True
            self.camera_thread = threading.Thread(target=self.worker_camera_reader, args=(cam_idx, True), daemon=True)
            self.ai_thread = threading.Thread(target=self.worker_ai_inference, daemon=True)
            self.camera_thread.start()
            self.ai_thread.start()
            print("[DEBUG] Live Mode threads successfully started!")
        self.ensure_engine_loaded_async(on_ready)

    def start_video(self):
        self.stop_all()
        path = filedialog.askopenfilename(filetypes=[("Video Files", "*.mp4 *.avi *.mov *.mkv")])
        if path:
            def on_ready():
                self.current_mode = "Video"
                self.is_processing = True
                self.camera_thread = threading.Thread(target=self.worker_camera_reader, args=(path, True), daemon=True)
                self.ai_thread = threading.Thread(target=self.worker_ai_inference, daemon=True)
                self.camera_thread.start()
                self.ai_thread.start()
            self.ensure_engine_loaded_async(on_ready)

    def start_image(self):
        self.stop_all()
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp")])
        if path:
            def on_ready():
                print(f"[DEBUG] on_ready triggered for Image Mode! Path: {path}") 
                frame = cv2.imread(path)
                if frame is not None:
                    self.current_mode = "Image"
                    self.current_image_bgr = frame
                    self.reprocess_current_image()
                    print("[DEBUG] Image sent to processing thread!") 
                else:
                    print(f"[ERROR] cv2.imread returned None for path: {path}")
                    messagebox.showerror("Image Error", "Could not read image file. Path might be invalid.", parent=self.root)
            self.ensure_engine_loaded_async(on_ready)

    def reprocess_current_image(self):
        if self.current_mode == "Image" and self.current_image_bgr is not None:
            self.canvas.delete("all")
            self.is_loading = True
            self.animate_loading("Analyzing Image...")
            threading.Thread(target=self.worker_process_single_image, daemon=True).start()

    def stop_all(self):
        self.is_processing = False 
        self.is_loading = False 
        self.current_mode = "Idle"
        self.current_image_bgr = None
        
        with self.overlay_lock: self.current_overlay_data = [] 
        self.current_cam_fps = 0.0
        self.current_ai_fps = 0.0
        
        if self.camera_thread and self.camera_thread.is_alive(): self.camera_thread.join(timeout=0.5) 
        if self.ai_thread and self.ai_thread.is_alive(): self.ai_thread.join(timeout=0.5) 
        
        while not self.frame_queue.empty():
            try: self.frame_queue.get_nowait()
            except queue.Empty: pass
        while not self.ai_frame_queue.empty():
            try: self.ai_frame_queue.get_nowait()
            except queue.Empty: pass
            
        self.canvas.delete("all")
        self.cam_fps_label.config(text="CAM: 0.0")
        self.ai_fps_label.config(text="AI: 0.0")
        
        cx, cy = self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2
        if cx <= 10: cx, cy = 500, 350
        self.canvas.create_text(cx, cy, text="STANDBY", fill="#282a36", font=("Segoe UI", 48, "bold"), justify="center", tags="msg")

        if self.engine:
            import torch
            if torch.cuda.is_available(): torch.cuda.empty_cache()

    # ==========================================
    # RENDER ENGINE
    # ==========================================
    def render_to_canvas(self, pil_img):
        try:
            self.is_loading = False 
            self.canvas.delete("loading")
            self.canvas.delete("msg") 
            
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
            if cw > 10 and ch > 10:
                if not self.cfg.get("KEEP_ASPECT_RATIO", True):
                    pil_img = pil_img.resize((cw, ch), Image.Resampling.LANCZOS)
                else:
                    pil_img.thumbnail((cw, ch), Image.Resampling.LANCZOS)
                
            self.tk_img = ImageTk.PhotoImage(image=pil_img)
            x_offset = (cw - self.tk_img.width()) // 2 if cw > 10 else 0
            y_offset = (ch - self.tk_img.height()) // 2 if ch > 10 else 0
            
            self.canvas.create_image(x_offset, y_offset, anchor="nw", image=self.tk_img)
        except Exception as e:
            pass

    def update_ui_loop(self):
        try:
            img = self.frame_queue.get_nowait()
            self.render_to_canvas(img)
            
            if self.current_mode in ["Live", "Video"]:
                self.cam_fps_label.config(text=f"CAM: {self.current_cam_fps:.1f}")
                self.ai_fps_label.config(text=f"AI: {self.current_ai_fps:.1f}")
            elif self.current_mode == "Preview":
                self.cam_fps_label.config(text=f"CAM: {self.current_cam_fps:.1f}")
                self.ai_fps_label.config(text="AI: OFF")
                
        except queue.Empty:
            pass
            
        self.root.after(16, self.update_ui_loop) 

if __name__ == "__main__":
    root = tk.Tk()
    app = RustApp(root)
    root.mainloop()