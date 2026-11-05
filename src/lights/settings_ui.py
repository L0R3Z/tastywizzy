"""Settings window. Tk lives in its own thread; other threads only call open() and stop()."""
import logging
import threading
from tkinter import colorchooser

import customtkinter as ctk

from . import config, hotkey
from .settings_schema import ADVANCED, COLOR_PRESETS, SECTIONS, format_value, get_value, snap, with_value

log = logging.getLogger(__name__)

SAVE_DELAY_MS = 40  # groups the many events of a slider drag
POLL_MS = 150
BG, CARD = "#14161a", "#1f2228"
TEXT, MUTED = "#f1f2f4", "#979ca6"
ACCENT, ACCENT_HOVER = "#f0a04b", "#f5b56f"
TRACK = "#3a3e47"
ERROR = "#ff7b72"


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(int(c) for c in rgb)


class SettingsWindow:
    def __init__(self, config_path, pause, get_rgb):
        self.config_path = config_path
        self.pause = pause
        self.get_rgb = get_rgb
        self._open = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    def open(self):
        """Shows the window (from any thread)."""
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()
        self._open.set()

    def stop(self):
        self._stop.set()

    def _run(self):
        try:
            _Window(self).mainloop()
        except Exception:
            log.exception("Settings window error")
        with self._lock:
            self._thread = None


