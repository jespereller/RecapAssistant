import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkFont
from threading import Thread
import os
import traceback
from collections import Counter 
import time
import csv
import random
import math
import uuid
import sys

from ttkbootstrap import Style, utility
utility.enable_high_dpi_awareness()
from ttkbootstrap.widgets import Progressbar

# Import project modules
from config import (
    WINDOW_TITLE, WINDOW_GEOMETRY, DEFAULT_THEME, EDITING_STYLES,
    METHOD_MEDIAPIPE # Keep for info label, though not used directly in logic here
)

EDITING_STYLE_LOGIC = {
     "Fast-paced": {"base_multipliers": [2, 4, 8],"weights": [0.2, 0.4, 0.4]},
     "Standard": {"base_multipliers": [2, 4, 8, 16],"weights": [0.1, 0.4, 0.4, 0.1]},
     "Relaxed": {"base_multipliers": [4, 8, 16],"weights": [0.2, 0.4, 0.4]},
     "_Default": {"base_multipliers": [2, 4, 8, 16],"weights": [0.1, 0.3, 0.3, 0.3]}
}

DEFAULT_FPS = 24.0
MIN_CLIP_FRAMES = 12
MIN_SLIDER_S = max(1.0, MIN_CLIP_FRAMES / DEFAULT_FPS if DEFAULT_FPS > 0 else 1.0)

from mediapipe_utils import load_object_detector, release_detector
from media_processing import get_bpm_and_offset, detect_video_moments
from resolve_script_generator import create_script

def resource_path(relative_path):
    """ Get absolute path to resource, needed for PyInstaller (when creating .EXE)"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class VideoAnalysisApp:
    def __init__(self, root):
        self.root = root
        self.style = Style(theme=DEFAULT_THEME)
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_GEOMETRY)

        try:
            icon_path = resource_path("assets/icon.ico")
            self.root.iconbitmap(icon_path)
            print(f"Icon set from: {icon_path}")
        except tk.TclError:
            print("Warning: Could not set window icon (.ico not found or invalid format?).")
        except Exception as e:
            print(f"Warning: An unexpected error occurred setting the icon: {e}")

        self._initialize_state()

        print("Loading MediaPipe object detector...")
        self.object_detector = load_object_detector()
        self.detector_loaded = self.object_detector is not None
        print(f"MediaPipe Detector Loaded: {self.detector_loaded}")

        self.create_widgets()
        self._configure_text_tags()
        self._set_initial_status_message()

        try:
            self.check_button_states()
        except tk.TclError:
            print("Warning: Initial check_button_states skipped (widgets initializing).")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _initialize_state(self):
        """Sets or resets all state variables."""
        self.audio_file_path = None
        self.video_files = []
        self.bpm = None
        self.beat_duration_s = None
        self.audio_offset_s = 0.0
        self.audio_duration_s = None
        self.people_moments = []
        self.other_scene_moments = []
        self.moment_counts = Counter()
        self.audio_processed = False
        self.video_processed = False
        self.is_processing = False
        self.audio_analysis_s = None
        self.video_analysis_s = None
        self.prepared_clips_cache = [] # looks like this - {'moment': (s, e, lbl, fname), 'calculated_duration_sec': float}
        self.simulated_total_duration_s = None
        self.video_errors = [] # List of (filename, error_string) tuples
        self.processing_id = None # UUID to track current processing task
        
        # Use hasattr check for robustness during initialization/reset
        if hasattr(self, 'target_duration_var'):
            self.target_duration_var.set(100.0) # Default value
        else:
            self.target_duration_var = tk.DoubleVar(value=100.0)


    def _set_initial_status_message(self):
        """Sets the initial status."""
        if self.detector_loaded:
            self.update_ui_status("Status: Ready. Please analyze audio first.")
        else:
            self.update_ui_status("Status: ERROR - MediaPipe detector failed! Video analysis disabled.", error=True)

    def _format_time(self, seconds):
        """Formats seconds into MM:SS or H:MM:SS string."""
        if seconds is None: return "N/A"
        try:
            sec_float = float(seconds)
            if not math.isfinite(sec_float) or sec_float < 0: return "N/A"
            total_seconds = int(round(sec_float))
            # Use divmod for cleaner calculation
            if total_seconds < 3600:
                minutes, seconds = divmod(total_seconds, 60)
                return f"{minutes:02d}:{seconds:02d}"
            else:
                minutes, seconds = divmod(total_seconds, 60)
                hours, minutes = divmod(minutes, 60)
                return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        except (ValueError, TypeError):
            return "N/A"

    def _s2f(self, s, fps=DEFAULT_FPS):
        """Converts seconds to frames."""
        return int(round(s * fps))

    def _f2s(self, f, fps=DEFAULT_FPS):
        """Converts frames to seconds."""
        return float(f) / fps if fps > 0 else 0.0

    def create_widgets(self):
        """Creates and packs all the UI widgets."""
        title_label = ttk.Label(self.root, text="Recap Assistant for DaVinci Resolve", font=("Arial", 12, "bold"))
        title_label.pack(padx=10, pady=(10, 5), side=tk.TOP, fill=tk.X)

        # Files selection
        file_frame = ttk.Frame(self.root, padding=5)
        file_frame.pack(side=tk.TOP, fill=tk.X, padx=10)
        self.upload_audio_button = ttk.Button(file_frame, text="1. Analyze Audio", command=self.select_audio_file, bootstyle="primary")
        self.upload_audio_button.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
        self.upload_video_button = ttk.Button(file_frame, text="2. Analyze Video(s)", command=self.select_video_files, bootstyle="primary")
        self.upload_video_button.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)

        # Options for user
        options_frame = ttk.Frame(self.root, padding=5)
        options_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        style_label = ttk.Label(options_frame, text="Editing Style*:")
        style_label.pack(side=tk.LEFT, padx=(0, 5))
        self.style_var = tk.StringVar(value="")
        self.style_combobox = ttk.Combobox(options_frame, textvariable=self.style_var, values=EDITING_STYLES, state="readonly", width=10)
        self.style_var.trace_add("write", self._on_style_change) # Use trace_add
        self.style_combobox.pack(side=tk.LEFT, padx=5)
        # Show detection method (even if only one option currently)
        method_info_label = ttk.Label(options_frame, text="(Analysis: MediaPipe Object Detection)")
        method_info_label.pack(side=tk.RIGHT, padx=(10, 5))

        # Duration / Slider
        self.est_length_label = ttk.Label(self.root, text="Audio: N/A | Target: N/A | Avail. Clips: N/A", anchor="w", font=("Arial", 9))
        self.est_length_label.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(5, 0))
        slider_frame = ttk.Frame(self.root, padding=(10, 0, 10, 5))
        slider_frame.pack(side=tk.TOP, fill=tk.X)
        slider_frame.columnconfigure(1, weight=1) # Make slider expand
        slider_title_label = ttk.Label(slider_frame, text="Target Duration:")
        slider_title_label.grid(row=0, column=0, padx=(0, 10), sticky="w")
        self.length_slider = ttk.Scale(slider_frame, from_=MIN_SLIDER_S, to=100.0, orient=tk.HORIZONTAL, variable=self.target_duration_var, command=self._on_slider_change, state=tk.DISABLED)
        self.length_slider.grid(row=0, column=1, sticky="ew")
        self.slider_label = ttk.Label(slider_frame, text="N/A", width=7, anchor="e") # Fixed width for label
        self.slider_label.grid(row=0, column=2, padx=(10, 0), sticky="e")

        # Progress bar
        self.progress_bar = Progressbar(self.root, mode='determinate', maximum=100, value=0, bootstyle="info-striped", length=300)
        self.progress_bar.pack(side=tk.TOP, pady=5, fill=tk.X, padx=10)

        # Results textbox
        result_label_frame = ttk.Frame(self.root)
        result_label_frame.pack(side=tk.TOP, pady=(5, 5), padx=10, fill=tk.BOTH, expand=True)
        bg_color = self.style.lookup('TFrame', 'background')
        fg_color = self.style.lookup('TLabel', 'foreground')
        
        # Use default font
        default_font_obj = tkFont.nametofont("TkDefaultFont")
        font_size = default_font_obj.actual("size")
        result_font = (default_font_obj.actual("family"), font_size + 1 if font_size > 0 else 10) # Make slightly larger
        self.result_display = tk.Text(result_label_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, padx=5, pady=5, relief=tk.FLAT, background=bg_color, foreground=fg_color, font=result_font)
        scrollbar = ttk.Scrollbar(result_label_frame, orient=tk.VERTICAL, command=self.result_display.yview, bootstyle="round")
        self.result_display.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bottom buttons
        bottom_button_frame = ttk.Frame(self.root)
        bottom_button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(5, 10))
        bottom_button_frame.columnconfigure(0, weight=2)
        bottom_button_frame.columnconfigure(1, weight=1)
        bottom_button_frame.columnconfigure(2, weight=1)
        self.create_script_button = ttk.Button(bottom_button_frame, text="Create Script", command=self.run_create_script, bootstyle="success")
        self.create_script_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.reset_button = ttk.Button(bottom_button_frame, text="Reset", command=self.reset_application, bootstyle="warning")
        self.reset_button.grid(row=0, column=1, sticky="ew", padx=(5, 5))
        self.save_csv_button = ttk.Button(bottom_button_frame, text="Save CSV", command=self.save_to_csv, bootstyle="info-outline")
        self.save_csv_button.grid(row=0, column=2, sticky="ew", padx=(5, 0))


    def _configure_text_tags(self):
        """Configure 'bold' and 'error' tags for the result Text widget."""
        try:
            # Check widget exists?
            if hasattr(self, 'result_display') and self.result_display.winfo_exists():
                base_font = tkFont.Font(font=self.result_display.cget("font"))
                family = base_font.actual("family")
                size = base_font.actual("size")

                if family and size > 0:
                    bold_font = tkFont.Font(family=family, size=size, weight="bold")
                    self.result_display.tag_configure("bold", font=bold_font)

                    error_font = tkFont.Font(family=family, size=size)
                    # Get theme's danger color, use red as fallback
                    danger_color = self.style.colors.get('danger')
                    if danger_color is None: # Check if the key was not found
                        danger_color = 'red'
                    self.result_display.tag_configure("error", font=error_font, foreground=danger_color)
                else:
                    print("Warning: Could not get valid default font properties for text tags.")
        except Exception as e:
            print(f"Warning: Failed to configure text tags - {e}")

    # UI Update Methods
    def update_ui_status(self, message, error=False):
        """Updates the result Text widget, applying 'error' tag if needed."""
        if hasattr(self, 'result_display') and self.result_display.winfo_exists():
            try:
                self.result_display.config(state=tk.NORMAL)
                self.result_display.delete("1.0", tk.END)

                # Clear previous tags (except selection) before inserting
                for tag in self.result_display.tag_names():
                    if tag not in ("sel", "bold", "error"): # Keep configured tags
                        self.result_display.tag_remove(tag, "1.0", tk.END)

                # Set default foreground color
                fg_color = self.style.lookup('TLabel', 'foreground', default='black')
                self.result_display.config(fg=fg_color)

                # Insert message + apply tag if necessary
                if error:
                    # Check if 'error' tag successfully configured
                    if "error" in self.result_display.tag_names():
                        self.result_display.insert(tk.END, message, "error")
                    else:
                        # Fallback if tag config failed
                        self.result_display.insert(tk.END, f"ERROR: {message}")
                        self.result_display.config(fg='red')
                else:
                    self.result_display.insert(tk.END, message)

                self.result_display.config(state=tk.DISABLED)
                self.root.update_idletasks()
            except tk.TclError as e:
                print(f"Error updating UI status: {e}")

    def set_progress(self, value=0, maximum=100):
        """Sets the progress bar to a specific value."""
        if hasattr(self, 'progress_bar') and self.progress_bar.winfo_exists():
            try:
                self.progress_bar.stop()
                safe_maximum = max(1, maximum)
                safe_value = min(max(0, value), safe_maximum)
                self.progress_bar.config(mode='determinate', maximum=safe_maximum, value=safe_value)
            except tk.TclError as e:
                print(f"Error setting progress bar: {e}")

    def start_indeterminate_progress(self):
        """Starts the indeterminate progress bar animation."""
        if hasattr(self, 'progress_bar') and self.progress_bar.winfo_exists():
            try:
                self.set_progress(0) # Reset to 0 first
                self.progress_bar.config(mode='indeterminate')
                self.progress_bar.start(10) # Start animation (10 ms) - to be changed?
                self.root.update_idletasks()
            except tk.TclError as e:
                print(f"Error starting indeterminate progress: {e}")

    def stop_progress(self):
        """Stops progress bar animation and resets to 0."""
        if hasattr(self, 'progress_bar') and self.progress_bar.winfo_exists():
            try:
                self.progress_bar.stop()
                self.progress_bar.config(mode='determinate', value=0, maximum=100)
                self.root.update_idletasks()
            except tk.TclError as e:
                print(f"Error stopping progress bar: {e}")

    def check_button_states(self):
        """Enables/Disables UI controls based on application state."""
        widget_names = [
            'upload_audio_button', 'upload_video_button', 'create_script_button',
            'reset_button', 'style_combobox', 'save_csv_button', 'length_slider'
        ]
        if not all(hasattr(self, name) and getattr(self, name, None) and getattr(self, name).winfo_exists() for name in widget_names):
            print("Debug: Not all widgets ready for state check.") # Debug for buttons missing
            return

        style_selected = hasattr(self, 'style_var') and self.style_var.get() in EDITING_STYLES

        can_adjust_or_save = (self.audio_processed and self.video_processed and not self.is_processing and not self.video_errors)

        can_create_script = (self.audio_processed and (self.video_processed or self.video_errors) and style_selected and self.detector_loaded)

        # Determine states when processing
        if self.is_processing:
            audio_state = tk.DISABLED
            video_state = tk.DISABLED
            script_state = tk.DISABLED
            combo_state = tk.DISABLED
            slider_state = tk.DISABLED
            save_csv_state = tk.DISABLED
        else:
            # Enable audio if not yet processed
            audio_state = tk.NORMAL if not self.audio_processed else tk.DISABLED
            # Enable video only if audio is done, video not yet done, and detector loaded
            video_state = tk.NORMAL if (self.audio_processed and not (self.video_processed or self.video_errors) and self.detector_loaded) else tk.DISABLED
            # Enable script creation at the end
            script_state = tk.NORMAL if can_create_script else tk.DISABLED
            # Combobox always readable when not processing
            combo_state = "readonly"
            # Enable slider/save based on their condition
            slider_state = tk.NORMAL if can_adjust_or_save else tk.DISABLED
            save_csv_state = tk.NORMAL if can_adjust_or_save else tk.DISABLED

        # Reset button always enabled
        reset_state = tk.NORMAL

        # configure widget states catching potential TclErrors
        try:
            self.upload_audio_button.config(state=audio_state)
            self.upload_video_button.config(state=video_state)
            self.create_script_button.config(state=script_state)
            self.reset_button.config(state=reset_state)
            self.style_combobox.config(state=combo_state)
            self.save_csv_button.config(state=save_csv_state)
            self.length_slider.config(state=slider_state)
        except tk.TclError as e:
            print(f"Warning: Error configuring button states: {e}")

    def _update_summary_display(self, processing_errors=None):
        """Updates the result Text widget with a formatted summary."""
        if not self.audio_processed:
            self.update_ui_status("Status: Please analyze audio first.")
            return
        if not hasattr(self, 'result_display') or not self.result_display.winfo_exists():
            return

        try:
            self.result_display.config(state=tk.NORMAL)
            self.result_display.delete("1.0", tk.END)
            self._configure_text_tags()

            # Audio Info 
            self.result_display.insert(tk.END, "Audio Analysis Results:\n")
            bpm_str = f"{self.bpm:.2f}" if self.bpm else "N/A"
            self.result_display.insert(tk.END, "  Estimated BPM: ")
            self.result_display.insert(tk.END, f"{bpm_str}\n", "bold")
            audio_len_str = self._format_time(self.audio_duration_s)
            self.result_display.insert(tk.END, f"  Audio Duration: {audio_len_str}\n")
            time_audio_str = self._format_time(self.audio_analysis_s)
            self.result_display.insert(tk.END, f"  Analysis time: {time_audio_str}\n")

            # Video Info
            if self.video_processed or self.video_errors: # If video analysis was attempted
                self.result_display.insert(tk.END, "\nVideo Analysis Results:\n")
                total_clips = sum(self.moment_counts.values()) if self.moment_counts else 0
                self.result_display.insert(tk.END, "  Total Clips Found: ")
                self.result_display.insert(tk.END, f"{total_clips}\n", "bold")
                # Use the simulated duration based on selected style
                video_clips_total_str = self._format_time(self.simulated_total_duration_s)
                self.result_display.insert(tk.END, f"  Avail. Clips Duration: {video_clips_total_str}\n")
                time_video_str = self._format_time(self.video_analysis_s)
                self.result_display.insert(tk.END, f"  Analysis time: {time_video_str}\n")

                # Display Errors
                final_errors = processing_errors if processing_errors else self.video_errors
                if final_errors:
                    self.result_display.insert(tk.END, f"\nProcessing completed with {len(final_errors)} error(s):\n", "error")
                    # Show first few errors inline
                    for i, (fname, err_str) in enumerate(final_errors):
                        if i < 5:
                             self.result_display.insert(tk.END, f"  - {fname}: {err_str}\n", "error")
                        elif i == 5:
                             self.result_display.insert(tk.END, "  ... (additional errors logged)\n", "error")
                             break
            elif self.is_processing and self.video_files:
                 self.result_display.insert(tk.END, "\nVideo Analysis: In Progress...\n")
            else:
                 self.result_display.insert(tk.END, "\nVideo Analysis: Not started.\n")

            # Total Time
            if self.audio_analysis_s is not None and self.video_analysis_s is not None:
                total_time = self.audio_analysis_s + self.video_analysis_s
                total_time_str = self._format_time(total_time)
                self.result_display.insert(tk.END, "\nTotal processing time: ", "bold")
                self.result_display.insert(tk.END, f"{total_time_str}\n", "bold")

                self.result_display.insert(tk.END, f"TIP: If you are not satisfied with the generated video, just\nclick 'Create Script' again for a different result - no re-analysis required!")


            self.result_display.config(state=tk.DISABLED)
        except tk.TclError as e:
            print(f"Error updating summary display: {e}")


    def _simulate_prep_clip(self, moment, style):
        """Simulates clip duration adjustment based on style and beat duration. Returns duration in seconds or None."""
        # Needs beat duration to function
        if not self.beat_duration_s or self.beat_duration_s <= 0: return None

        start_s, end_s, _, _ = moment # Unpack moment tuple
        original_duration_s = end_s - start_s
        if original_duration_s <= 0: return None

        # Convert to frames for beat-based calculation
        original_duration_f = self._s2f(original_duration_s)
        beat_f = self._s2f(self.beat_duration_s)
        if beat_f <= 0: return None

        final_duration_f = 0
        chosen_multiplier = 1 # Default multiplier

        # Get style parameters or default
        style_params = EDITING_STYLE_LOGIC.get(style, EDITING_STYLE_LOGIC.get("_Default"))
        base_multipliers = sorted(style_params.get("base_multipliers", [1])) # Ensure sorted
        base_weights = style_params.get("weights")

        # Only adjust if clip is at least one beat long
        if original_duration_f >= beat_f:
            # Find max possible multiplier based on original duration
            max_possible_multiplier = math.floor(original_duration_f / beat_f)

            # Filter multipliers and their corresponding weights
            valid_multipliers = []
            valid_indices = []
            for i, m in enumerate(base_multipliers):
                if max_possible_multiplier >= m:
                    valid_multipliers.append(m)
                    valid_indices.append(i)

            # Ensure we have at least one multiplier (use the smallest if needed)
            if not valid_multipliers:
                valid_multipliers = [base_multipliers[0]] if base_multipliers else [1]
                valid_indices = [0] if base_multipliers else []

            # Calculate weights for the valid multipliers
            weights = None
            if base_weights and len(base_weights) == len(base_multipliers) and valid_indices:
                temp_weights = [base_weights[i] for i in valid_indices]
                sum_w = sum(temp_weights)
                if sum_w > 0: # Normalize weights
                    weights = [w / sum_w for w in temp_weights]

            # Choose a multiplier
            if valid_multipliers:
                if weights and len(weights) == len(valid_multipliers):
                    try: # Use weighted choice if possible
                        chosen_multiplier = random.choices(valid_multipliers, weights=weights, k=1)[0]
                    except Exception as e: # Fallback if weights are invalid
                        print(f"Warning: random.choices failed (weights invalid?), using random.choice. Error: {e}")
                        chosen_multiplier = random.choice(valid_multipliers)
                else: # Use uniform random choice if weights are not available/valid
                    chosen_multiplier = random.choice(valid_multipliers)

            final_duration_f = chosen_multiplier * beat_f
        else:
            # If clip is shorter than a beat, use its original duration
            # Note: Filtering in detect_video_moments might make this rare
            final_duration_f = original_duration_f

        # Ensure final duration meets minimum clip length requirement (in frames)
        final_duration_f = max(MIN_CLIP_FRAMES, final_duration_f)

        # Convert back to seconds for return value
        return self._f2s(final_duration_f)


    def _simulate_prep_and_get_duration(self, selected_style):
        """Simulates clip preparation for all moments, populates cache, returns total duration (seconds)."""
        # Requires video analysis attempted and beat duration known
        if not (self.video_processed or self.video_errors) or not self.beat_duration_s:
            print("Warning: Cannot simulate clip prep - video/beat data missing.")
            return [], None # Return empty list and None duration

        print(f"Simulating clip preparation for style '{selected_style}'...")
        prepared_clips = []
        total_simulated_seconds = 0.0
        all_moments = (self.people_moments or []) + (self.other_scene_moments or [])

        if not all_moments:
            print("No video moments found to simulate.")
            return [], 0.0

        simulation_count = 0
        for moment_data in all_moments:
            # Simulate the duration calculation for this moment and style
            calculated_duration_s = self._simulate_prep_clip(moment_data, selected_style)

            # Only include clips with a valid positive duration
            if calculated_duration_s is not None and calculated_duration_s > 0:
                # Store original moment tuple and its calculated duration
                prepared_info = {
                    "moment": moment_data,
                    "calculated_duration_sec": calculated_duration_s # Use calculated duration
                 }
                prepared_clips.append(prepared_info)
                total_simulated_seconds += calculated_duration_s
                simulation_count += 1

        print(f"Simulation complete. Calculated total duration from {simulation_count} clips: {total_simulated_seconds:.2f}s.")
        # Return the list of prepared clip info and the total duration
        return prepared_clips, total_simulated_seconds


    def _calculate_and_configure_slider(self):
        """Runs simulation, updates total duration, configures slider range/value, updates labels."""
        # Check required UI elements exist
        widgets_to_check = ['est_length_label', 'length_slider', 'slider_label', 'style_var']
        if not all(hasattr(self, w) and getattr(self, w, None) for w in widgets_to_check):
             print("Warning: UI elements for slider/length calculation not ready.")
             return
        # Check widgets that need winfo_exists (Tkinter widgets)
        tk_widgets = ['est_length_label', 'length_slider', 'slider_label']
        if not all(getattr(self, w).winfo_exists() for w in tk_widgets if hasattr(self,w) and getattr(self,w)):
             print("Warning: Tkinter UI elements for slider/length not ready.")
             return


        selected_style = self.style_var.get()

        # Check conditions required for calculation
        conditions_met = (
            self.audio_processed and self.audio_duration_s is not None and
            (self.video_processed or self.video_errors) and # Video analysis attempted
            selected_style in EDITING_STYLES and
            self.beat_duration_s is not None # Beat duration needed
        )

        # Initialize display strings
        audio_duration_str = self._format_time(self.audio_duration_s) if self.audio_duration_s else "N/A"
        video_clips_total_str = "N/A"
        target_str = "N/A"
        slider_enabled = False # Default slider state

        if conditions_met:
            print(f"Recalculating video clip total duration for style: {selected_style}")
            # Run simulation
            # This populates self.prepared_clips_cache and returns the total duration
            self.prepared_clips_cache, self.simulated_total_duration_s = self._simulate_prep_and_get_duration(selected_style)
            video_clips_total_str = self._format_time(self.simulated_total_duration_s)

            # Configure Slider
            if self.simulated_total_duration_s is not None and self.simulated_total_duration_s > 0:
                audio_len = self.audio_duration_s
                video_len = self.simulated_total_duration_s

                try:
                    # Slider max is MIN(audio length, total calculated clip length)
                    actual_max_duration = min(audio_len, video_len)
                    # Ensure max is not less than min slider value
                    slider_max_value = max(actual_max_duration, MIN_SLIDER_S)
                    slider_min_value = MIN_SLIDER_S

                    # Ensure 'to' > 'from' for the scale widget
                    if slider_max_value <= slider_min_value:
                        slider_max_value = slider_min_value + 0.1 # Add small delta

                    self.length_slider.config(from_=slider_min_value, to=slider_max_value)

                    # Set initial slider value to the maximum possible usable duration
                    initial_slider_value = actual_max_duration
                    # Clamp value within the configured slider range
                    initial_slider_value = max(slider_min_value, min(initial_slider_value, slider_max_value))
                    self.target_duration_var.set(initial_slider_value)

                    # Update labels
                    target_str = self._format_time(initial_slider_value)
                    self.slider_label.config(text=target_str)
                    slider_enabled = True # Mark slider as successfully configured

                except tk.TclError as e:
                    print(f"Error configuring slider TclError: {e}")
                    slider_enabled = False
                except Exception as e:
                    print(f"Unexpected error configuring slider: {e}")
                    slider_enabled = False
            else:
                # Simulation resulted in 0 or error, reset relevant state
                video_clips_total_str = "0s / Error"
                target_str = "N/A"
                slider_enabled = False
                self.prepared_clips_cache = [] # Clear cache if simulation failed
                self.simulated_total_duration_s = None

        else: # Conditions not met
            self.simulated_total_duration_s = None
            self.prepared_clips_cache = []
            video_clips_total_str = "N/A"
            target_str = "N/A (Analyze/Select Style)"
            slider_enabled = False

        # Reset Slider if necessary
        if not slider_enabled:
            try:
                if hasattr(self, 'length_slider') and self.length_slider.winfo_exists():
                    self.length_slider.config(state=tk.DISABLED, from_=MIN_SLIDER_S, to=100.0) # Reset range
                if hasattr(self, 'slider_label') and self.slider_label.winfo_exists():
                    self.slider_label.config(text="N/A")
                if hasattr(self, 'target_duration_var'):
                    self.target_duration_var.set(100.0) # Reset variable
            except tk.TclError: pass # Ignore errors if widgets destroyed

        # Update the main estimate label (always)
        try:
            if hasattr(self, 'est_length_label') and self.est_length_label.winfo_exists():
                self.est_length_label.config(text=f"Audio: {audio_duration_str} | Target: {target_str} | Avail. Clips: {video_clips_total_str}")
        except tk.TclError: pass

        self.root.update_idletasks() # Process UI updates


    # Event Handlers / Actions
    def _on_style_change(self, *args):
        """Call when editing style combobox changes."""
        selected_style = self.style_var.get()
        print(f"Style changed to: '{selected_style}'")
        # Recalculate length/slider config if analysis already done
        if self.audio_processed and (self.video_processed or self.video_errors):
             self._calculate_and_configure_slider()
        self.check_button_states()


    def _on_slider_change(self, value=None):
        """Call when slider value changes. Updates labels."""
        # Check required UI elements exist and target_duration_var exists
        if not all(hasattr(self, w) for w in ['slider_label', 'est_length_label', 'target_duration_var']): return
        if not all(getattr(self, w, None) and getattr(self,w).winfo_exists() for w in ['slider_label', 'est_length_label'] if hasattr(self, w)): return


        try:
            current_target_s = self.target_duration_var.get()
            target_str = self._format_time(current_target_s)

            # Update the label next to the slider
            self.slider_label.config(text=target_str)

            # Update the main estimate label dynamically
            audio_duration_str = self._format_time(self.audio_duration_s) if hasattr(self,'audio_duration_s') else "N/A"
            video_clips_total_str = self._format_time(self.simulated_total_duration_s) if hasattr(self,'simulated_total_duration_s') else "N/A"
            self.est_length_label.config(text=f"Audio: {audio_duration_str} | Target: {target_str} | Avail. Clips: {video_clips_total_str}")

            self.root.update_idletasks()
        except tk.TclError as e:
             print(f"Error during slider change update (TclError): {e}")
        except AttributeError as e:
             print(f"Attribute Error during slider change update: {e}") # Catch if state vars missing
        except Exception as e:
             print(f"Unexpected error in _on_slider_change: {e}")


    def reset_application(self):
        """Resets application state and UI to initial values."""
        was_processing = self.is_processing
        self.is_processing = False # Stop processing flag first
        self.processing_id = uuid.uuid4() # Generate new ID to invalidate pending callbacks
        if was_processing:
            print("Interrupting ongoing processing...")
            self.stop_progress() # Stop progress bar immediately

        print("Resetting application state...")
        self._initialize_state() # Reset backend state variables

        # Reset UI elements safely
        try:
            if hasattr(self, 'progress_bar') and self.progress_bar.winfo_exists(): self.stop_progress()
            if hasattr(self, 'style_var') and hasattr(self, 'style_combobox') and self.style_combobox.winfo_exists(): self.style_var.set("")
            if hasattr(self, 'est_length_label') and self.est_length_label.winfo_exists():
                self.est_length_label.config(text="Audio: N/A | Target: N/A | Avail. Clips: N/A")
            if hasattr(self, 'target_duration_var'): self.target_duration_var.set(100.0) # Reset tk variable
            if hasattr(self, 'length_slider') and self.length_slider.winfo_exists():
                self.length_slider.config(state=tk.DISABLED, from_=MIN_SLIDER_S, to=100.0) # Reset range/state
            if hasattr(self, 'slider_label') and self.slider_label.winfo_exists(): self.slider_label.config(text="N/A")
            if hasattr(self, 'result_display') and self.result_display.winfo_exists():
                self.result_display.config(state=tk.NORMAL); self.result_display.delete("1.0", tk.END); self.result_display.config(state=tk.DISABLED)

            # Set initial status message (checks detector) and update button states
            self._set_initial_status_message()
            self.check_button_states()
            print("Application reset complete.")
        except tk.TclError as e:
            print(f"Error resetting UI elements: {e}")


    def select_audio_file(self):
        """Handles audio file selection and starts analysis thread."""
        if self.is_processing:
            messagebox.showwarning("Busy", "Analysis is already in progress.")
            return
        file_path = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=[("Audio Files", "*.wav *.mp3 *.flac *.aac *.ogg"), ("All Files", "*.*")]
        )
        if file_path:
            self.reset_application() # Reset state before starting new analysis
            self.audio_file_path = file_path
            # Start processing
            run_id = uuid.uuid4(); self.processing_id = run_id
            self.is_processing = True
            self.update_ui_status(f"Starting Audio Analysis: {os.path.basename(file_path)}...")
            self.start_indeterminate_progress()
            self.check_button_states()
            # Run analysis in a separate thread
            thread = Thread(target=self._run_audio_analysis, args=(file_path, run_id), daemon=True)
            thread.start()

    def select_video_files(self):
        """Handles video file selection and starts analysis thread."""
        if self.is_processing:
            messagebox.showwarning("Busy", "Analysis is already in progress.")
            return
        # Prerequisites check
        if not self.audio_processed or self.beat_duration_s is None or self.audio_duration_s is None:
            messagebox.showerror("Prerequisite Missing", "Please analyze an audio file successfully first (requires BPM and duration).")
            return
        if not self.detector_loaded:
            messagebox.showerror("Error", "MediaPipe object detector not loaded. Cannot analyze video.")
            return

        file_paths = filedialog.askopenfilenames(
            title="Select Video File(s)",
            filetypes=[("Video Files", "*.mp4 *.avi *.mov *.mkv *.webm"), ("All Files", "*.*")]
        )
        if file_paths:
            # Reset only video-related state and UI components
            self.video_files = list(file_paths)
            self.video_processed = False
            self.people_moments.clear()
            self.other_scene_moments.clear()
            self.moment_counts.clear()
            self.video_analysis_s = None
            self.video_errors = []
            self.prepared_clips_cache = []
            self.simulated_total_duration_s = None

            # Reset relevant UI parts safely
            try:
                if hasattr(self, 'est_length_label') and self.est_length_label.winfo_exists():
                    audio_len_str = self._format_time(self.audio_duration_s)
                    self.est_length_label.config(text=f"Audio: {audio_len_str} | Target: N/A (Analyzing) | Avail. Clips: N/A")
                if hasattr(self, 'length_slider') and self.length_slider.winfo_exists():
                    self.length_slider.config(state=tk.DISABLED)
                if hasattr(self, 'target_duration_var'):
                    self.target_duration_var.set(100.0) # Reset slider variable
                if hasattr(self, 'slider_label') and self.slider_label.winfo_exists():
                    self.slider_label.config(text="N/A")
            except tk.TclError as e:
                print(f"Error resetting video UI elements before analysis: {e}")

            # Start processing
            run_id = uuid.uuid4(); self.processing_id = run_id
            self.is_processing = True
            self.update_ui_status(f"Analyzing {len(self.video_files)} video file(s)...")
            self.start_indeterminate_progress()
            self.check_button_states()
            # Run analysis in a separate thread
            thread = Thread(target=self._run_video_processing, args=(self.video_files, self.beat_duration_s, run_id), daemon=True)
            thread.start()


    def run_create_script(self):
        """Gathers data, adjusts clips based on target duration, and calls script generator."""
        if self.is_processing:
            messagebox.showwarning("Busy", "Processing in progress. Please wait.")
            return

        selected_style = self.style_var.get()
        if not selected_style or selected_style not in EDITING_STYLES:
            messagebox.showerror("Input Error", "Please select a valid Editing Style.")
            return
        if not self.audio_processed:
            messagebox.showerror("Input Error", "Audio analysis must be completed successfully.")
            return
        if not (self.video_processed or self.video_errors): # Video analysis must have been attempted
            messagebox.showerror("Input Error", "Video analysis must be attempted first.")
            return
        if not self.detector_loaded:
            messagebox.showerror("Error", "MediaPipe detector is not loaded.")
            return
        if not hasattr(self, 'target_duration_var'):
             messagebox.showerror("Internal Error", "Target duration variable is missing.")
             return
        # Ensure clip simulation has run (or re-run it if needed)
        if self.prepared_clips_cache is None:
             print("Warning: prepared_clips_cache is None. Recalculating...")
             self._calculate_and_configure_slider() # This runs the simulation
             if self.prepared_clips_cache is None: # Check again
                 messagebox.showerror("Error", "Clip preparation/simulation failed. Cannot create script.")
                 return

        # Target Duration and Available Duration
        target_duration_s = self.target_duration_var.get()
        available_duration_s = self.simulated_total_duration_s if self.simulated_total_duration_s is not None else 0.0

        # Max duration is limited by both audio and available (simulated) video clips
        max_target_duration_s = min(self.audio_duration_s if self.audio_duration_s else float('inf'),
                                   available_duration_s if available_duration_s > 0 else float('inf'))

        # Final target duration is the slider value, capped by the max usable, and not less than min slider value
        final_target_s = min(target_duration_s, max_target_duration_s)
        final_target_s = max(final_target_s, MIN_SLIDER_S) # Ensure minimum

        # Select Clips based on Target Duration
        final_moments = [] # This will hold the original moment tuples to use

        if not self.prepared_clips_cache or available_duration_s <= 0:
            print("No prepared clips available or total duration is zero. Script will have no video clips.")
            
        # Use all clips if target is close to or exceeds available (allow small float tolerance)
        elif final_target_s >= available_duration_s * 0.999:
            print(f"Using all {len(self.prepared_clips_cache)} prepared clips. Target ({self._format_time(final_target_s)}) >= Available ({self._format_time(available_duration_s)}).")
            final_moments = [clip_info['moment'] for clip_info in self.prepared_clips_cache]
        else:
            # Remove clips until total duration is <= target
            print(f"Target duration ({self._format_time(final_target_s)}) requires shortening from {self._format_time(available_duration_s)}...")
            # Work with a copy of the cached clip info (which includes calculated durations)
            clips_to_shorten = list(self.prepared_clips_cache)
            current_total_s = available_duration_s
            num_removed = 0

            # Sort by calculated duration (ascending) to remove shortest first
            clips_to_shorten.sort(key=lambda x: x['calculated_duration_sec'])

            print(f" Starting shortening. Initial simulated duration: {current_total_s:.2f}s. Target: {final_target_s:.2f}s")
            while current_total_s > final_target_s and clips_to_shorten:
                # Remove the shortest clip (based on its pre-calculated duration)
                removed_clip_info = clips_to_shorten.pop(0)
                removed_duration = removed_clip_info['calculated_duration_sec'] # Use stored calculated duration
                current_total_s -= removed_duration
                num_removed += 1
                # Safety break
                if current_total_s < -0.01: # Allow tiny negative due to float math
                    print(f" Warning: Shortening resulted in negative duration ({current_total_s:.2f}s). Stopping removal.")
                    break

            print(f" Removed {num_removed} clips (shortest first). New simulated duration: {current_total_s:.2f}s.")
            # The remaining clips' original moments are used for the script
            final_moments = [clip_info['moment'] for clip_info in clips_to_shorten]


        # Separate Final Moments for Script Generator
        final_people_moments = [m for m in final_moments if m[2] == "People"]
        final_other_moments = [m for m in final_moments if m[2] != "People"]
        print(f"Passing {len(final_people_moments)} People and {len(final_other_moments)} Other moments ({len(final_moments)} total) to script generator.")

        # Call Script Generator
        try:
            create_script(
                estimated_tempo=self.bpm,
                frame_duration=self.beat_duration_s,
                merged_moments=final_people_moments,
                scene_moments=final_other_moments,
                video_files=self.video_files,
                audio_file_path=self.audio_file_path,
                audio_start_offset=self.audio_offset_s,
                selected_style=selected_style,
                
                audio_processed=self.audio_processed,
                video_processed=self.video_processed or self.video_errors
            )
        except Exception as e:
            tb_str = traceback.format_exc()
            messagebox.showerror("Script Generation Error", f"Failed to create script:\n{e}\n\nDetails:\n{tb_str}")
            print(f"Script Generation Error:\n{tb_str}")


    def save_to_csv(self):
        """Saves detailed analysis results (including simulated durations) to a CSV file."""

        if not self.audio_processed:
            messagebox.showwarning("Save CSV", "Audio analysis must be completed first.")
            return
        if not (self.video_processed or self.video_errors):
            messagebox.showwarning("Save CSV", "Video analysis must be attempted first.")
            return
        if self.is_processing:
            messagebox.showwarning("Save CSV", "Please wait for analysis to complete.")
            return

        if self.simulated_total_duration_s is None:
             messagebox.showwarning("Save CSV", "Clip durations not calculated (select style?). Cannot save full summary.")
             # Optionally, could save partial data here, but for now require simulation
             return


        default_filename = f"analysis_summary_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = filedialog.asksaveasfilename(
            title="Save Analysis Summary CSV",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile=default_filename
        )
        if not file_path:
            print("CSV save cancelled.")
            return

        print(f"Saving analysis summary to: {file_path}")
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                header = [
                    "DataType", "SourceFile", "Label",
                    "StartTimeSec", "EndTimeSec", "DurationSec",
                    "EstBPM", "BeatDurationSec", "AudioOffsetSec", "TotalAudioDurationSec",
                    "SelectedStyle", "AudioAnalysisTimeSec", "VideoAnalysisTimeSec",
                    "TotalProcessingTimeSec", "TotalClipsFound", "SimulatedTotalClipsDurationSec",
                    "VideoErrors"
                ]
                writer.writerow(header)

                # Summary Data
                total_time_s = None
                if self.audio_analysis_s is not None and self.video_analysis_s is not None:
                    total_time_s = self.audio_analysis_s + self.video_analysis_s

                total_clips_found = sum(self.moment_counts.values()) if self.moment_counts else 0
                simulated_duration_str = f"{self.simulated_total_duration_s:.3f}" if self.simulated_total_duration_s is not None else "N/A"
                video_error_str = "; ".join([f"{fname}: {err}" for fname, err in self.video_errors]) if self.video_errors else ""
                selected_style_str = self.style_var.get() if hasattr(self, 'style_var') and self.style_var.get() in EDITING_STYLES else "N/A"

                # Audio Summary Row
                audio_row = [
                    "AudioSummary",
                    os.path.basename(self.audio_file_path) if self.audio_file_path else "N/A",
                    "", "", "", "", # Placeholders for Moment fields
                    f"{self.bpm:.2f}" if self.bpm else "N/A",
                    f"{self.beat_duration_s:.4f}" if self.beat_duration_s else "N/A",
                    f"{self.audio_offset_s:.3f}",
                    f"{self.audio_duration_s:.3f}" if self.audio_duration_s is not None else "N/A",
                    selected_style_str,
                    f"{self.audio_analysis_s:.2f}" if self.audio_analysis_s else "N/A",
                    f"{self.video_analysis_s:.2f}" if self.video_analysis_s else "N/A",
                    f"{total_time_s:.2f}" if total_time_s is not None else "N/A",
                    total_clips_found,
                    simulated_duration_str, # Use simulated duration !!
                    video_error_str
                ]
                writer.writerow(audio_row)

                # Video Moment Rows
                all_moments = (self.people_moments or []) + (self.other_scene_moments or [])
                # Sort by filename
                all_moments.sort(key=lambda x: (x[3], x[0]))

                for start, end, label, fname in all_moments:
                    duration = end - start
                    # Moment rows don't repeat the summary data
                    moment_row = [
                        "VideoMoment", fname, label,
                        f"{start:.3f}", f"{end:.3f}", f"{duration:.3f}",
                        "", "", "", "", "", "", "", "", "", "", ""
                    ]
                    writer.writerow(moment_row)

            messagebox.showinfo("Save CSV", f"Analysis summary saved successfully to:\n{file_path}")
        except IOError as e:
            messagebox.showerror("Save CSV Error", f"Could not write file to disk:\n{e}")
            print(f"Save CSV IO Error: {e}")
        except Exception as e:
            tb_str = traceback.format_exc()
            messagebox.showerror("Save CSV Error", f"An unexpected error occurred during CSV saving:\n{e}")
            print(f"Save CSV Unexpected Error:\n{tb_str}")


    def on_close(self):
        """Handles window closing: release detector, destroy window."""
        print("Closing application...")
        # Signal threads to stop processing callbacks by changing ID
        self.is_processing = False
        self.processing_id = uuid.uuid4()
        print("Releasing MediaPipe detector (if loaded)...")
        release_detector() # cleanup function from mediapipe_utils
        print("Destroying Tkinter root window...")
        if self.root:
            try:
                self.root.destroy()
            except tk.TclError as e:
                # This can happen if the window is already gone
                print(f"Error destroying root window (might be already destroyed): {e}")
        print("Application closed.")

    # Background Task Execution

    def _run_audio_analysis(self, file_path, run_id):
        """Worker function for audio analysis (runs in thread)."""
        start_time = time.perf_counter()
        try:

            if run_id != self.processing_id:
                print(f"Audio run {run_id} cancelled before start.")
                return

            self.root.after(0, self.update_ui_status, f"Audio: Loading & Analyzing...")

            tempo, beat_dur, offset, total_audio_dur = get_bpm_and_offset(file_path)

            if run_id != self.processing_id:
                print(f"Audio run {run_id} cancelled after processing.")
                return

            end_time = time.perf_counter()
            self.audio_analysis_s = end_time - start_time # Store duration
            print(f"--- Audio analysis completed in {self.audio_analysis_s:.2f}s ---")

            self.bpm = tempo
            self.beat_duration_s = beat_dur
            self.audio_offset_s = offset
            self.audio_duration_s = total_audio_dur
            self.audio_processed = True

            self.root.after(0, self._on_audio_analysis_complete, run_id)

        except Exception as e:
            if run_id != self.processing_id:
                print(f"Audio run {run_id} cancelled during error handling.")
                return

            end_time = time.perf_counter()
            if 'start_time' in locals(): 
                self.audio_analysis_s = end_time - start_time
                print(f"--- Audio analysis FAILED after {self.audio_analysis_s:.2f}s ---")
            else:
                print(f"--- Audio analysis FAILED (timing error) ---")
                self.audio_analysis_s = None 

            self.audio_processed = False
            self.bpm = None
            self.beat_duration_s = None
            self.audio_offset_s = 0.0
            self.audio_duration_s = None

            tb_str = traceback.format_exc() 
            print(f"Audio Analysis Error: {e}\n{tb_str}")

            self.root.after(0, self._on_audio_analysis_error, e, tb_str, run_id)


    def _run_video_processing(self, file_paths, beat_duration_s, run_id):
        """Worker function for video processing (runs in thread). Handles errors per file."""
        overall_start_time = time.perf_counter()
        # Local lists to accumulate results
        all_people_local = []
        all_other_local = []
        video_errors_local = []
        local_moment_counts = Counter()
        processed_count = 0
        num_files = len(file_paths)

        try:
            for i, path in enumerate(file_paths):
                 # Check for cancellation before processing each file
                if run_id != self.processing_id:
                    print(f"Video run {run_id} cancelled before file {i+1}/{num_files}.")
                    return

                video_start_time = time.perf_counter()
                base_name = os.path.basename(path)
                # Update UI status
                self.root.after(0, self.update_ui_status, f"Video {i+1}/{num_files}: Analyzing {base_name}...")

                try:
                    # Video detection HERE
                    local_people, local_other = detect_video_moments(path, beat_duration_s)

                    video_end_time = time.perf_counter()
                    video_duration = video_end_time - video_start_time
                    print(f"--- Processed '{base_name}' in {video_duration:.2f}s ({len(local_people)} P, {len(local_other)} O clips) ---")

                    # Append results to local lists
                    all_people_local.extend(local_people)
                    all_other_local.extend(local_other)

                    # Counts
                    if local_people: local_moment_counts["People"] += len(local_people)
                    for _, _, label, _ in local_other: local_moment_counts[label] += 1
                    processed_count += 1

                except Exception as video_err:
                     # Check for cancellation
                    if run_id != self.processing_id:
                        print(f"Video run {run_id} cancelled during error handling for {base_name}.")
                        return

                    err_str = str(video_err)
                    tb_str = traceback.format_exc()
                    print(f"--- FAILED processing '{base_name}': {err_str} ---\n{tb_str}")
                    video_errors_local.append((base_name, err_str))


            # Loop finished,
            # Check for cancellation again
            if run_id != self.processing_id:
                print(f"Video run {run_id} cancelled after loop completion.")
                return

            overall_end_time = time.perf_counter()
            self.video_analysis_s = overall_end_time - overall_start_time
            print(f"--- Video processing loop finished in {self.video_analysis_s:.2f}s ---")

            # Update main state variables
            self.people_moments = all_people_local
            self.other_scene_moments = all_other_local
            self.moment_counts = local_moment_counts
            self.video_errors = video_errors_local

            # Set video_processed flag: True if analysis ran, even with errors, as long as some clips were found
            self.video_processed = bool(all_people_local or all_other_local or not video_errors_local)


            # Appropriate UI callback
            if not video_errors_local:
                print("Video processing fully successful.")
                self.root.after(0, self._on_video_processing_complete, run_id)
            else:
                # If finished with errors
                print(f"Video processing finished with {len(video_errors_local)} error(s). Processed {processed_count}/{num_files} files.")
                print(f" Found clips: {bool(all_people_local or all_other_local)}. video_processed flag set to: {self.video_processed}")
                self.root.after(0, self._on_video_processing_partial_success, video_errors_local, run_id)

        except Exception as e: # Catches errors outside the per-file loop
             # Check for cancellation again
            if run_id != self.processing_id:
                print(f"Video run {run_id} cancelled during overall error handling.")
                return

            overall_end_time = time.perf_counter()
            if 'overall_start_time' in locals():
                self.video_analysis_s = overall_end_time - overall_start_time
                print(f"--- Video processing FAILED critically after {self.video_analysis_s:.2f}s ---")
            else:
                print(f"--- Video processing FAILED critically (timing error) ---")
                self.video_analysis_s = None

            # Preserve data collected before critical error
            self.people_moments = all_people_local
            self.other_scene_moments = all_other_local
            self.moment_counts = local_moment_counts
            self.video_errors = video_errors_local
            # Add critical error
            self.video_errors.append( ("Overall Processing", str(e)) )
            # Mark as not successfully processed overall
            self.video_processed = False

            tb_str = traceback.format_exc()
            print(f"Video Processing Critical Error: {e}\n{tb_str}")

            # critical error callback
            self.root.after(0, self._on_video_processing_error, e, tb_str, run_id)


    # Callbacks from Threads
    def _on_audio_analysis_complete(self, run_id):
        """UI update after successful audio analysis."""
        if run_id != self.processing_id: return # Ignore if cancelled
        if not self.root.winfo_exists(): return # Ignore if no root exists

        print("UI: Audio analysis complete callback.")
        self.is_processing = False
        self.stop_progress()
        self._update_summary_display()
        self._calculate_and_configure_slider() # Update slider based on new audio data
        # Update status message depending on whether video is next
        if not self.video_processed and not self.video_errors:
             status_msg = "Audio analysis complete."
             if self.detector_loaded: status_msg += " Please analyze video(s)."
             else: status_msg += " Detector ERROR - Cannot analyze video."
             self.update_ui_status(status_msg)
        else:
             # If video was already done/attempted, summary display is sufficient
             pass
        self.check_button_states()

    def _on_audio_analysis_error(self, error, traceback_str, run_id):
        """UI update after failed audio analysis."""
        if run_id != self.processing_id: return # Ignore if cancelled
        if not self.root.winfo_exists(): return # Ignore if no root exists

        print("UI: Audio analysis error callback.")
        self.is_processing = False
        # State variables should have been reset in the worker thread's except block
        self.stop_progress()
        # Show error message box
        messagebox.showerror("Audio Error", f"Audio analysis failed:\n{error}\n\nDetails logged to console.")
        # Update UI status text
        self.update_ui_status(f"Error during audio analysis: {error}", error=True)
        self._calculate_and_configure_slider() # Update slider (will be disabled)
        self.check_button_states()

    def _on_video_processing_complete(self, run_id):
        """UI update after successful video processing (all files OK)."""
        if run_id != self.processing_id: return # Ignore if cancelled
        if not self.root.winfo_exists(): return # Ignore if no root exists

        print("UI: Video processing complete (success) callback.")
        self.is_processing = False
        self.stop_progress()
        # Recalculate total duration based on found clips and selected style, configure slider
        self._calculate_and_configure_slider()
        self._update_summary_display() # Show final results
        self.check_button_states()

    def _on_video_processing_partial_success(self, errors, run_id):
        """UI update after video processing finishes with some file errors."""
        if run_id != self.processing_id: return # Ignore if cancelled
        if not self.root.winfo_exists(): return # Ignore if no root exists

        print(f"UI: Video processing complete (partial success/errors: {len(errors)}) callback.")
        self.is_processing = False
        self.stop_progress()
        # Recalculate based on successfully processed clips and configure slider
        self._calculate_and_configure_slider()
        # Update summary, explicitly passing errors to display them
        self._update_summary_display(processing_errors=errors)
        self.check_button_states()

    def _on_video_processing_error(self, error, traceback_str, run_id):
        """UI update after a critical video processing failure."""
        if run_id != self.processing_id: return # Ignore if cancelled
        if not self.root.winfo_exists(): return # Ignore if no root exists

        print("UI: Video processing critical error callback.")
        self.is_processing = False
        # State variables (video_processed=False) should be set in worker thread
        self.stop_progress()
        # Show error message box
        messagebox.showerror("Video Processing Error", f"Video processing failed critically:\n{error}\n\nDetails logged to console.")

        # Prepare detailed error message for UI status
        error_summary_msg = f"Critical error during video processing: {error}\n"
        # Include info about any file-specific errors that occurred before the critical one
        num_file_errors = len([e for e in self.video_errors if e[0] != "Overall Processing"])
        if num_file_errors > 0:
            error_summary_msg += f"Also encountered {num_file_errors} error(s) in specific files (see log).\n"

        self.update_ui_status(error_summary_msg, error=True)
        self._calculate_and_configure_slider() # Update slider
        self.check_button_states()


# Main Execution
if __name__ == "__main__":
    root = tk.Tk()
    app = VideoAnalysisApp(root)
    root.mainloop()