class _Window(ctk.CTk):
    def __init__(self, owner):
        ctk.set_appearance_mode("dark")
        super().__init__(fg_color=BG)
        self.owner = owner
        self.title("TastyWizzy settings")
        self.geometry("560x780")
        self.minsize(460, 420)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        self.cfg = config.load(owner.config_path)
        self.pending = {}
        self.save_job = None
        self.rows = []  # (row frame, field, grid options)
        self.updaters = []  # refresh each control from self.cfg, when the window is reopened
        self._shown_rgb = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self.body = ctk.CTkScrollableFrame(self, fg_color=BG, scrollbar_button_color=TRACK)
        self.body.grid(row=1, column=0, sticky="nsew", padx=(10, 4), pady=(0, 10))
        self.body.grid_columnconfigure(0, weight=1)
        row = 0
        for title, fields in SECTIONS:
            self._card(self.body, title, fields).grid(row=row, column=0, sticky="ew", padx=6, pady=6)
            row += 1
        self.adv_button = ctk.CTkButton(self.body, text="Show advanced settings", command=self._toggle_advanced,
                                        fg_color="transparent", hover_color=CARD, text_color=MUTED)
        self.adv_button.grid(row=row, column=0, pady=(6, 8))
        self.advanced = ctk.CTkFrame(self.body, fg_color="transparent")
        self.advanced.grid_columnconfigure(0, weight=1)
        for i, (title, fields) in enumerate(ADVANCED):
            self._card(self.advanced, title, fields).grid(row=i, column=0, sticky="ew", padx=6, pady=6)
        self._bulbs_card(self.advanced).grid(row=len(ADVANCED), column=0, sticky="ew", padx=6, pady=6)
        self._refresh_visibility()
        self.withdraw()
        self.after(POLL_MS, self._poll)

    # --- layout ---

    def _build_header(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        head.grid_columnconfigure(1, weight=1)
        self.dot = ctk.CTkFrame(head, width=38, height=38, corner_radius=19, fg_color=ACCENT)
        self.dot.grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ctk.CTkLabel(head, text="TastyWizzy", font=ctk.CTkFont(size=20, weight="bold"), text_color=TEXT,
                     height=24, anchor="w").grid(row=0, column=1, sticky="w")
        self.status = ctk.CTkLabel(head, text="Changes apply instantly", text_color=MUTED, height=18, anchor="w",
                                   font=ctk.CTkFont(size=12))
        self.status.grid(row=1, column=1, sticky="w")
        self.pause_button = ctk.CTkButton(head, width=92, height=34, text="Pause", text_color=TEXT, fg_color=TRACK,
                                          hover_color="#4a4f5a", command=self.owner.pause.toggle_manual)
        self.pause_button.grid(row=0, column=2, rowspan=2)

    def _card(self, parent, title, fields):
        card = self._empty_card(parent, title)
        for i, field in enumerate(fields):
            frame = ctk.CTkFrame(card, fg_color="transparent")
            frame.grid_columnconfigure(0, weight=1)
            options = {"row": i + 1, "column": 0, "sticky": "ew", "padx": 16, "pady": (0, 12)}
            frame.grid(**options)
            getattr(self, "_" + field.kind)(frame, field)
            self.rows.append((frame, field, options))
        return card

    def _empty_card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=14, weight="bold"), text_color=ACCENT,
                     anchor="w").grid(row=0, column=0, sticky="w", padx=16, pady=(10, 6))
        return card

    def _bulbs_card(self, parent):
        card = self._empty_card(parent, "Bulbs")
        for i, (name, entry) in enumerate(self.cfg["bulbs"].items()):
            ip = entry["ip"] if isinstance(entry, dict) else entry
            frame = ctk.CTkFrame(card, fg_color="transparent")
            frame.grid_columnconfigure(0, weight=1)
            frame.grid(row=i + 1, column=0, sticky="ew", padx=16, pady=(0, 10))
            ctk.CTkLabel(frame, text=name.capitalize(), text_color=TEXT, height=20, anchor="w").grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(frame, text=ip, text_color=MUTED, height=20).grid(row=0, column=1)
        return card

    def _labels(self, frame, field):
        ctk.CTkLabel(frame, text=field.label, text_color=TEXT, height=20, anchor="w",
                     font=ctk.CTkFont(size=13)).grid(row=0, column=0, sticky="w")
        if field.help:
            ctk.CTkLabel(frame, text=field.help, text_color=MUTED, height=16, anchor="w",
                         font=ctk.CTkFont(size=11)).grid(row=1, column=0, sticky="w")

    # --- controls ---

    def _slider(self, frame, field):
        self._labels(frame, field)
        value_label = ctk.CTkLabel(frame, text="", text_color=TEXT, height=20, font=ctk.CTkFont(size=13, weight="bold"))
        value_label.grid(row=0, column=1, sticky="e")

        def moved(position):
            value = snap(position, field)
            value_label.configure(text=format_value(value, field))
            self._change(field, value)

        slider = ctk.CTkSlider(frame, from_=field.lo, to=field.hi, number_of_steps=round((field.hi - field.lo) / field.step),
                               command=moved, progress_color=ACCENT, button_color=ACCENT,
                               button_hover_color=ACCENT_HOVER, fg_color=TRACK, height=18)
        slider.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        def update():
            value = get_value(self.cfg, field.path)
            slider.set(value)
            value_label.configure(text=format_value(value, field))
        update()
        self.updaters.append(update)

    def _switch(self, frame, field):
        self._labels(frame, field)
        switch = ctk.CTkSwitch(frame, text="", width=46, progress_color=ACCENT, fg_color=TRACK,
                               command=lambda: self._change(field, bool(switch.get())))
        switch.grid(row=0, column=1, rowspan=2, sticky="e")

        def update():
            (switch.select if get_value(self.cfg, field.path) else switch.deselect)()
        update()
        self.updaters.append(update)

    def _choice(self, frame, field):
        self._labels(frame, field)
        to_value = {label: value for value, label in field.options}
        to_label = {value: label for value, label in field.options}
        button = ctk.CTkSegmentedButton(frame, values=list(to_value), selected_color=ACCENT, text_color=TEXT,
                                        selected_hover_color=ACCENT_HOVER, unselected_color=TRACK,
                                        unselected_hover_color="#4a4f5a", fg_color=TRACK,
                                        command=lambda label: self._change(field, to_value[label]))
        button.grid(row=0, column=1, rowspan=2, sticky="e")

        def update():
            button.set(to_label.get(get_value(self.cfg, field.path), ""))
        update()
        self.updaters.append(update)

    def _color(self, frame, field):
        self._labels(frame, field)
        chips = ctk.CTkFrame(frame, fg_color="transparent")
        chips.grid(row=0, column=1, rowspan=2, sticky="e")

        def pick(rgb):
            self._change(field, list(rgb))
            update()

        for i, (name, rgb) in enumerate(COLOR_PRESETS):
            ctk.CTkButton(chips, text=name, width=50, height=28, fg_color=TRACK, hover_color="#4a4f5a", text_color=TEXT,
                          command=lambda c=rgb: pick(c)).grid(row=0, column=i, padx=(0, 4))

        def custom():
            chosen = colorchooser.askcolor(color=_hex(get_value(self.cfg, field.path)), parent=self)[0]
            if chosen:
                pick([int(c) for c in chosen])

        swatch = ctk.CTkButton(chips, text="", width=32, height=28, border_width=1, border_color=MUTED, command=custom)
        swatch.grid(row=0, column=len(COLOR_PRESETS), padx=(4, 0))

        def update():
            color = _hex(get_value(self.cfg, field.path))
            swatch.configure(fg_color=color, hover_color=color)
        update()
        self.updaters.append(update)

    def _hotkey(self, frame, field):
        self._labels(frame, field)
        entry = ctk.CTkEntry(frame, width=130, fg_color=TRACK, border_width=0, text_color=TEXT)
        entry.grid(row=0, column=1, rowspan=2, sticky="e")

        def commit(_=None):
            combo = entry.get().strip().lower()
            if combo == get_value(self.cfg, field.path):
                return
            try:
                if combo:
                    hotkey.parse(combo)
            except ValueError:
                self._show(f"Invalid shortcut: {combo}", error=True)
                return
            self._change(field, combo)

        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)

        def update():
            entry.delete(0, "end")
            entry.insert(0, get_value(self.cfg, field.path))
        update()
        self.updaters.append(update)

    # --- behaviour ---

    def _change(self, field, value):
        candidate = with_value(self.cfg, field.path, value)
        try:
            config.validate(candidate)
        except ValueError as e:
            self._show(str(e), error=True)
            return
        self.cfg = candidate
        key = field.path[0]
        self.pending[key] = candidate[key]
        self._refresh_visibility()
        if self.save_job:
            self.after_cancel(self.save_job)
        self.save_job = self.after(SAVE_DELAY_MS, self._save)

    def _save(self):
        self.save_job = None
        pending, self.pending = self.pending, {}
        try:
            config.save_values(self.owner.config_path, pending)
            self._show("Changes apply instantly")
        except (OSError, ValueError) as e:
            log.warning("Settings not saved: %s", e)
            self._show(f"Not saved: {e}", error=True)

    def _show(self, text, error=False):
        self.status.configure(text=text, text_color=ERROR if error else MUTED)

    def _refresh_visibility(self):
        for frame, field, options in self.rows:
            if field.visible is None or field.visible(self.cfg):
                frame.grid(**options)
            else:
                frame.grid_remove()

    def _toggle_advanced(self):
        if self.advanced.winfo_ismapped():
            self.advanced.grid_remove()
            self.adv_button.configure(text="Show advanced settings")
        else:
            self.advanced.grid(row=len(SECTIONS) + 1, column=0, sticky="ew")
            self.adv_button.configure(text="Hide advanced settings")

    def _reload(self):
        try:
            self.cfg = config.load(self.owner.config_path)
        except ValueError as e:
            self._show(str(e), error=True)
            return
        for update in self.updaters:
            update()
        self._refresh_visibility()

    def _poll(self):
        owner = self.owner
        if owner._stop.is_set():
            self.quit()
            return
        if owner._open.is_set():
            owner._open.clear()
            if self.state() == "withdrawn":
                self._reload()
            self.deiconify()
            self.lift()
            self.focus_force()
        paused = owner.pause.paused
        rgb = (110, 110, 110) if paused else owner.get_rgb()
        if rgb != self._shown_rgb:
            self._shown_rgb = rgb
            self.dot.configure(fg_color=_hex(rgb))
        self.pause_button.configure(text="Resume" if paused else "Pause")
        self.after(POLL_MS, self._poll)
