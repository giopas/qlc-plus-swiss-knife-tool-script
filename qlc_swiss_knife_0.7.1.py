#!/usr/bin/env python3
"""
================================================================================
  QLC+ SWISS KNIFE — Unified Live Console Toolkit (v0.7.1)
================================================================================
  A single, ergonomic interface combining four essential QLC+ 5.x utilities:

    1. SETLIST MANAGER   — Build show cue lists from text setlists, map to
                           QLC+ functions, generate pristine clones, export PDF.
    2. DICTIONARY MANAGER — Create & edit ID→description mapping files used
                           to annotate your QLC+ function pool.
    3. SETUP CHECKLIST   — Parse fixture patches, 3D positions, groups, and
                           export printable blueprint PDFs & text checklists.
    4. TRIGGER MANAGER   — Audit & edit Virtual Console keyboard/MIDI
                           bindings in a spreadsheet-style view.
    5. FIXTURE CONFIGURATOR — Design your stage rig: load any .qxf fixture
                           definitions, place fixtures on a 2-D stage canvas,
                           assign names and DMX patches, then generate a ready-
                           to-use .qxw file cloned from a template workspace.

  Zero external dependencies — pure Python 3 stdlib + tkinter.
  Works on Windows, macOS, and Linux.
================================================================================
"""

import os
import platform
import string
import re
import copy
import sys
import traceback
import zlib
import datetime
import difflib

# ==============================================================================
# CROSS-PLATFORM & macOS HANDLING
# ==============================================================================
if platform.system() == "Darwin":
    os.environ['SYSTEM_VERSION_COMPAT'] = '0'
    os.environ['TK_SILENCE_DEPRECATION'] = '1'

import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ==============================================================================
# QLC+ XML NAMESPACE
# ==============================================================================
QLC_NS_URI = 'http://www.qlcplus.org/Workspace'
NS = {'q': QLC_NS_URI}
ET.register_namespace('', QLC_NS_URI)

# ==============================================================================
# SHARED CONSTANTS & HELPERS
# ==============================================================================
_NEWLINE_SENTINEL = "\\n"

# Extract version dynamically from the module docstring so you only
# need to update the number in ONE place (the top comment block).
_ver_match = re.search(r'\(v([\d.]+)\)', __doc__ or "")
VERSION = _ver_match.group(1) if _ver_match else "0.0"
APP_TITLE = f"QLC+ Swiss Knife v{VERSION}"


def format_time_for_ui(t_str):
    """Converts QLC+ internal 'Infinite' representation to readable UI string."""
    if t_str == "4294967294" or t_str == "-2":
        return "Inf"
    return t_str


def parse_time_for_xml(t_str):
    """Converts user input back into QLC+ integer format."""
    t_str = t_str.strip()
    if t_str.lower() in ["inf", "infinite", ""]:
        return "4294967294"
    cleaned = re.sub(r'[^0-9]', '', t_str)
    if not cleaned:
        return "4294967294"
    return str(int(cleaned))


def hex_to_01(h):
    """Converts hex color codes to PDF-friendly 0.0-1.0 RGB tuples."""
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


# ==============================================================================
# UNIFIED THEME ENGINE
# ==============================================================================
THEMES = {
    "dark": {
        "bg": "#1e1e2e", "fg": "#cdd6f4",
        "tree_bg": "#181825", "tree_fg": "#cdd6f4",
        "select_bg": "#89b4fa", "select_fg": "#1e1e2e",
        "missing": "#f38ba8", "btn_bg": "#313244",
        "lbl_gray": "#6c7086", "lbl_green": "#a6e3a1", "lbl_red": "#f38ba8",
        "accent": "#89b4fa", "accent2": "#f5c2e7",
        "info_bg": "#11111b", "info_fg": "#89dceb",
        "canvas_bg": "#11111b", "stage_lines": "#45475a",
        "grid_line": "#313244", "dim_line": "#cdd6f4",
        "tab_bg": "#313244", "tab_fg": "#cdd6f4",
        "tab_sel_bg": "#89b4fa", "tab_sel_fg": "#1e1e2e",
        "header_bg": "#181825", "border": "#45475a",
        "surface": "#313244", "overlay": "#45475a",
        "yellow": "#f9e2af", "peach": "#fab387",
        "green": "#a6e3a1", "red": "#f38ba8",
        "blue": "#89b4fa", "mauve": "#cba6f7",
    },
    "light": {
        "bg": "#eff1f5", "fg": "#4c4f69",
        "tree_bg": "#ffffff", "tree_fg": "#4c4f69",
        "select_bg": "#1e66f5", "select_fg": "#ffffff",
        "missing": "#d20f39", "btn_bg": "#ccd0da",
        "lbl_gray": "#8c8fa1", "lbl_green": "#40a02b", "lbl_red": "#d20f39",
        "accent": "#1e66f5", "accent2": "#ea76cb",
        "info_bg": "#e6e9ef", "info_fg": "#1e66f5",
        "canvas_bg": "#ffffff", "stage_lines": "#bcc0cc",
        "grid_line": "#e6e9ef", "dim_line": "#4c4f69",
        "tab_bg": "#ccd0da", "tab_fg": "#4c4f69",
        "tab_sel_bg": "#1e66f5", "tab_sel_fg": "#ffffff",
        "header_bg": "#dce0e8", "border": "#bcc0cc",
        "surface": "#ccd0da", "overlay": "#bcc0cc",
        "yellow": "#df8e1d", "peach": "#fe640b",
        "green": "#40a02b", "red": "#d20f39",
        "blue": "#1e66f5", "mauve": "#8839ef",
    }
}


class ToolTip:
    """Minimal hover-tooltip for any tkinter widget."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event=None):
        if self.tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(tw, text=self.text, justify="left",
                       background="#f9e2af", foreground="#1e1e2e",
                       relief="solid", borderwidth=1,
                       font=("Helvetica", 9), padx=8, pady=4,
                       wraplength=320)
        lbl.pack()

    def _hide(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


# ██████████████████████████████████████████████████████████████████████████████
#  MAIN APPLICATION
# ██████████████████████████████████████████████████████████████████████████████

class QLCSwissKnife:
    """The unified application shell: shared workspace, tabs, theme engine."""

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1600x900")
        self.root.minsize(1200, 700)

        # ── Shared workspace state ────────────────────────────────────────────
        self.xml_tree = None
        self.qxw_root = None
        self.current_qxw_file = ""

        # Shared maps rebuilt on QXW load
        self.fixture_map = {}        # fid -> {name, universe, address, groups, pos}
        self.group_map = {}          # group_id -> group_name
        self.fixture_groups_map = {} # fid -> [group_names]
        self.func_by_name = {}       # name -> fid
        self.func_by_id = {}         # fid -> name
        self.func_detailed = {}      # fid -> {name, type, contains}
        self.vc_buttons = {}         # fid -> {captions, frames}
        self.available_frames = set()
        self.chasers = {}            # chaser_name -> fid
        self.highest_func_id = 0
        self.shared_descriptions = {} # fid -> description string (shared across tabs)

        # ── Theme ─────────────────────────────────────────────────────────────
        self.current_theme = "dark"
        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')

        # ── Build UI ──────────────────────────────────────────────────────────
        self._build_shell()
        self.apply_theme()
        # Apply tab-specific theming at startup (not just on toggle)
        self.setlist_mgr.on_theme_changed()
        self.dict_mgr.on_theme_changed()
        self.setup_mgr.on_theme_changed()
        self.trigger_mgr.on_theme_changed()
        self.fixture_cfg.on_theme_changed()

    # ══════════════════════════════════════════════════════════════════════════
    # SHELL UI
    # ══════════════════════════════════════════════════════════════════════════
    def _build_shell(self):
        """Top bar  +  Notebook tabs  +  Status bar."""

        # ── Top Header Bar ────────────────────────────────────────────────────
        self.header = tk.Frame(self.root, padx=12, pady=8)
        self.header.pack(fill=tk.X)

        # Logo / Title
        self.lbl_title = tk.Label(
            self.header,
            text="⚡ QLC+ SWISS KNIFE",
            font=("Helvetica", 14, "bold"),
        )
        self.lbl_title.pack(side=tk.LEFT)

        self.lbl_version = tk.Label(
            self.header,
            text=f"  v{VERSION}  —  Unified Toolkit for QLC+ 5.x",
            font=("Helvetica", 9, "italic"),
        )
        self.lbl_version.pack(side=tk.LEFT, padx=(4, 20))

        # QXW Load button
        self.btn_load_qxw = ttk.Button(
            self.header, text="📂 Load QXW Workspace",
            command=self.load_qxw_dialog, style="Accent.TButton"
        )
        self.btn_load_qxw.pack(side=tk.LEFT, padx=(0, 8))

        self.lbl_qxw = tk.Label(
            self.header, text="No workspace loaded",
            font=("Helvetica", 10, "bold"),
        )
        self.lbl_qxw.pack(side=tk.LEFT, padx=(0, 20))

        # Refresh button
        self.btn_refresh = ttk.Button(
            self.header, text="🔄 Reload",
            command=self.refresh_qxw, style="Normal.TButton"
        )
        self.btn_refresh.pack(side=tk.LEFT)

        # Theme toggle (right side)
        self.btn_toggle = ttk.Button(
            self.header, text="🌗 Theme",
            command=self.toggle_theme, style="Normal.TButton"
        )
        self.btn_toggle.pack(side=tk.RIGHT)

        # ── Separator ─────────────────────────────────────────────────────────
        self.sep = tk.Frame(self.root, height=2)
        self.sep.pack(fill=tk.X)

        # ── Notebook (Tabs) ──────────────────────────────────────────────────
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 0))

        # Tab 1 — Setlist Manager
        self.tab_setlist = tk.Frame(self.notebook)
        self.notebook.add(self.tab_setlist, text="  🎵  Setlist Manager  ")
        self.setlist_mgr = SetlistManagerTab(self.tab_setlist, self)

        # Tab 2 — Dictionary Manager
        self.tab_dict = tk.Frame(self.notebook)
        self.notebook.add(self.tab_dict, text="  📖  Dictionary  ")
        self.dict_mgr = DictionaryManagerTab(self.tab_dict, self)

        # Tab 3 — Setup Checklist
        self.tab_setup = tk.Frame(self.notebook)
        self.notebook.add(self.tab_setup, text="  📋  Setup Checklist  ")
        self.setup_mgr = SetupChecklistTab(self.tab_setup, self)

        # Tab 4 — Trigger Manager
        self.tab_trigger = tk.Frame(self.notebook)
        self.notebook.add(self.tab_trigger, text="  🎛  Triggers  ")
        self.trigger_mgr = TriggerManagerTab(self.tab_trigger, self)

        # Tab 5 — Fixture Configurator
        self.tab_fixture_cfg = tk.Frame(self.notebook)
        self.notebook.add(self.tab_fixture_cfg, text="  🔧  Fixture Configurator  ")
        self.fixture_cfg = FixtureConfiguratorTab(self.tab_fixture_cfg, self)

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # ── Status Bar ────────────────────────────────────────────────────────
        self.status_bar = tk.Frame(self.root, padx=12, pady=6)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_status = tk.Label(
            self.status_bar,
            text="Ready — Load a .qxw workspace to begin.",
            font=("Helvetica", 9),
            anchor="w",
        )
        self.lbl_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lbl_counts = tk.Label(
            self.status_bar,
            text="",
            font=("Helvetica", 9),
            anchor="e",
        )
        self.lbl_counts.pack(side=tk.RIGHT)

    def _on_tab_changed(self, event):
        """Notify tabs that they've been selected (e.g. for canvas redraws)."""
        idx = self.notebook.index(self.notebook.select())
        if idx == 2:  # Setup Checklist tab
            self.setup_mgr.on_tab_activated()

    # ══════════════════════════════════════════════════════════════════════════
    # THEME ENGINE
    # ══════════════════════════════════════════════════════════════════════════
    def toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.apply_theme()
        # Notify children
        self.setlist_mgr.on_theme_changed()
        self.dict_mgr.on_theme_changed()
        self.setup_mgr.on_theme_changed()
        self.trigger_mgr.on_theme_changed()
        self.fixture_cfg.on_theme_changed()

    def apply_theme(self):
        t = THEMES[self.current_theme]
        self.root.configure(bg=t["bg"])

        # ── ttk styles ────────────────────────────────────────────────────────
        self.style.configure(".", background=t["bg"], foreground=t["fg"])

        self.style.configure("Treeview",
                             background=t["tree_bg"],
                             fieldbackground=t["tree_bg"],
                             foreground=t["tree_fg"],
                             rowheight=26, borderwidth=0)
        self.style.configure("Treeview.Heading",
                             background=t["surface"],
                             foreground=t["fg"],
                             font=("Helvetica", 9, "bold"))
        self.style.map("Treeview",
                        background=[("selected", t["select_bg"])],
                        foreground=[("selected", t["select_fg"])])

        self.style.configure("TButton", font=("Helvetica", 10), padding=4)
        self.style.configure("Normal.TButton",
                             background=t["btn_bg"], foreground=t["fg"])
        self.style.configure("Accent.TButton",
                             background=t["accent"], foreground=t["bg"],
                             font=("Helvetica", 10, "bold"))
        self.style.configure("Assign.TButton",
                             background=t["blue"], foreground="#ffffff",
                             font=("Helvetica", 10, "bold"))
        self.style.configure("Danger.TButton",
                             background=t["btn_bg"], foreground=t["red"])
        self.style.configure("Save.TButton",
                             background=t["green"], foreground="#1e1e2e",
                             font=("Helvetica", 11, "bold"))
        self.style.configure("Export.TButton",
                             background=t["mauve"], foreground="#ffffff",
                             font=("Helvetica", 11, "bold"))

        for s in ["Normal.TButton", "Accent.TButton", "Assign.TButton",
                   "Danger.TButton", "Save.TButton", "Export.TButton"]:
            self.style.map(s,
                           background=[("active", t["accent"])],
                           foreground=[("active", t["bg"])])

        self.style.configure("TEntry",
                             fieldbackground=t["tree_bg"],
                             foreground=t["tree_fg"],
                             insertcolor=t["tree_fg"], borderwidth=1)

        self.style.configure("TCombobox",
                             fieldbackground=t["tree_bg"],
                             background=t["btn_bg"],
                             foreground=t["tree_fg"],
                             arrowcolor=t["fg"],
                             selectbackground=t["select_bg"],
                             selectforeground=t["select_fg"])
        self.style.map("TCombobox",
                        fieldbackground=[("readonly", t["tree_bg"]),
                                         ("disabled", t["surface"])],
                        foreground=[("readonly", t["tree_fg"]),
                                    ("disabled", t["lbl_gray"])],
                        selectbackground=[("readonly", t["select_bg"])],
                        selectforeground=[("readonly", t["select_fg"])])

        # Fix the dropdown list (Listbox) colors — these are tk widgets,
        # not ttk, so they need option_add on the root.
        self.root.option_add('*TCombobox*Listbox.background', t["tree_bg"])
        self.root.option_add('*TCombobox*Listbox.foreground', t["tree_fg"])
        self.root.option_add('*TCombobox*Listbox.selectBackground', t["select_bg"])
        self.root.option_add('*TCombobox*Listbox.selectForeground', t["select_fg"])

        self.style.configure("TCheckbutton",
                             background=t["bg"], foreground=t["fg"])
        self.style.map("TCheckbutton",
                        background=[('active', t["bg"])])

        self.style.configure("TNotebook",
                             background=t["bg"], borderwidth=0, padding=0)
        self.style.configure("TNotebook.Tab",
                             background=t["tab_bg"],
                             foreground=t["tab_fg"],
                             font=("Helvetica", 10, "bold"),
                             padding=[14, 6])
        self.style.map("TNotebook.Tab",
                        background=[("selected", t["tab_sel_bg"])],
                        foreground=[("selected", t["tab_sel_fg"])],
                        expand=[("selected", [0, 0, 0, 2])])

        # Header + status bar
        self.header.configure(bg=t["header_bg"])
        self.lbl_title.configure(bg=t["header_bg"], fg=t["accent"])
        self.lbl_version.configure(bg=t["header_bg"], fg=t["lbl_gray"])
        self.sep.configure(bg=t["border"])
        self.status_bar.configure(bg=t["header_bg"])
        self.lbl_status.configure(bg=t["header_bg"], fg=t["lbl_gray"])
        self.lbl_counts.configure(bg=t["header_bg"], fg=t["accent"])

        if self.current_qxw_file:
            self.lbl_qxw.configure(bg=t["header_bg"], fg=t["lbl_green"])
        else:
            self.lbl_qxw.configure(bg=t["header_bg"], fg=t["lbl_red"])

        # Recursive for plain tk widgets
        self._apply_theme_recursive(self.root, t)

    def _apply_theme_recursive(self, widget, t):
        wtype = widget.winfo_class()
        try:
            if wtype in ("Frame", "Tk", "Toplevel"):
                widget.configure(bg=t["bg"])
            elif wtype == "Label":
                # Don't clobber labels that have special colors
                if widget not in (self.lbl_title, self.lbl_version, self.lbl_qxw,
                                  self.lbl_status, self.lbl_counts):
                    widget.configure(bg=t["bg"], fg=t["fg"])
            elif wtype in ("Labelframe", "LabelFrame"):
                widget.configure(bg=t["bg"], fg=t["fg"])
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._apply_theme_recursive(child, t)

    # ══════════════════════════════════════════════════════════════════════════
    # SHARED QXW LOADING
    # ══════════════════════════════════════════════════════════════════════════
    def load_qxw_dialog(self):
        filename = filedialog.askopenfilename(
            title="Select QLC+ Workspace",
            filetypes=[("QLC+ Workspace", "*.qxw"), ("All Files", "*.*")]
        )
        if filename:
            self.load_qxw(filename)

    def refresh_qxw(self):
        if self.current_qxw_file and os.path.exists(self.current_qxw_file):
            self.load_qxw(self.current_qxw_file)
            self.set_status("Workspace reloaded from disk.")
        else:
            messagebox.showwarning("Notice", "No workspace file is currently loaded.")

    def load_qxw(self, filename):
        """Loads a QXW, parses shared maps, then notifies all tabs."""
        try:
            self.xml_tree = ET.parse(filename)
            self.qxw_root = self.xml_tree.getroot()
            self.current_qxw_file = filename

            t = THEMES[self.current_theme]
            self.lbl_qxw.config(text=os.path.basename(filename), fg=t["lbl_green"])

            self._parse_shared_data()

            # Notify all tabs
            self.setlist_mgr.on_qxw_loaded()
            self.dict_mgr.on_qxw_loaded()
            self.setup_mgr.on_qxw_loaded()
            self.trigger_mgr.on_qxw_loaded()
            self.fixture_cfg.on_qxw_loaded()

            fc = len(self.func_detailed)
            fix_count = len(self.fixture_map)
            vc_count = len(self.vc_buttons)
            self.lbl_counts.config(
                text=f"Functions: {fc}  |  Fixtures: {fix_count}  |  VC Buttons: {vc_count}"
            )
            self.set_status(f"Loaded: {os.path.basename(filename)}")

        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            messagebox.showerror("Error", f"Failed to load QXW:\n{e}")

    def _parse_shared_data(self):
        """Builds all shared maps from the loaded XML tree."""
        self.fixture_map.clear()
        self.group_map.clear()
        self.fixture_groups_map.clear()
        self.func_by_name.clear()
        self.func_by_id.clear()
        self.func_detailed.clear()
        self.vc_buttons.clear()
        self.available_frames.clear()
        self.chasers.clear()
        self.highest_func_id = 0

        if not self.qxw_root:
            return

        # ── Fixture Groups ────────────────────────────────────────────────────
        for group in self.qxw_root.findall('q:Engine/q:FixtureGroup', NS):
            g_id = group.get('ID')
            g_name_node = group.find('q:Name', NS)
            g_name = (g_name_node.text or "").strip() if g_name_node is not None else f"Group {g_id}"
            if not g_name:
                g_name = f"Group {g_id}"
            if g_id:
                self.group_map[g_id] = g_name
            for head in group.findall('q:Head', NS):
                f_id = head.get('Fixture')
                if f_id:
                    if f_id not in self.fixture_groups_map:
                        self.fixture_groups_map[f_id] = []
                    if g_name not in self.fixture_groups_map[f_id]:
                        self.fixture_groups_map[f_id].append(g_name)

        # ── 3D Monitor positions ──────────────────────────────────────────────
        monitor_pos = {}
        for fx_item in self.qxw_root.findall('.//q:Monitor/q:FxItem', NS):
            f_id = fx_item.get('ID')
            monitor_pos[f_id] = (
                float(fx_item.get('XPos', '0')),
                float(fx_item.get('YPos', '0')),
                float(fx_item.get('ZPos', '0'))
            )

        # ── Fixtures ──────────────────────────────────────────────────────────
        for fix in self.qxw_root.findall('q:Engine/q:Fixture', NS):
            f_id_node = fix.find('q:ID', NS)
            f_id = fix.get('ID')
            if f_id_node is not None:
                f_id = f_id_node.text or f_id

            f_name = fix.find('q:Name', NS)
            f_name = (f_name.text or "").strip() if f_name is not None else ""
            if not f_name:
                f_name = f"Fixture {f_id}"

            uni_node = fix.find('q:Universe', NS)
            addr_node = fix.find('q:Address', NS)
            universe = int(uni_node.text) if uni_node is not None else 0
            address = int(addr_node.text) if addr_node is not None else 0

            groups = self.fixture_groups_map.get(f_id, [])
            group_str = ", ".join(groups) if groups else "None"

            pos = monitor_pos.get(f_id, (0, 0, 0))
            pos_str = f"X:{pos[0]:.0f} Y:{pos[1]:.0f} Z:{pos[2]:.0f}"

            if f_id:
                self.fixture_map[f_id] = {
                    "name": f_name,
                    "universe": universe + 1,
                    "address": address + 1,
                    "groups": group_str,
                    "pos": pos_str,
                }

        # ── Functions ─────────────────────────────────────────────────────────
        for func in self.qxw_root.findall('q:Engine/q:Function', NS):
            f_name = func.get('Name')
            f_id = func.get('ID')
            f_type = func.get('Type')

            if f_id:
                int_id = int(f_id)
                if int_id > self.highest_func_id:
                    self.highest_func_id = int_id

            if f_name and f_id:
                self.func_by_name[f_name] = f_id
                self.func_by_id[f_id] = f_name

                if f_type == 'Chaser':
                    self.chasers[f_name] = f_id

                contains = []
                for step in func.findall('q:Step', NS):
                    if step.text:
                        contains.append(step.text)

                self.func_detailed[f_id] = {
                    'name': f_name,
                    'type': f_type,
                    'contains': ", ".join(contains),
                }

        # ── Virtual Console buttons ───────────────────────────────────────────
        vc_root = self.qxw_root.find('q:VirtualConsole', NS)
        if vc_root is not None:
            self._parse_vc_node(vc_root, [])

    def _parse_vc_node(self, node, frame_ancestry=None):
        """
        Recursively walk the Virtual Console XML tree.
        frame_ancestry is a list of all Frame/SoloFrame Caption strings
        from the root down to the current node — so every button gets tagged
        with ALL enclosing frame names, not just its direct parent.
        This makes the Frame filter work correctly for nested frames.
        """
        if frame_ancestry is None:
            frame_ancestry = []

        tag_name = node.tag.replace(f"{{{QLC_NS_URI}}}", "")

        if tag_name in ["Frame", "SoloFrame"]:
            caption = node.get('Caption', frame_ancestry[-1] if frame_ancestry else "[No Frame]")
            self.available_frames.add(caption)
            frame_ancestry = frame_ancestry + [caption]   # new list — don't mutate caller's

        if tag_name == "Button":
            caption = node.get('Caption')
            func_node = node.find('q:Function', NS)
            if func_node is not None and caption:
                f_id = func_node.get('ID')
                if f_id and f_id not in ["4294967295", "-1"]:
                    clean_cap = caption.replace('\n', ' ').strip()
                    if f_id not in self.vc_buttons:
                        self.vc_buttons[f_id] = {'captions': set(), 'frames': set()}
                    self.vc_buttons[f_id]['captions'].add(clean_cap)
                    # Tag the button with every ancestor frame so that
                    # filtering by any level in the hierarchy works correctly.
                    for anc in frame_ancestry:
                        self.vc_buttons[f_id]['frames'].add(anc)

        for child in node:
            self._parse_vc_node(child, frame_ancestry)

    def set_status(self, msg):
        self.lbl_status.config(text=msg)


# ██████████████████████████████████████████████████████████████████████████████
#  TAB 1 — SETLIST MANAGER  (multi-slot: one slot per QLC+ CueList)
# ██████████████████████████████████████████████████████████████████████████████

class SetlistSlot:
    """
    One 'slot' = one CueList / Chaser pair.
    Owns its own setlist_data list, TXT file reference, and all the
    per-cuelist UI widgets (left tree, timing bar, chaser picker …).
    The shared function-pool tree lives on the parent SetlistManagerTab.
    """

    def __init__(self, parent_frame, mgr, slot_index, cuelist_caption="",
                 chaser_id="", chaser_name=""):
        self.parent_frame  = parent_frame   # tk.Frame inside the inner notebook tab
        self.mgr           = mgr            # SetlistManagerTab reference
        self.slot_index    = slot_index

        # Data
        self.setlist_data     = []
        self.current_txt_file = ""

        # CueList linkage (set from the showfile on load, editable by user)
        self.cuelist_caption  = cuelist_caption   # VC CueList caption
        self.linked_chaser_id = chaser_id         # Chaser ID this CueList points to

        self._build_ui(chaser_name)

    # ──────────────────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────────────────
    def _build_ui(self, chaser_name):
        app = self.mgr.app

        # ── Top bar ────────────────────────────────────────────────────────────
        top = tk.Frame(self.parent_frame, padx=8, pady=4)
        top.pack(fill=tk.X)

        ttk.Button(top, text="📄 Load Setlist TXT",
                   command=self.load_txt_dialog,
                   style="Normal.TButton").pack(side=tk.LEFT)
        self.lbl_txt = tk.Label(top, text="No setlist", font=("Helvetica", 9, "bold"))
        self.lbl_txt.pack(side=tk.LEFT, padx=(5, 15))

        # Chaser target picker
        tk.Label(top, text="Target Chaser:", font=("Helvetica", 9, "bold")).pack(
            side=tk.LEFT, padx=(12, 4))
        self.chaser_var = tk.StringVar(
            value=chaser_name if chaser_name else "[ Create New Chaser ]")
        self.combo_chaser = ttk.Combobox(top, textvariable=self.chaser_var,
                                         state="readonly", width=36,
                                         font=("Helvetica", 9))
        self.combo_chaser.pack(side=tk.LEFT, padx=(0, 4))
        self.combo_chaser.bind("<<ComboboxSelected>>", self.on_chaser_change)

        ttk.Button(top, text="✎ Rename to CueList",
                   command=self.rename_chaser_to_cuelist,
                   style="Normal.TButton").pack(side=tk.LEFT, padx=(0, 8))

        # CueList caption label (informational)
        if self.cuelist_caption:
            tk.Label(top, text=f"↔ VC CueList: «{self.cuelist_caption}»",
                     font=("Helvetica", 8, "italic")).pack(side=tk.LEFT, padx=8)

        # ── Bottom timing bar — packed FIRST so it gets reserved space ──────────
        bottom = tk.Frame(self.parent_frame, padx=8, pady=6)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)

        timing_f = tk.LabelFrame(bottom, text="Timings (ms)", padx=8, pady=4)
        timing_f.pack(side=tk.LEFT)
        tk.Label(timing_f, text="In:").pack(side=tk.LEFT)
        self.var_in = tk.StringVar(value="1000")
        ttk.Entry(timing_f, textvariable=self.var_in, width=6).pack(side=tk.LEFT, padx=2)
        tk.Label(timing_f, text="Hold:").pack(side=tk.LEFT, padx=(8, 0))
        self.var_hold = tk.StringVar(value="Inf")
        ttk.Entry(timing_f, textvariable=self.var_hold, width=6).pack(side=tk.LEFT, padx=2)
        tk.Label(timing_f, text="Out:").pack(side=tk.LEFT, padx=(8, 0))
        self.var_out = tk.StringVar(value="1000")
        ttk.Entry(timing_f, textvariable=self.var_out, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(timing_f, text="Apply", command=self.update_timings,
                   style="Normal.TButton").pack(side=tk.LEFT, padx=8)
        self.lbl_duration = tk.Label(timing_f, text="Runtime: 00:00:00",
                                     font=("Helvetica", 9, "bold"))
        self.lbl_duration.pack(side=tk.LEFT, padx=16)

        ttk.Button(bottom, text="💾 SAVE THIS SLOT",
                   command=self.save_qxw, style="Save.TButton").pack(
            side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 0), ipady=4)
        ttk.Button(bottom, text="🖨️ PDF",
                   command=self.export_setlist_pdf, style="Export.TButton").pack(
            side=tk.RIGHT, padx=(8, 0), ipady=4)
        ttk.Button(bottom, text="📄 XML TXT",
                   command=self.export_txt, style="Export.TButton").pack(
            side=tk.RIGHT, padx=(8, 0), ipady=4)

        # ── Action toolbar — packed SECOND (before tree) to reserve its space ──
        act = tk.Frame(self.parent_frame, padx=8, pady=2)
        act.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Button(act, text="◀ ASSIGN", command=self.assign_cue,
                   style="Assign.TButton").pack(side=tk.LEFT, padx=(0, 4), ipady=3)
        ttk.Button(act, text="Unassign", command=self.unassign_cue,
                   style="Danger.TButton").pack(side=tk.LEFT, padx=2, ipady=3)
        ttk.Button(act, text="Unassign All", command=self.unassign_all,
                   style="Danger.TButton").pack(side=tk.LEFT, padx=2, ipady=3)
        ttk.Button(act, text="✕ Delete", command=self.delete_item,
                   style="Danger.TButton").pack(side=tk.LEFT, padx=2, ipady=3)
        ttk.Button(act, text="▲ Up",     command=self.move_up,
                   style="Normal.TButton").pack(side=tk.LEFT, padx=(12, 2), ipady=3)
        ttk.Button(act, text="▼ Down",   command=self.move_down,
                   style="Normal.TButton").pack(side=tk.LEFT, padx=2, ipady=3)

        # ── Setlist treeview — fills all remaining space ───────────────────────
        content = tk.Frame(self.parent_frame, padx=8, pady=2)
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        tk.Label(content, text="🎵 Setlist Cue Order",
                 font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(0, 2))

        tree_frame = tk.Frame(content)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols_l = ("#", "Song (TXT)", "ID", "QLC+ Cue", "In", "Hold", "Out")
        self.tree_left = ttk.Treeview(tree_frame, columns=cols_l,
                                      show="headings", selectmode="browse")
        widths_l = [32, 160, 40, 200, 50, 50, 50]
        for col, w in zip(cols_l, widths_l):
            self.tree_left.heading(col, text=col)
            self.tree_left.column(col, width=w,
                                  anchor="center" if w <= 50 else "w")
        ttk.Scrollbar(tree_frame, orient="vertical",
                      command=self.tree_left.yview).pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree_left.bind("<<TreeviewSelect>>", self.on_left_select)

    # ──────────────────────────────────────────────────────────────────────────
    # Chaser dropdown helpers
    # ──────────────────────────────────────────────────────────────────────────
    def update_chaser_dropdown(self):
        options = ["[ Create New Chaser ]"] + sorted(self.mgr.app.chasers.keys())
        self.combo_chaser['values'] = options
        # If a linked chaser ID is known, select it in the dropdown
        if self.linked_chaser_id:
            id_to_name = {v: k for k, v in self.mgr.app.chasers.items()}
            name = id_to_name.get(self.linked_chaser_id, "")
            if name and name in options:
                self.chaser_var.set(name)
                return
        # Fallback: keep current value if still valid, else reset
        if self.chaser_var.get() not in options:
            self.chaser_var.set(options[0])

    def on_chaser_change(self, event):
        cn = self.chaser_var.get()
        if cn == "[ Create New Chaser ]":
            return
        cid = self.mgr.app.chasers.get(cn)
        if not cid:
            return
        if self.setlist_data and event is not None:
            if not messagebox.askyesno("Load Chaser",
                                       "Replace current setlist with this Chaser's steps?"):
                return
        self.setlist_data.clear()
        chaser_node = self.mgr.app.qxw_root.find(
            f"q:Engine/q:Function[@ID='{cid}']", NS)
        if chaser_node is not None:
            id_to_name = {v: k for k, v in self.mgr.app.func_by_name.items()}
            for step in chaser_node.findall('q:Step', NS):
                fid = step.text
                qn = id_to_name.get(fid, f"Unknown ID {fid}")
                raw_hold = step.get('Hold', '4294967294')
                # '0' means the chaser Speed block controls hold (i.e. infinite
                # when Duration="Common" / "4294967294").  Normalise to the
                # explicit infinite sentinel so the UI and saved XML are correct.
                if raw_hold == '0':
                    raw_hold = '4294967294'
                self.setlist_data.append({
                    "txt_name": qn, "qxw_name": qn, "qxw_id": fid,
                    "in": step.get('FadeIn', '0'),
                    "hold": raw_hold,
                    "out": step.get('FadeOut', '0')
                })
        self.refresh_left_tree()

    # ──────────────────────────────────────────────────────────────────────────
    # TXT loading
    # ──────────────────────────────────────────────────────────────────────────
    def load_txt_dialog(self):
        fn = filedialog.askopenfilename(title="Select Setlist TXT",
                                        filetypes=[("Text", "*.txt")])
        if fn:
            self.load_txt(fn)

    def load_txt(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
            self.current_txt_file = filename
            self.lbl_txt.config(text=os.path.basename(filename))
            self.setlist_data.clear()
            for line in lines:
                match_name, match_id = self.mgr.find_best_match(line)
                self.setlist_data.append({
                    "txt_name": line,
                    "qxw_name": match_name if match_id else "--- Unassigned ---",
                    "qxw_id": match_id,
                    "in": "1000", "hold": "4294967294", "out": "1000"
                })
            self.refresh_left_tree()
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            messagebox.showerror("Error", f"Failed to load TXT:\n{e}")

    # ──────────────────────────────────────────────────────────────────────────
    # Tree helpers
    # ──────────────────────────────────────────────────────────────────────────
    def apply_tree_tags(self):
        t = THEMES[self.mgr.app.current_theme]
        self.tree_left.tag_configure("missing",
                                     foreground=t["missing"],
                                     background=t["tree_bg"])
        self.tree_left.tag_configure("ok",
                                     foreground=t["tree_fg"],
                                     background=t["tree_bg"])

    def refresh_left_tree(self):
        self.tree_left.delete(*self.tree_left.get_children())
        for i, d in enumerate(self.setlist_data):
            tag = "missing" if not d["qxw_id"] else "ok"
            self.tree_left.insert("", tk.END, values=(
                f"{i + 1:02d}", d['txt_name'] or f"[Step {i}]",
                d['qxw_id'] or "---", d['qxw_name'],
                format_time_for_ui(d['in']),
                format_time_for_ui(d['hold']),
                format_time_for_ui(d['out'])
            ), tags=(tag,))
        self.update_duration_display()
        # Refresh usage counts in the shared right tree
        self.mgr.refresh_all_usage_counts()

    def update_duration_display(self):
        total_ms = 0
        for d in self.setlist_data:
            try:
                h  = int(d.get("hold", 0))
                fi = int(d.get("in",   0))
                fo = int(d.get("out",  0))
                if h  < 4000000000: total_ms += h
                if fi < 4000000000: total_ms += fi
                if fo < 4000000000: total_ms += fo
            except ValueError:
                pass
        s  = (total_ms // 1000)   % 60
        m  = (total_ms // 60000)  % 60
        hr =  total_ms // 3600000
        self.lbl_duration.config(text=f"Runtime: {hr:02d}:{m:02d}:{s:02d}")

    # ──────────────────────────────────────────────────────────────────────────
    # Actions
    # ──────────────────────────────────────────────────────────────────────────
    def on_left_select(self, event):
        sel = self.tree_left.selection()
        if not sel:
            return
        idx = self.tree_left.index(sel[0])
        d = self.setlist_data[idx]
        self.var_in.set(format_time_for_ui(d["in"]))
        self.var_hold.set(format_time_for_ui(d["hold"]))
        self.var_out.set(format_time_for_ui(d["out"]))

    def assign_cue(self):
        """Assign selected pool function → selected left-tree row."""
        sl = self.tree_left.selection()
        sr = self.mgr.tree_right.selection()
        if not sl:
            return messagebox.showwarning("Notice",
                                          "Select a row in the setlist first.")
        if not sr:
            return messagebox.showwarning("Notice",
                                          "Select a function in the pool first.")
        tags = self.mgr.tree_right.item(sr[0], "tags")
        if not tags:
            return messagebox.showwarning("Notice",
                                          "Select a specific function, not a folder.")
        fid   = tags[0]
        fname = self.mgr.app.func_detailed[fid]['name']
        idx   = self.tree_left.index(sl[0])
        self.setlist_data[idx]["qxw_name"] = fname
        self.setlist_data[idx]["qxw_id"]   = fid
        self.refresh_left_tree()
        children = self.tree_left.get_children()
        if idx + 1 < len(children):
            self.tree_left.selection_set(children[idx + 1])

    def unassign_cue(self):
        sel = self.tree_left.selection()
        if sel:
            idx = self.tree_left.index(sel[0])
            self.setlist_data[idx]["qxw_name"] = "--- Unassigned ---"
            self.setlist_data[idx]["qxw_id"]   = ""
            self.refresh_left_tree()

    def unassign_all(self):
        if not self.setlist_data:
            return
        assigned = sum(1 for d in self.setlist_data if d["qxw_id"])
        if assigned == 0:
            return messagebox.showinfo("Notice", "No assigned cues to unassign.")
        if not messagebox.askyesno("Unassign All",
                                   f"Unassign all {assigned} assigned cues in this slot?"):
            return
        for d in self.setlist_data:
            d["qxw_name"] = "--- Unassigned ---"
            d["qxw_id"]   = ""
        self.refresh_left_tree()

    def rename_chaser_to_cuelist(self):
        """Rename the linked chaser in the QXW XML to match the CueList caption."""
        if not self.cuelist_caption:
            return messagebox.showwarning("Notice",
                                          "This slot has no CueList caption to rename to.")
        cn = self.chaser_var.get()
        if cn == "[ Create New Chaser ]":
            return messagebox.showwarning("Notice",
                                          "Select a target chaser first.")
        cid = self.mgr.app.chasers.get(cn)
        if not cid:
            return
        # Rename in XML
        engine = self.mgr.app.qxw_root.find('q:Engine', NS)
        func = engine.find(f"q:Function[@ID='{cid}']", NS)
        if func is None:
            return messagebox.showerror("Error", f"Function ID {cid} not found in XML.")
        old_name = func.get('Name', '')
        new_name = self.cuelist_caption
        func.set('Name', new_name)
        # Update chasers dict
        del self.mgr.app.chasers[old_name]
        self.mgr.app.chasers[new_name] = cid
        self.chaser_var.set(new_name)
        # Refresh all slot dropdowns
        for slot in self.mgr.slots:
            slot.update_chaser_dropdown()
        messagebox.showinfo("Renamed",
                            f"Chaser renamed:\n«{old_name}»  →  «{new_name}»")

    def update_timings(self):
        sel = self.tree_left.selection()
        if not sel:
            return
        try:
            fi = parse_time_for_xml(self.var_in.get())
            fh = parse_time_for_xml(self.var_hold.get())
            fo = parse_time_for_xml(self.var_out.get())
            for item in sel:
                idx = self.tree_left.index(item)
                self.setlist_data[idx]["in"]   = fi
                self.setlist_data[idx]["hold"]  = fh
                self.setlist_data[idx]["out"]  = fo
            self.refresh_left_tree()
        except ValueError:
            messagebox.showerror("Input Error",
                                 "Timings must be numeric or 'Inf'.")

    def move_up(self):
        sel = self.tree_left.selection()
        if not sel:
            return
        idx = self.tree_left.index(sel[0])
        if idx > 0:
            self.setlist_data[idx], self.setlist_data[idx - 1] = \
                self.setlist_data[idx - 1], self.setlist_data[idx]
            self.refresh_left_tree()
            self.tree_left.selection_set(self.tree_left.get_children()[idx - 1])

    def move_down(self):
        sel = self.tree_left.selection()
        if not sel:
            return
        idx = self.tree_left.index(sel[0])
        if idx < len(self.setlist_data) - 1:
            self.setlist_data[idx], self.setlist_data[idx + 1] = \
                self.setlist_data[idx + 1], self.setlist_data[idx]
            self.refresh_left_tree()
            self.tree_left.selection_set(self.tree_left.get_children()[idx + 1])

    def delete_item(self):
        sel = self.tree_left.selection()
        if sel:
            idx = self.tree_left.index(sel[0])
            self.setlist_data.pop(idx)
            self.refresh_left_tree()
            children = self.tree_left.get_children()
            if children:
                self.tree_left.selection_set(
                    children[min(idx, len(children) - 1)])

    # ──────────────────────────────────────────────────────────────────────────
    # Exports
    # ──────────────────────────────────────────────────────────────────────────
    def export_txt(self):
        if not self.setlist_data:
            return messagebox.showwarning("Warning", "Setlist is empty.")
        fp = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text", "*.txt")],
            title="Export XML Code",
            initialfile=f"Slot{self.slot_index + 1}_Code_Export.txt")
        if not fp:
            return
        try:
            xl = ['', f'<Function ID="NEW_ID" Type="Chaser" Name="{self.chaser_var.get()}">',
                  ' <Speed FadeIn="0" FadeOut="0" Duration="4294967294"/>',
                  ' <Direction>Forward</Direction>', ' <RunOrder>Loop</RunOrder>',
                  ' <SpeedModes FadeIn="PerStep" FadeOut="PerStep" Duration="Common"/>']
            sc = 0
            for d in self.setlist_data:
                if d["qxw_id"]:
                    xl.append(
                        f' <Step Number="{sc}" FadeIn="{d["in"]}" '
                        f'Hold="{d["hold"]}" FadeOut="{d["out"]}">'
                        f'{d["qxw_id"]}</Step>')
                    sc += 1
            xl.append('</Function>')
            with open(fp, 'w', encoding='utf-8') as f:
                f.write("\n".join(xl))
            messagebox.showinfo("Success", f"XML code exported to:\n{fp}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n{e}")

    def export_setlist_pdf(self):
        if not self.setlist_data:
            return messagebox.showwarning("Warning", "Setlist is empty!")

        dlg = tk.Toplevel(self.parent_frame)
        dlg.title("PDF Column Settings")
        dlg.geometry("340x370")
        dlg.resizable(False, False)
        dlg.grab_set()

        t = THEMES[self.mgr.app.current_theme]
        dlg.configure(bg=t["bg"])

        tk.Label(dlg, text="Select columns to include:",
                 font=("Helvetica", 11, "bold"),
                 bg=t["bg"], fg=t["fg"]).pack(anchor="w", padx=16, pady=(14, 8))

        col_defs = [
            ("num",      "#",                  True),
            ("song",     "Song / Step Name",   True),
            ("cue",      "QLC+ Assigned Cue",  True),
            ("fade_in",  "Fade In",            True),
            ("hold",     "Hold",               True),
            ("fade_out", "Fade Out",           True),
        ]
        col_vars = {}
        for key, label, default in col_defs:
            var = tk.BooleanVar(value=default)
            col_vars[key] = var
            ttk.Checkbutton(dlg, text=label, variable=var).pack(
                anchor="w", padx=32, pady=2)

        ttk.Separator(dlg, orient="horizontal").pack(fill=tk.X, padx=16, pady=8)

        notes_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dlg, text='Add "Notes" column (fills remaining space)',
                        variable=notes_var).pack(anchor="w", padx=32, pady=2)

        tk.Label(dlg, text="Paper size:",
                 font=("Helvetica", 9),
                 bg=t["bg"], fg=t["fg"]).pack(anchor="w", padx=16, pady=(12, 2))
        paper_var = tk.StringVar(value="A4 Portrait")
        ttk.Combobox(dlg, textvariable=paper_var, state="readonly", width=22,
                     values=["A4 Portrait", "A4 Landscape",
                             "US Letter Portrait", "US Letter Landscape"]).pack(
            anchor="w", padx=32)

        result = {"go": False}
        def on_export():
            result["go"] = True; dlg.destroy()

        btn_frame = tk.Frame(dlg, bg=t["bg"])
        btn_frame.pack(fill=tk.X, padx=16, pady=14)
        ttk.Button(btn_frame, text="Cancel",     style="Normal.TButton",
                   command=dlg.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(btn_frame, text="Export PDF", style="Save.TButton",
                   command=on_export).pack(side=tk.RIGHT)

        dlg.wait_window()
        if not result["go"]:
            return

        selected = [(k, lbl) for k, lbl, _ in col_defs if col_vars[k].get()]
        if not selected:
            return messagebox.showwarning("Warning", "Select at least one column!")

        paper_sizes = {
            "A4 Portrait": (595.0, 842.0), "A4 Landscape": (842.0, 595.0),
            "US Letter Portrait": (612.0, 792.0), "US Letter Landscape": (792.0, 612.0),
        }
        W, H = paper_sizes.get(paper_var.get(), (595.0, 842.0))

        bn = (os.path.splitext(os.path.basename(self.mgr.app.current_qxw_file))[0]
              if self.mgr.app.current_qxw_file else f"Slot{self.slot_index+1}")
        fp = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            title="Export PDF",
            initialfile=f"{bn}_Slot{self.slot_index+1}_Setlist.pdf")
        if not fp:
            return
        try:
            pdf = self._build_setlist_pdf(W, H, selected, notes_var.get())
            if pdf:
                with open(fp, "wb") as f:
                    f.write(pdf)
                messagebox.showinfo("Success", f"PDF exported to:\n{fp}")
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            messagebox.showerror("Error", f"PDF export failed:\n{e}")

    def _build_setlist_pdf(self, W, H, selected_cols, include_notes):
        if not self.setlist_data:
            return None

        header_col  = (0.12, 0.12, 0.18)
        row_alt     = (0.95, 0.97, 1.00)
        show_name   = (os.path.basename(self.mgr.app.current_qxw_file)
                       if self.mgr.app.current_qxw_file else "Untitled")
        slot_label  = self.cuelist_caption or f"Slot {self.slot_index + 1}"
        doc_date    = datetime.date.today().strftime("%Y-%m-%d")

        pages, cur_ln = [], []

        def sc(r, g, b):  cur_ln.append(f"{r:.4f} {g:.4f} {b:.4f} RG")
        def fc(r, g, b):  cur_ln.append(f"{r:.4f} {g:.4f} {b:.4f} rg")
        def lw(w):        cur_ln.append(f"{w} w")
        def rfill(x, y, w, h, col):
            fc(*col); cur_ln.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")
        def rbox(x, y, w, h, fcol, scol, wd=0.5):
            fc(*fcol); sc(*scol); lw(wd)
            cur_ln.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re B")
        def txt(x, y, s, sz=8, bold=False):
            s = str(s).encode('latin-1', errors='replace').decode('latin-1')
            s = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            cur_ln.append(
                f"BT {'/F2' if bold else '/F1'} {sz} Tf "
                f"{x:.2f} {y:.2f} Td ({s}) Tj ET")

        TITLE_H  = 40; T_PAD = 14; ROW_H = 24; HDR_H = 26
        BODY_SZ  = 10; HDR_SZ = 10; NUM_SZ = 11
        dark_hdr = (0.22, 0.30, 0.45)

        base_widths = {"num": 28, "song": 0, "cue": 0,
                       "fade_in": 48, "hold": 48, "fade_out": 48}
        usable_w  = W - 2 * T_PAD
        fixed_used = sum(base_widths.get(k, 0)
                         for k, _ in selected_cols if base_widths.get(k, 0) > 0)
        flex_keys  = [k for k, _ in selected_cols if base_widths.get(k, 0) == 0]
        notes_min_w = 100 if include_notes else 0
        remaining   = usable_w - fixed_used - notes_min_w
        flex_w = max(60, remaining / len(flex_keys)) if flex_keys else 0

        col_labels, col_w = [], []
        for key, label in selected_cols:
            col_labels.append(label)
            bw = base_widths.get(key, 0)
            col_w.append(bw if bw > 0 else flex_w)
        if include_notes:
            used    = sum(col_w)
            notes_w = max(notes_min_w, usable_w - used)
            col_labels.append("Notes"); col_w.append(notes_w)

        col_x, cx = [], T_PAD
        for w in col_w:
            col_x.append(cx); cx += w

        def get_row_values(ri, d):
            vals = []
            for key, _ in selected_cols:
                if   key == "num":
                    vals.append(f"{ri + 1:02d}")
                elif key == "song":
                    vals.append((d["txt_name"] or "")
                                [:int(flex_w / (BODY_SZ * 0.5))])
                elif key == "cue":
                    vals.append((d["qxw_name"] or "")
                                [:int(flex_w / (BODY_SZ * 0.5))])
                elif key == "fade_in":  vals.append(format_time_for_ui(d['in']))
                elif key == "hold":     vals.append(format_time_for_ui(d['hold']))
                elif key == "fade_out": vals.append(format_time_for_ui(d['out']))
            if include_notes:
                vals.append("")
            return vals

        def finish_page():
            if cur_ln:
                pages.append(zlib.compress("\n".join(cur_ln).encode("latin-1")))
                cur_ln.clear()

        def draw_header(pn):
            rfill(0, H - TITLE_H, W, TITLE_H, header_col)
            cur_ln.append("1 1 1 rg")
            txt(14, H - TITLE_H + 18,
                f"SETLIST: {show_name}  ·  {slot_label}", sz=14, bold=True)
            txt(W - 200, H - TITLE_H + 22, f"Date: {doc_date}", sz=9)
            txt(W - 200, H - TITLE_H + 10, f"Page {pn}", sz=9)
            T_TOP = H - TITLE_H - T_PAD
            hy    = T_TOP - HDR_H
            for cx2, cw2 in zip(col_x, col_w):
                rbox(cx2, hy, cw2, HDR_H, dark_hdr, (0.1, 0.2, 0.35), 0.3)
            cur_ln.append("1 1 1 rg")
            for lbl, cx2 in zip(col_labels, col_x):
                txt(cx2 + 4, hy + 8, lbl, sz=HDR_SZ, bold=True)
            return hy

        pn = 1; cy = draw_header(pn)
        for ri, d in enumerate(self.setlist_data):
            cy -= ROW_H
            if cy < T_PAD:
                finish_page(); pn += 1; cy = draw_header(pn); cy -= ROW_H
            rc = row_alt if ri % 2 == 0 else (1.0, 1.0, 1.0)
            for cx2, cw2 in zip(col_x, col_w):
                rbox(cx2, cy, cw2, ROW_H, rc, (0.75, 0.80, 0.88), 0.25)
            cur_ln.append("0 0 0 rg")
            vals = get_row_values(ri, d)
            for vi, v in enumerate(vals):
                is_num = (vi == 0 and selected_cols[0][0] == "num")
                txt(col_x[vi] + 5, cy + 7, v,
                    sz=NUM_SZ if is_num else BODY_SZ, bold=is_num)
        finish_page()
        return SetlistManagerTab._assemble_pdf(pages, W, H)

    # ──────────────────────────────────────────────────────────────────────────
    # Save & clone generation  (same logic as the original, scoped to this slot)
    # ──────────────────────────────────────────────────────────────────────────
    def save_qxw(self):
        app = self.mgr.app
        if not app.qxw_root:
            return messagebox.showwarning("Warning", "No QXW loaded!")
        unassigned = sum(1 for d in self.setlist_data if not d["qxw_id"])
        if unassigned > 0:
            if not messagebox.askyesno(
                    "Warning",
                    f"{unassigned} unassigned cues will be skipped.\nSave anyway?"):
                return

        target_name   = self.chaser_var.get()
        engine        = app.qxw_root.find('q:Engine', NS)
        master_chaser = None
        linked        = False
        mc_id         = None

        if target_name == "[ Create New Chaser ]":
            app.highest_func_id += 1
            mc_id = str(app.highest_func_id)
            master_chaser = ET.SubElement(
                engine, f"{{{QLC_NS_URI}}}Function",
                {'ID': mc_id, 'Type': "Chaser",
                 'Name': f"Setlist Chaser Slot{self.slot_index + 1} (Auto)"})
            ET.SubElement(master_chaser, f"{{{QLC_NS_URI}}}Speed",
                          {'FadeIn': "0", 'FadeOut': "0", 'Duration': "4294967294"})
            ET.SubElement(master_chaser, f"{{{QLC_NS_URI}}}Direction").text = "Forward"
            ET.SubElement(master_chaser, f"{{{QLC_NS_URI}}}RunOrder").text  = "Loop"
            ET.SubElement(master_chaser, f"{{{QLC_NS_URI}}}SpeedModes",
                          {'FadeIn': "PerStep", 'FadeOut': "PerStep",
                           'Duration': "Common"})
            # Auto-link: prefer the CueList that corresponds to this slot
            linked_cl = None
            if self.cuelist_caption:
                for cl in app.qxw_root.findall('.//q:CueList', NS):
                    if cl.get('Caption', '') == self.cuelist_caption:
                        linked_cl = cl; break
            if linked_cl is None:
                # Fallback: first unlinked CueList
                for cl in app.qxw_root.findall('.//q:CueList', NS):
                    cn = cl.find('q:Chaser', NS)
                    if cn is not None and cn.text in ("4294967295", "-1"):
                        linked_cl = cl; break
            if linked_cl is not None:
                cn = linked_cl.find('q:Chaser', NS)
                if cn is not None:
                    cn.text = mc_id; linked = True
        else:
            mc_id = app.chasers.get(target_name)
            master_chaser = engine.find(f"q:Function[@ID='{mc_id}']", NS)
            if master_chaser is not None:
                for step in master_chaser.findall('q:Step', NS):
                    master_chaser.remove(step)
                # Ensure Speed/SpeedModes are correct for per-step infinite hold
                spd = master_chaser.find('q:Speed', NS)
                if spd is not None:
                    spd.set('Duration', '4294967294')
                spm = master_chaser.find('q:SpeedModes', NS)
                if spm is not None:
                    spm.set('FadeIn', 'PerStep')
                    spm.set('FadeOut', 'PerStep')
                    spm.set('Duration', 'Common')

        if master_chaser is None:
            return

        if self.mgr.enforce_naming_var.get():
            for func in engine.findall('q:Function', NS):
                fid = func.get('ID'); fname = func.get('Name', '')
                if fid == mc_id or "(Auto-Clone)" in fname or "(Setlist)" in fname:
                    continue
                bi = app.vc_buttons.get(fid)
                if bi and bi['captions']:
                    func.set('Name', " | ".join(sorted(bi['captions'])))
                else:
                    func.set('Name',
                             f"[{fid}] {func.get('Type', 'Function')} - Unassigned")

        # Collect the clone IDs that SHOULD exist after this save
        # (so we only delete orphaned clones from THIS chaser, not other slots)
        step_count = 0
        active_ids = set()
        for d in self.setlist_data:
            bid = d["qxw_id"]
            if not bid:
                continue
            base = engine.find(f"q:Function[@ID='{bid}']", NS)
            if base is None:
                continue
            txt_n = d["txt_name"] or f"Step {step_count}"
            app.highest_func_id += 1
            cid = str(app.highest_func_id)
            active_ids.add(cid)
            clone = copy.deepcopy(base)
            clone.set('ID', cid)
            clone.set('Name', f"{txt_n} (Setlist)")
            engine.append(clone)
            sa = {'Number': str(step_count), 'FadeIn': d['in'],
                  'Hold': d['hold'], 'FadeOut': d['out']}
            ns2 = ET.SubElement(master_chaser, f"{{{QLC_NS_URI}}}Step", sa)
            ns2.text = cid; ns2.tail = "\n   "
            step_count += 1

        # Remove stale Setlist clones that were previously linked to THIS chaser.
        # We detect them as functions whose name ends in "(Setlist)" and whose ID
        # is NOT in active_ids AND is NOT referenced by any other chaser's steps.
        used_by_others = set()
        for f in engine.findall('q:Function', NS):
            fid_other = f.get('ID')
            if fid_other == mc_id:
                continue
            for step in f.findall('q:Step', NS):
                if step.text:
                    used_by_others.add(step.text)

        for func in engine.findall('q:Function', NS):
            fn  = func.get('Name', '')
            fid = func.get('ID')
            if ("(Setlist)" in fn) and (fid not in active_ids) \
                    and (fid not in used_by_others):
                engine.remove(func)

        # ── Write output file ─────────────────────────────────────────────────
        odir = os.path.dirname(app.current_qxw_file)
        obn  = os.path.splitext(os.path.basename(app.current_qxw_file))[0]
        m    = re.search(r'(\d+)$', obn)
        if m:
            bn = obn[:m.start()] + str(int(m.group(1)) + 1).zfill(len(m.group(1)))
        else:
            bn = f"{obn}_GIG_READY"
        nf = os.path.join(odir, bn + ".qxw")

        if os.path.exists(nf):
            ans = messagebox.askyesnocancel(
                "Exists",
                f"'{bn}.qxw' exists.\n\nYes=Overwrite  No=New file  Cancel=Abort")
            if ans is None:
                return
            if not ans:
                while os.path.exists(nf):
                    m2 = re.search(r'(\d+)$', bn)
                    bn = (bn[:m2.start()]
                          + str(int(m2.group(1)) + 1).zfill(len(m2.group(1)))
                          ) if m2 else bn + "_1"
                    nf = os.path.join(odir, bn + ".qxw")

        try:
            xb = ET.tostring(app.qxw_root, encoding="utf-8").decode("utf-8")
            with open(nf, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<!DOCTYPE Workspace>\n' + xb)
            app.current_qxw_file = nf
            t2 = THEMES[app.current_theme]
            app.lbl_qxw.config(text=os.path.basename(nf), fg=t2["lbl_green"])
            msg = f"Saved {step_count} cues to:\n{os.path.basename(nf)}"
            if linked:
                msg += "\n\nAuto-linked to Virtual Console Cue List!"
            messagebox.showinfo("Success", msg)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed:\n{e}")


# ──────────────────────────────────────────────────────────────────────────────

class SetlistManagerTab:
    """
    Hosts N SetlistSlot panels (one per CueList in the showfile) inside an
    inner ttk.Notebook, plus the shared QLC+ function-pool tree on the right.
    """

    def __init__(self, parent, app: QLCSwissKnife):
        self.parent = parent
        self.app    = app

        self.slots            = []         # list[SetlistSlot]
        self.current_desc_file = ""

        self._build_ui()

    # ──────────────────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Global top bar ────────────────────────────────────────────────────
        top = tk.Frame(self.parent, padx=10, pady=6)
        top.pack(fill=tk.X)

        ttk.Button(top, text="📄 Load Dictionary TXT",
                   command=self.load_desc_dialog,
                   style="Normal.TButton").pack(side=tk.LEFT)
        self.lbl_desc = tk.Label(top, text="No dictionary",
                                 font=("Helvetica", 9, "bold"))
        self.lbl_desc.pack(side=tk.LEFT, padx=(5, 15))

        self.enforce_naming_var = tk.BooleanVar(value=False)
        chk_enforce = ttk.Checkbutton(top, text="Enforce VC Naming",
                                      variable=self.enforce_naming_var)
        chk_enforce.pack(side=tk.LEFT, padx=8)
        ToolTip(chk_enforce,
                "When checked, on SAVE the script renames all base pool "
                "functions to match their Virtual Console button captions.\n\n"
                "Unassigned functions get tagged as '[ID] Type - Unassigned'.\n"
                "This keeps your QLC+ pool tidy but modifies original names.")

        ttk.Button(top, text="➕ Add Slot",
                   command=self.add_empty_slot,
                   style="Normal.TButton").pack(side=tk.LEFT, padx=(20, 4))
        ttk.Button(top, text="🗑 Remove Active Slot",
                   command=self.remove_active_slot,
                   style="Danger.TButton").pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(top, text="💾 SAVE ALL SLOTS",
                   command=self.save_all_slots,
                   style="Save.TButton").pack(side=tk.LEFT, padx=(20, 4), ipady=3)

        ttk.Button(top, text="📝 Dict",
                   command=self.export_dictionary,
                   style="Export.TButton").pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(top, text="🧹 Find Orphans",
                   command=self.find_orphans,
                   style="Normal.TButton").pack(side=tk.RIGHT)

        # ── Main split: slots notebook (left) + function pool (right) ─────────
        main = tk.PanedWindow(self.parent, orient=tk.HORIZONTAL,
                              sashrelief=tk.RAISED, sashwidth=6)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # LEFT pane — inner notebook of slots
        left_outer = tk.Frame(main)
        main.add(left_outer, minsize=400)

        self.slot_notebook = ttk.Notebook(left_outer)
        self.slot_notebook.pack(fill=tk.BOTH, expand=True)

        # RIGHT pane — shared function pool
        right_outer = tk.Frame(main)
        main.add(right_outer, minsize=500)
        self._build_pool_panel(right_outer)

    def _build_pool_panel(self, parent):
        """Builds the shared QLC+ function pool panel."""
        rtop = tk.Frame(parent, padx=4, pady=4)
        rtop.pack(fill=tk.X)

        tk.Label(rtop, text="🎛 QLC+ Function Pool",
                 font=("Helvetica", 10, "bold")).pack(side=tk.LEFT)

        tk.Label(rtop, text="Search:", font=("Helvetica", 8)).pack(
            side=tk.LEFT, padx=(12, 2))
        self.search_var = tk.StringVar()
        ttk.Entry(rtop, textvariable=self.search_var, width=14).pack(side=tk.LEFT)
        self.search_var.trace_add("write", lambda *a: self.populate_right_tree())

        self.frame_filter_var = tk.StringVar(value="All Frames")
        self.combo_frame_filter = ttk.Combobox(rtop, textvariable=self.frame_filter_var,
                                               state="readonly", width=16)
        self.combo_frame_filter.pack(side=tk.RIGHT, padx=4)
        self.combo_frame_filter.bind("<<ComboboxSelected>>",
                                     lambda e: self.populate_right_tree())
        tk.Label(rtop, text="Frame:", font=("Helvetica", 8)).pack(side=tk.RIGHT)

        self.show_vc_only_var = tk.BooleanVar(value=True)
        chk_vc = ttk.Checkbutton(rtop, text="VC Only",
                                  variable=self.show_vc_only_var,
                                  command=self.populate_right_tree)
        chk_vc.pack(side=tk.RIGHT, padx=6)
        ToolTip(chk_vc,
                "When checked, only shows functions that are assigned to a "
                "Virtual Console button.\n\n"
                "Uncheck to see ALL functions in the QXW pool, including "
                "background building blocks not on any VC button.")

        tree_c = tk.Frame(parent)
        tree_c.pack(fill=tk.BOTH, expand=True, padx=4)

        cols_r = ("ID", "Contains", "Uses", "VC Button", "Description")
        self.tree_right = ttk.Treeview(tree_c, columns=cols_r, selectmode="browse")
        self.tree_right.heading("#0", text="Function Name")
        for c in cols_r:
            self.tree_right.heading(c, text=c)
        self.tree_right.column("#0",          width=200, minwidth=180)
        self.tree_right.column("ID",          width=48,  anchor="center")
        self.tree_right.column("Contains",    width=65,  anchor="center")
        self.tree_right.column("Uses",        width=50,  anchor="center")
        self.tree_right.column("VC Button",   width=140, anchor="w")
        self.tree_right.column("Description", width=300, anchor="w")

        ttk.Scrollbar(tree_c, orient="vertical",
                      command=self.tree_right.yview).pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Slot management
    # ──────────────────────────────────────────────────────────────────────────
    def _make_slot(self, cuelist_caption="", chaser_id="", chaser_name=""):
        """Create a new SetlistSlot and add it to the inner notebook."""
        idx        = len(self.slots)
        tab_frame  = tk.Frame(self.slot_notebook)
        tab_label  = cuelist_caption or f"Slot {idx + 1}"
        self.slot_notebook.add(tab_frame, text=f"  {tab_label}  ")
        slot = SetlistSlot(tab_frame, self, idx,
                           cuelist_caption=cuelist_caption,
                           chaser_id=chaser_id,
                           chaser_name=chaser_name)
        self.slots.append(slot)
        # Select the newly created tab
        self.slot_notebook.select(len(self.slot_notebook.tabs()) - 1)
        return slot

    def add_empty_slot(self):
        slot = self._make_slot()
        slot.update_chaser_dropdown()
        self.app.set_status(f"Added Slot {slot.slot_index + 1}.")

    def remove_active_slot(self):
        if len(self.slots) <= 1:
            return messagebox.showwarning("Notice",
                                          "At least one slot must remain.")
        idx = self.slot_notebook.index(self.slot_notebook.select())
        if not messagebox.askyesno("Remove Slot",
                                   f"Remove Slot {idx + 1}?"):
            return
        # Destroy the tab widget
        tab_id = self.slot_notebook.tabs()[idx]
        self.slot_notebook.forget(tab_id)
        self.slots.pop(idx)
        # Re-number remaining slots
        for i, s in enumerate(self.slots):
            s.slot_index = i

    def _active_slot(self):
        """Return the currently visible SetlistSlot (or None)."""
        if not self.slots:
            return None
        try:
            idx = self.slot_notebook.index(self.slot_notebook.select())
            return self.slots[idx]
        except Exception:
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # Callbacks from shell
    # ──────────────────────────────────────────────────────────────────────────
    def on_qxw_loaded(self):
        # Rebuild slots from the CueLists found in the workspace
        # First, clear the old notebook tabs
        for tab in self.slot_notebook.tabs():
            self.slot_notebook.forget(tab)
        self.slots.clear()

        id_to_name = {v: k for k, v in self.app.chasers.items()}

        cuelist_nodes = self.app.qxw_root.findall('.//q:CueList', NS)
        if cuelist_nodes:
            for cl in cuelist_nodes:
                caption    = cl.get('Caption', '')
                chaser_node = cl.find('q:Chaser', NS)
                chaser_id  = chaser_node.text if chaser_node is not None else ""
                # Ignore unlinked placeholder IDs
                if chaser_id in ("4294967295", "-1"):
                    chaser_id = ""
                chaser_name = id_to_name.get(chaser_id, "")
                self._make_slot(cuelist_caption=caption,
                                chaser_id=chaser_id,
                                chaser_name=chaser_name)
        else:
            # No CueLists in the workspace: create one blank slot
            self._make_slot()

        # Update dropdowns and pool in all slots
        for slot in self.slots:
            slot.update_chaser_dropdown()
            slot.apply_tree_tags()

        self.combo_frame_filter['values'] = (
            ["All Frames"] + sorted(list(self.app.available_frames)))
        self.frame_filter_var.set("All Frames")
        self.populate_right_tree()

    def on_theme_changed(self):
        t = THEMES[self.app.current_theme]
        for slot in self.slots:
            slot.apply_tree_tags()
        self.tree_right.tag_configure("used", foreground=t["lbl_green"])

    # ──────────────────────────────────────────────────────────────────────────
    # Shared function-pool methods (used by all slots)
    # ──────────────────────────────────────────────────────────────────────────
    def find_best_match(self, query):
        """Fuzzy match a setlist line against QLC+ function names."""
        fbn = self.app.func_by_name
        if not fbn:
            return "", ""
        if query in fbn:
            return query, fbn[query]
        q_lower = query.lower()
        matches = [(n, i) for n, i in fbn.items() if q_lower in n.lower()]
        if len(matches) == 1:
            return matches[0]
        trans    = str.maketrans(string.punctuation, ' ' * len(string.punctuation))
        q_tokens = set(query.translate(trans).lower().split())
        best, best_id, max_ov = "", "", 0
        for name, fid in fbn.items():
            ov = len(q_tokens.intersection(
                set(name.translate(trans).lower().split())))
            if ov > max_ov:
                max_ov, best, best_id = ov, name, fid
        mn = min(2, len(q_tokens)) if q_tokens else 1
        if max_ov >= mn:
            return best, best_id
        if matches:
            return matches[0]
        close = difflib.get_close_matches(
            q_lower, [n.lower() for n in fbn], n=1, cutoff=0.6)
        if close:
            for name, fid in fbn.items():
                if name.lower() == close[0]:
                    return name, fid
        return "", ""

    def populate_right_tree(self):
        self.tree_right.delete(*self.tree_right.get_children())
        fd = self.app.func_detailed
        if not fd:
            return

        # Aggregate usage across ALL slots
        usage_counts = {}
        for slot in self.slots:
            for d in slot.setlist_data:
                if d["qxw_id"]:
                    usage_counts[d["qxw_id"]] = \
                        usage_counts.get(d["qxw_id"], 0) + 1

        fvc = self.show_vc_only_var.get()
        ff  = self.frame_filter_var.get()
        st  = self.search_var.get().lower().strip()

        for f_type in sorted(set(d['type'] for d in fd.values())):
            items    = [(fid, det) for fid, det in fd.items()
                        if det['type'] == f_type]
            filtered = []
            for fid, det in items:
                if st and st not in fid and st not in det['name'].lower():
                    continue
                btn_info = self.app.vc_buttons.get(fid)
                if fvc and not btn_info:
                    continue
                if ff != "All Frames":
                    if not btn_info or ff not in btn_info['frames']:
                        continue
                filtered.append((fid, det))
            if not filtered:
                continue
            parent_node = self.tree_right.insert("", tk.END,
                                                 text=f"📂 {f_type}s", open=True)
            filtered.sort(key=lambda x: int(x[0]))
            for fid, det in filtered:
                desc     = self.app.shared_descriptions.get(fid, "")
                uses     = usage_counts.get(fid, 0)
                btn_info = self.app.vc_buttons.get(fid)
                vc_btn   = " | ".join(sorted(btn_info['captions'])) \
                           if btn_info else ""
                tags     = (fid, "used") if uses > 0 else (fid,)
                uses_d   = f"★ {uses}" if uses > 0 else str(uses)
                self.tree_right.insert(parent_node, tk.END,
                                       text=f" {det['name']}",
                                       values=(fid, det['contains'],
                                               uses_d, vc_btn, desc),
                                       tags=tags)

    def refresh_all_usage_counts(self):
        """Re-paint the 'Uses' column without a full tree rebuild."""
        if not self.tree_right.get_children():
            return
        usage_counts = {}
        for slot in self.slots:
            for d in slot.setlist_data:
                if d["qxw_id"]:
                    usage_counts[d["qxw_id"]] = \
                        usage_counts.get(d["qxw_id"], 0) + 1

        def _update(node):
            tags = self.tree_right.item(node, "tags")
            if tags:
                fid  = tags[0]
                uses = usage_counts.get(fid, 0)
                vals = list(self.tree_right.item(node, "values"))
                while len(vals) < 5:
                    vals.append("")
                vals[2] = f"★ {uses}" if uses > 0 else str(uses)
                self.tree_right.item(node, values=vals,
                                     tags=(fid, "used") if uses > 0 else (fid,))
            for c in self.tree_right.get_children(node):
                _update(c)

        for it in self.tree_right.get_children():
            _update(it)

    # ──────────────────────────────────────────────────────────────────────────
    # Global save (all slots, one file write)
    # ──────────────────────────────────────────────────────────────────────────
    def save_all_slots(self):
        """
        Iterate every slot and apply its setlist to the XML tree, then write
        the output file once. Identical clone-pruning logic as the per-slot
        save, but runs across all chasers in a single pass.
        """
        app = self.app
        if not app.qxw_root:
            return messagebox.showwarning("Warning", "No QXW loaded!")

        total_unassigned = sum(
            sum(1 for d in s.setlist_data if not d["qxw_id"])
            for s in self.slots)
        if total_unassigned > 0:
            if not messagebox.askyesno(
                    "Warning",
                    f"{total_unassigned} unassigned cues across all slots "
                    f"will be skipped.\nSave anyway?"):
                return

        engine = app.qxw_root.find('q:Engine', NS)
        all_active_ids = set()
        slot_summaries = []

        for slot in self.slots:
            target_name   = slot.chaser_var.get()
            master_chaser = None
            linked        = False
            mc_id         = None

            if target_name == "[ Create New Chaser ]":
                app.highest_func_id += 1
                mc_id = str(app.highest_func_id)
                master_chaser = ET.SubElement(
                    engine, f"{{{QLC_NS_URI}}}Function",
                    {'ID': mc_id, 'Type': "Chaser",
                     'Name': (f"Setlist Chaser "
                              f"{slot.cuelist_caption or f'Slot{slot.slot_index+1}'}"
                              f" (Auto)")})
                ET.SubElement(master_chaser, f"{{{QLC_NS_URI}}}Speed",
                              {'FadeIn': "0", 'FadeOut': "0",
                               'Duration': "4294967294"})
                ET.SubElement(master_chaser,
                              f"{{{QLC_NS_URI}}}Direction").text = "Forward"
                ET.SubElement(master_chaser,
                              f"{{{QLC_NS_URI}}}RunOrder").text  = "Loop"
                ET.SubElement(master_chaser, f"{{{QLC_NS_URI}}}SpeedModes",
                              {'FadeIn': "PerStep", 'FadeOut': "PerStep",
                               'Duration': "Common"})
                # Auto-link to this slot's CueList (or first free one)
                linked_cl = None
                if slot.cuelist_caption:
                    for cl in app.qxw_root.findall('.//q:CueList', NS):
                        if cl.get('Caption', '') == slot.cuelist_caption:
                            linked_cl = cl; break
                if linked_cl is None:
                    for cl in app.qxw_root.findall('.//q:CueList', NS):
                        cn = cl.find('q:Chaser', NS)
                        if cn is not None and cn.text in ("4294967295", "-1"):
                            linked_cl = cl; break
                if linked_cl is not None:
                    cn = linked_cl.find('q:Chaser', NS)
                    if cn is not None:
                        cn.text = mc_id; linked = True
            else:
                mc_id = app.chasers.get(target_name)
                master_chaser = engine.find(f"q:Function[@ID='{mc_id}']", NS)
                if master_chaser is not None:
                    for step in master_chaser.findall('q:Step', NS):
                        master_chaser.remove(step)
                    # Ensure Speed/SpeedModes are correct for per-step infinite hold
                    spd = master_chaser.find('q:Speed', NS)
                    if spd is not None:
                        spd.set('Duration', '4294967294')
                    spm = master_chaser.find('q:SpeedModes', NS)
                    if spm is not None:
                        spm.set('FadeIn', 'PerStep')
                        spm.set('FadeOut', 'PerStep')
                        spm.set('Duration', 'Common')

            if master_chaser is None:
                slot_summaries.append((slot, 0, False))
                continue

            if self.enforce_naming_var.get():
                for func in engine.findall('q:Function', NS):
                    fid2  = func.get('ID')
                    fname = func.get('Name', '')
                    if fid2 == mc_id or "(Auto-Clone)" in fname \
                            or "(Setlist)" in fname:
                        continue
                    bi = app.vc_buttons.get(fid2)
                    if bi and bi['captions']:
                        func.set('Name', " | ".join(sorted(bi['captions'])))
                    else:
                        func.set('Name',
                                 f"[{fid2}] {func.get('Type','Function')} "
                                 f"- Unassigned")

            step_count = 0
            for d in slot.setlist_data:
                bid = d["qxw_id"]
                if not bid:
                    continue
                base = engine.find(f"q:Function[@ID='{bid}']", NS)
                if base is None:
                    continue
                txt_n = d["txt_name"] or f"Step {step_count}"
                app.highest_func_id += 1
                cid = str(app.highest_func_id)
                all_active_ids.add(cid)
                clone = copy.deepcopy(base)
                clone.set('ID', cid)
                clone.set('Name', f"{txt_n} (Setlist)")
                engine.append(clone)
                sa = {'Number': str(step_count), 'FadeIn': d['in'],
                      'Hold': d['hold'], 'FadeOut': d['out']}
                ns2 = ET.SubElement(master_chaser, f"{{{QLC_NS_URI}}}Step", sa)
                ns2.text = cid; ns2.tail = "\n   "
                step_count += 1

            slot_summaries.append((slot, step_count, linked))

        # Prune stale Setlist clones not referenced by any active chaser
        used_by_chasers = set()
        for f in engine.findall('q:Function', NS):
            if f.get('Type') == 'Chaser':
                for step in f.findall('q:Step', NS):
                    if step.text:
                        used_by_chasers.add(step.text)

        for func in list(engine.findall('q:Function', NS)):
            fn  = func.get('Name', '')
            fid = func.get('ID')
            if "(Setlist)" in fn and fid not in all_active_ids \
                    and fid not in used_by_chasers:
                engine.remove(func)

        # ── Write file ────────────────────────────────────────────────────────
        odir = os.path.dirname(app.current_qxw_file)
        obn  = os.path.splitext(os.path.basename(app.current_qxw_file))[0]
        m    = re.search(r'(\d+)$', obn)
        if m:
            bn = obn[:m.start()] + str(int(m.group(1)) + 1).zfill(len(m.group(1)))
        else:
            bn = f"{obn}_GIG_READY"
        nf = os.path.join(odir, bn + ".qxw")

        if os.path.exists(nf):
            ans = messagebox.askyesnocancel(
                "Exists",
                f"'{bn}.qxw' exists.\n\nYes=Overwrite  No=New file  Cancel=Abort")
            if ans is None:
                return
            if not ans:
                while os.path.exists(nf):
                    m2 = re.search(r'(\d+)$', bn)
                    bn = (bn[:m2.start()]
                          + str(int(m2.group(1)) + 1).zfill(len(m2.group(1)))
                          ) if m2 else bn + "_1"
                    nf = os.path.join(odir, bn + ".qxw")

        try:
            xb = ET.tostring(app.qxw_root, encoding="utf-8").decode("utf-8")
            with open(nf, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<!DOCTYPE Workspace>\n' + xb)
            app.current_qxw_file = nf
            t2 = THEMES[app.current_theme]
            app.lbl_qxw.config(text=os.path.basename(nf), fg=t2["lbl_green"])

            lines = [f"Saved to: {os.path.basename(nf)}\n"]
            for slot, count, lnk in slot_summaries:
                lbl = slot.cuelist_caption or f"Slot {slot.slot_index + 1}"
                ln_note = " (auto-linked)" if lnk else ""
                lines.append(f"  • {lbl}: {count} cues{ln_note}")
            messagebox.showinfo("Success", "\n".join(lines))
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed:\n{e}")

    # ──────────────────────────────────────────────────────────────────────────
    # Description / dictionary helpers (shared, unchanged from v0.6)
    # ──────────────────────────────────────────────────────────────────────────
    def load_desc_dialog(self):
        fn = filedialog.askopenfilename(
            title="Select Descriptions TXT",
            filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if fn:
            self.load_desc(fn)

    def load_desc(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            self.app.shared_descriptions.clear()
            current_id = None
            for line in lines:
                line = line.strip()
                if not line or line.startswith("ID|"):
                    continue
                parts = line.split('|')
                if len(parts) >= 3 and parts[0].isdigit():
                    current_id = parts[0].strip()
                    desc = "|".join(parts[2:]).strip()
                    desc = desc.replace(_NEWLINE_SENTINEL, "\n")
                    self.app.shared_descriptions[current_id] = desc
                elif current_id and len(parts) == 1:
                    self.app.shared_descriptions[current_id] += " " + line
            self.current_desc_file = filename
            self.lbl_desc.config(text=os.path.basename(filename))
            if self.app.qxw_root:
                self.populate_right_tree()
            self.app.dict_mgr.sync_from_shared_descriptions()
            self.app.dict_mgr.current_txt_file = filename
            self.app.dict_mgr.lbl_txt.config(text=os.path.basename(filename))
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            messagebox.showerror("Error", f"Failed to load Descriptions:\n{e}")

    def find_orphans(self):
        fd = self.app.func_detailed
        if not fd:
            return messagebox.showwarning("Notice", "Load a QXW file first.")
        used_in_steps = set()
        for det in fd.values():
            if det['contains']:
                for sid in det['contains'].split(','):
                    used_in_steps.add(sid.strip())
        orphans = []
        for fid, det in fd.items():
            if fid not in self.app.vc_buttons and fid not in used_in_steps:
                if det['name'] not in self.app.chasers:
                    orphans.append(f"[{fid}] {det['name']}")
        if not orphans:
            messagebox.showinfo("Clean", "No orphaned functions found!")
        else:
            msg = "\n".join(orphans[:25])
            if len(orphans) > 25:
                msg += f"\n...and {len(orphans) - 25} more."
            messagebox.showinfo("Orphans Found",
                                f"Disconnected functions:\n\n{msg}")

    def export_dictionary(self):
        fd = self.app.func_detailed
        if not fd:
            return messagebox.showwarning("Notice",
                                          "Load a QXW workspace first.")
        bn = (os.path.splitext(os.path.basename(self.app.current_qxw_file))[0]
              if self.app.current_qxw_file else "Untitled")
        fp = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text", "*.txt")],
            title="Export ID Dictionary",
            initialfile=f"{bn}_ID_description.txt")
        if not fp:
            return
        try:
            lines = ["ID|Name|Description"]
            for fid in sorted(fd, key=lambda x: int(x)):
                name = fd[fid]['name']
                desc = self.app.shared_descriptions.get(fid, "")
                lines.append(f"{fid}|{name}|{desc}")
            with open(fp, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
            messagebox.showinfo("Success", f"Dictionary exported to:\n{fp}")
            self.load_desc(fp)
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n{e}")

    @staticmethod
    def _assemble_pdf(pages, W, H):
        raw = "%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        offsets = []
        def add(s):
            nonlocal raw; offsets.append(len(raw)); raw += s
        def obj(n, c): return f"{n} 0 obj\n{c}\nendobj\n"
        def sobj(n, data):
            body = data.decode("latin-1")
            return obj(n,
                       f"<< /Length {len(data)} /Filter /FlateDecode >>\n"
                       f"stream\n{body}\nendstream")
        font_res = "<< /Font << /F1 3 0 R /F2 4 0 R >> >>"
        kids, po, so = [], [], []
        cid = 5
        for ps in pages:
            kids.append(f"{cid} 0 R")
            po.append(obj(cid,
                          f"<< /Type /Page /Parent 2 0 R "
                          f"/MediaBox [0 0 {W:.2f} {H:.2f}] "
                          f"/Contents {cid + 1} 0 R "
                          f"/Resources {font_res} >>"))
            so.append(sobj(cid + 1, ps))
            cid += 2
        add(obj(1, "<< /Type /Catalog /Pages 2 0 R >>"))
        add(obj(2, f"<< /Type /Pages /Kids [{' '.join(kids)}] "
                   f"/Count {len(pages)} >>"))
        add(obj(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                   "/Encoding /WinAnsiEncoding >>"))
        add(obj(4, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
                   "/Encoding /WinAnsiEncoding >>"))
        for p, s in zip(po, so):
            add(p); add(s)
        n    = cid - 1
        xoff = len(raw)
        raw += f"xref\n0 {n + 1}\n0000000000 65535 f \n"
        for o in offsets:
            raw += f"{o:010d} 00000 n \n"
        raw += f"trailer\n<< /Size {n + 1} /Root 1 0 R >>\nstartxref\n{xoff}\n%%EOF\n"
        return raw.encode("latin-1")


# ██████████████████████████████████████████████████████████████████████████████
#  TAB 2 — DICTIONARY MANAGER
# ██████████████████████████████████████████████████████████████████████████████

class DictionaryManagerTab:
    def __init__(self, parent, app: QLCSwissKnife):
        self.parent = parent
        self.app = app
        self.dict_data = {}
        self.current_txt_file = ""
        self._build_ui()

    def _build_ui(self):
        top = tk.Frame(self.parent, padx=10, pady=6)
        top.pack(fill=tk.X)

        ttk.Button(top, text="📄 Load Dictionary TXT",
                   command=self.load_txt_dialog, style="Normal.TButton").pack(side=tk.LEFT)
        self.lbl_txt = tk.Label(top, text="No dictionary", font=("Helvetica", 9, "bold"))
        self.lbl_txt.pack(side=tk.LEFT, padx=(5, 15))

        main = tk.Frame(self.parent, padx=10, pady=4)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="📖 Function ID Descriptions",
                 font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(0, 4))

        tree_f = tk.Frame(main)
        tree_f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        cols = ("ID", "Function Name", "Description")
        self.tree_ui = ttk.Treeview(tree_f, columns=cols, show="headings", selectmode="browse")
        self.tree_ui.heading("ID", text="ID"); self.tree_ui.column("ID", width=60, anchor="center")
        self.tree_ui.heading("Function Name", text="Function Name"); self.tree_ui.column("Function Name", width=250)
        self.tree_ui.heading("Description", text="Description"); self.tree_ui.column("Description", width=400)
        self.tree_ui.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Scrollbar(tree_f, orient="vertical", command=self.tree_ui.yview).pack(side=tk.LEFT, fill=tk.Y)
        self.tree_ui.bind("<<TreeviewSelect>>", self.on_item_select)

        right = tk.Frame(main)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=10)

        ef = tk.LabelFrame(right, text="Edit Description", padx=12, pady=12)
        ef.pack(fill=tk.X)
        self.lbl_edit_id = tk.Label(ef, text="ID: ---", font=("Helvetica", 11, "bold"))
        self.lbl_edit_id.pack(anchor="w")
        self.lbl_edit_name = tk.Label(ef, text="Name: ---", font=("Helvetica", 9, "italic"))
        self.lbl_edit_name.pack(anchor="w", pady=(0, 8))
        tk.Label(ef, text="Description / Notes:").pack(anchor="w")
        self.text_desc = tk.Text(ef, width=42, height=8, font=("Helvetica", 10), wrap="word")
        self.text_desc.pack(anchor="w", pady=(0, 12))
        ttk.Button(ef, text="⬆ Update In Memory", command=self.update_description,
                   style="Assign.TButton").pack(fill=tk.X, ipady=4)

        inf = tk.LabelFrame(right, text="Function Inspector", padx=10, pady=10)
        inf.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.text_info = tk.Text(inf, width=42, height=12, font=("Courier", 10), wrap="word", state=tk.DISABLED)
        self.text_info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Scrollbar(inf, orient="vertical", command=self.text_info.yview).pack(side=tk.RIGHT, fill=tk.Y)

        bottom = tk.Frame(self.parent, padx=10, pady=8)
        bottom.pack(fill=tk.X)
        ttk.Button(bottom, text="💾 SAVE & VERSION DICTIONARY",
                   command=self.save_txt, style="Save.TButton").pack(
            side=tk.RIGHT, fill=tk.X, expand=True, ipady=6)

    def on_qxw_loaded(self):
        for func in self.app.qxw_root.findall('q:Engine/q:Function', NS):
            fid = func.get('ID'); fn = func.get('Name', 'Unknown')
            if "(Auto-Clone)" in fn or "(Setlist)" in fn:
                continue
            if fid:
                existing_desc = self.app.shared_descriptions.get(fid, "")
                if fid not in self.dict_data:
                    self.dict_data[fid] = {"name": fn, "desc": existing_desc}
                else:
                    self.dict_data[fid]["name"] = fn
                    if existing_desc and not self.dict_data[fid]["desc"]:
                        self.dict_data[fid]["desc"] = existing_desc
        self.refresh_tree()

    def on_theme_changed(self):
        t = THEMES[self.app.current_theme]
        self.text_desc.configure(bg=t["tree_bg"], fg=t["tree_fg"], insertbackground=t["tree_fg"])
        self.text_info.configure(bg=t["info_bg"], fg=t["info_fg"])

    def load_txt_dialog(self):
        fn = filedialog.askopenfilename(title="Select Dictionary TXT", filetypes=[("Text", "*.txt")])
        if fn:
            self.load_txt(fn)

    def load_txt(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            self.current_txt_file = filename
            self.lbl_txt.config(text=os.path.basename(filename))
            for line in lines:
                cl = line.strip()
                if not cl or cl.startswith("ID|"):
                    continue
                parts = cl.split('|')
                if len(parts) >= 3 and parts[0].isdigit():
                    cid = parts[0].strip()
                    name = parts[1].strip()
                    desc = "|".join(parts[2:]).strip().replace(_NEWLINE_SENTINEL, "\n")
                    if cid not in self.dict_data:
                        self.dict_data[cid] = {"name": name, "desc": desc}
                    else:
                        self.dict_data[cid]["desc"] = desc
                    # Sync to shared descriptions
                    self.app.shared_descriptions[cid] = desc
            self.refresh_tree()
            # Always sync the setlist tab label + file path
            self.app.setlist_mgr.lbl_desc.config(text=os.path.basename(filename))
            self.app.setlist_mgr.current_desc_file = filename
            # Update the setlist pool view if QXW data exists
            if self.app.qxw_root:
                self.app.setlist_mgr.populate_right_tree()
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            messagebox.showerror("Error", f"Failed to load TXT:\n{e}")

    def refresh_tree(self):
        self.tree_ui.delete(*self.tree_ui.get_children())
        for fid in sorted(self.dict_data, key=lambda x: int(x)):
            d = self.dict_data[fid]
            dd = d["desc"].replace('\n', ' ')
            self.tree_ui.insert("", tk.END, iid=fid, values=(fid, d["name"], dd))

    def on_item_select(self, event):
        sel = self.tree_ui.selection()
        if not sel:
            return
        fid = sel[0]
        d = self.dict_data[fid]
        self.lbl_edit_id.config(text=f"ID: {fid}")
        self.lbl_edit_name.config(text=f"Name: {d['name']}")
        self.text_desc.delete("1.0", tk.END)
        self.text_desc.insert(tk.END, d["desc"])
        self.update_inspector(fid)

    def update_description(self):
        sel = self.tree_ui.selection()
        if not sel:
            return messagebox.showwarning("Notice", "Select an ID first.")
        fid = sel[0]
        new_desc = self.text_desc.get("1.0", tk.END).strip()
        self.dict_data[fid]["desc"] = new_desc
        self.app.shared_descriptions[fid] = new_desc
        self.refresh_tree()
        self.tree_ui.selection_set(fid)
        # Live-update the setlist pool view
        if self.app.qxw_root:
            self.app.setlist_mgr.populate_right_tree()

    def sync_from_shared_descriptions(self):
        """Called when descriptions are loaded from the Setlist tab — pull into dict_data."""
        for fid, desc in self.app.shared_descriptions.items():
            if fid in self.dict_data:
                self.dict_data[fid]["desc"] = desc
            else:
                name = self.app.func_by_id.get(fid, f"ID {fid}")
                self.dict_data[fid] = {"name": name, "desc": desc}
        self.refresh_tree()

    def update_inspector(self, f_id):
        self.text_info.config(state=tk.NORMAL)
        self.text_info.delete("1.0", tk.END)
        if not self.app.qxw_root:
            self.text_info.insert(tk.END, "Load a QXW file to inspect.")
            self.text_info.config(state=tk.DISABLED); return

        func_node = self.app.qxw_root.find(f"q:Engine/q:Function[@ID='{f_id}']", NS)
        if func_node is None:
            self.text_info.insert(tk.END, "Function not found in QXW.")
            self.text_info.config(state=tk.DISABLED); return

        ft = func_node.get('Type', 'Unknown')
        info = f"Type: {ft}\n{'=' * 35}\n\n"

        if ft == "Scene":
            fvs = func_node.findall('q:FixtureVal', NS)
            info += f"Active Fixtures: {len(fvs)}\n{'-' * 35}\n"
            for fv in fvs:
                fix_id = fv.get('ID')
                fi = self.app.fixture_map.get(fix_id, {})
                fn = fi.get("name", f"Unknown {fix_id}")
                info += f"[{fn}] (U{fi.get('universe', '?')}.Ch{fi.get('address', '?')})\n"
                info += f"   Groups: {fi.get('groups', 'None')}\n\n"
        elif ft in ("Collection", "Chaser"):
            steps = func_node.findall('q:Step', NS)
            info += f"Steps: {len(steps)}\n{'-' * 35}\n"
            for i, s in enumerate(steps):
                tn = self.dict_data.get(s.text, {}).get("name", f"ID {s.text}")
                info += f"{i + 1}. {tn}\n"
        elif ft == "RGBMatrix":
            gi = func_node.find('q:FixtureGroup', NS)
            gn = self.app.group_map.get(gi.text, f"Group {gi.text}") if gi is not None and gi.text else "Unknown"
            algo = func_node.find('q:Algorithm', NS)
            info += f"Group: {gn}\nEffect: {algo.text if algo is not None else 'Unknown'}\n"
        elif ft == "EFX":
            algo = func_node.find('q:Algorithm', NS)
            info += f"Pattern: {algo.text if algo is not None else 'Unknown'}\n"
            fxs = func_node.findall('q:Fixture', NS)
            info += f"Fixtures: {len(fxs)}\n"
            for fx in fxs:
                fxi = fx.find('q:ID', NS)
                if fxi is not None and fxi.text:
                    fi2 = self.app.fixture_map.get(fxi.text, {})
                    info += f"  - {fi2.get('name', f'Fixture {fxi.text}')}\n"
        elif ft == "Audio":
            src = func_node.find('q:Source', NS)
            info += f"File: {src.text if src is not None else 'Unknown'}\n"
        else:
            info += "No detailed inspection for this type."

        self.text_info.insert(tk.END, info)
        self.text_info.config(state=tk.DISABLED)

    def save_txt(self):
        if not self.dict_data:
            return messagebox.showwarning("Warning", "Dictionary is empty!")
        bn = "ID_description"
        odir = os.path.expanduser("~")
        if self.current_txt_file:
            odir = os.path.dirname(self.current_txt_file)
            obn = os.path.splitext(os.path.basename(self.current_txt_file))[0]
            m = re.search(r'_v(\d+)$', obn)
            if m:
                bn = obn[:m.start()] + f"_v{int(m.group(1)) + 1}"
            else:
                bn = f"{obn}_v2"
        fp = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text", "*.txt")],
            title="Save Dictionary", initialfile=f"{bn}.txt", initialdir=odir)
        if not fp:
            return
        try:
            lines = ["ID|Name|Description"]
            for fid in sorted(self.dict_data, key=lambda x: int(x)):
                d = self.dict_data[fid]
                sd = d['desc'].replace('\n', _NEWLINE_SENTINEL)
                lines.append(f"{fid}|{d['name']}|{sd}")
            with open(fp, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
            self.current_txt_file = fp
            self.lbl_txt.config(text=os.path.basename(fp))
            # Sync all descriptions to shared pool
            for fid, d in self.dict_data.items():
                self.app.shared_descriptions[fid] = d['desc']
            # Update setlist view
            self.app.setlist_mgr.lbl_desc.config(text=os.path.basename(fp))
            self.app.setlist_mgr.current_desc_file = fp
            if self.app.qxw_root:
                self.app.setlist_mgr.populate_right_tree()
            messagebox.showinfo("Success", f"Dictionary saved to:\n{fp}")
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            messagebox.showerror("Error", f"Save failed:\n{e}")


# ██████████████████████████████████████████████████████████████████████████████
#  TAB 3 — SETUP CHECKLIST
# ██████████████████████████████████████████████████████████████████████████████

class SetupChecklistTab:
    def __init__(self, parent, app: QLCSwissKnife):
        self.parent = parent
        self.app = app
        self.fixture_data = []
        self.model_colors = {}
        self.color_palette = ["#00e5ff", "#ff007f", "#39ff14", "#ffff00",
                              "#ff8c00", "#b026ff", "#ff3333"]
        self._resize_timer = None
        self._build_ui()

    def _build_ui(self):
        top = tk.Frame(self.parent, padx=10, pady=6)
        top.pack(fill=tk.X)

        tk.Label(top, text="Show:", font=("Helvetica", 9)).pack(side=tk.LEFT)
        self.entry_show = tk.Entry(top, width=20, font=("Helvetica", 10))
        self.entry_show.pack(side=tk.LEFT, padx=(4, 12))
        self.entry_show.insert(0, "Untitled Show")

        tk.Label(top, text="Date:", font=("Helvetica", 9)).pack(side=tk.LEFT)
        self.entry_date = tk.Entry(top, width=11, font=("Helvetica", 10))
        self.entry_date.pack(side=tk.LEFT, padx=(4, 12))
        self.entry_date.insert(0, datetime.date.today().strftime("%Y-%m-%d"))

        self.unit_var = tk.StringVar(value="Metric (m)")
        ttk.Combobox(top, textvariable=self.unit_var,
                     values=["Metric (m)", "Imperial (ft/in)"],
                     state="readonly", width=14).pack(side=tk.RIGHT, padx=4)
        tk.Label(top, text="Units:", font=("Helvetica", 9)).pack(side=tk.RIGHT)

        self.paper_var = tk.StringVar(value="A3 Landscape")
        ttk.Combobox(top, textvariable=self.paper_var,
                     values=["A3 Landscape", "A4 Portrait", "A4 Landscape",
                             "US Letter Portrait", "US Letter Landscape"],
                     state="readonly", width=18).pack(side=tk.RIGHT, padx=4)
        tk.Label(top, text="Paper:", font=("Helvetica", 9)).pack(side=tk.RIGHT)

        # Sub-notebook for data vs plot
        self.sub_nb = ttk.Notebook(self.parent)
        self.sub_nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        self.sub_nb.bind("<<NotebookTabChanged>>", self._on_sub_tab)

        # Data tab
        self.tab_data = tk.Frame(self.sub_nb)
        self.sub_nb.add(self.tab_data, text="  📋 Patch List  ")

        cols = ("Name", "Model", "Patch", "Groups", "Position", "Rotation")
        self.tree_ui = ttk.Treeview(self.tab_data, columns=cols, show="headings", selectmode="browse")
        widths = [160, 200, 100, 160, 220, 180]
        for c, w in zip(cols, widths):
            self.tree_ui.heading(c, text=c, command=lambda cc=c: self.sort_tree(cc, False))
            self.tree_ui.column(c, width=w, anchor="center" if c == "Patch" else "w")
        self.tree_ui.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Scrollbar(self.tab_data, orient="vertical",
                      command=self.tree_ui.yview).pack(side=tk.LEFT, fill=tk.Y)

        # Plot tab
        self.tab_plot = tk.Frame(self.sub_nb)
        self.sub_nb.add(self.tab_plot, text="  🗺️ Blueprint  ")
        self.canvas = tk.Canvas(self.tab_plot)
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=4)

        # Bottom
        bottom = tk.Frame(self.parent, padx=10, pady=8)
        bottom.pack(fill=tk.X)
        ttk.Button(bottom, text="🖼️ EXPORT BLUEPRINT PDF",
                   command=self.export_plot, style="Save.TButton").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4), ipady=6)
        ttk.Button(bottom, text="📄 EXPORT TEXT CHECKLIST",
                   command=self.export_txt, style="Save.TButton").pack(
            side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0), ipady=6)

    def on_qxw_loaded(self):
        self.fixture_data.clear()
        self.model_colors.clear()
        qr = self.app.qxw_root

        groups_map = {}
        for g in qr.findall('q:Engine/q:FixtureGroup', NS):
            gn = g.find('q:Name', NS)
            gn = (gn.text or "").strip() if gn is not None else ""
            if not gn:
                gn = "Unknown"
            for h in g.findall('q:Head', NS):
                fid = h.get('Fixture')
                if fid:
                    groups_map.setdefault(fid, []).append(gn)

        monitor = {}
        for fx in qr.findall('.//q:Monitor/q:FxItem', NS):
            fid = fx.get('ID')
            monitor[fid] = {
                "x": float(fx.get('XPos', '0')), "y": float(fx.get('YPos', '0')),
                "z": float(fx.get('ZPos', '0')),
                "xr": fx.get('XRot', '0'), "yr": fx.get('YRot', '0'), "zr": fx.get('ZRot', '0'),
                "in_3d": True
            }

        for fix in qr.findall('q:Engine/q:Fixture', NS):
            id_n = fix.find('q:ID', NS)
            fid = id_n.text if id_n is not None else None
            name = fix.find('q:Name', NS)
            name = (name.text or "").strip() if name is not None else ""
            if not name:
                name = f"Fixture {fid}"
            mfg = fix.find('q:Manufacturer', NS)
            mfg = mfg.text if mfg is not None else "Unknown"
            model = fix.find('q:Model', NS)
            model = model.text if model is not None else "Unknown"
            mode = fix.find('q:Mode', NS)
            mode = mode.text if mode is not None else "Default"

            if model not in self.model_colors:
                self.model_colors[model] = self.color_palette[len(self.model_colors) % len(self.color_palette)]

            un = fix.find('q:Universe', NS)
            ad = fix.find('q:Address', NS)
            universe = int(un.text) + 1 if un is not None else 1
            address = int(ad.text) + 1 if ad is not None else 1

            md = monitor.get(fid, {"x": 0, "y": 0, "z": 0, "xr": "0", "yr": "0", "zr": "0", "in_3d": False})

            self.fixture_data.append({
                "name": name, "model": f"{mfg} {model}", "mode": mode,
                "patch": f"U{universe}.{address:03d}",
                "address_sort": universe * 1000 + address,
                "groups": ", ".join(groups_map.get(fid, [])) or "None",
                "color": self.model_colors[model],
                **{k: md[k] for k in ("x", "y", "z", "xr", "yr", "zr", "in_3d")}
            })

        self.refresh_tree()

    def on_theme_changed(self):
        t = THEMES[self.app.current_theme]
        self.canvas.configure(bg=t["canvas_bg"], highlightthickness=0)
        for e in (self.entry_show, self.entry_date):
            e.configure(bg=t["tree_bg"], fg=t["tree_fg"], insertbackground=t["tree_fg"],
                        relief="flat", highlightbackground=t["border"])
        if self.fixture_data:
            self.draw_plots()

    def on_tab_activated(self):
        if self.fixture_data:
            self.parent.update_idletasks()
            self.draw_plots()

    def _on_sub_tab(self, event):
        idx = self.sub_nb.index(self.sub_nb.select())
        if idx == 1 and self.fixture_data:
            self.parent.update_idletasks()
            self.draw_plots()

    def format_coord(self, mm):
        if self.unit_var.get() == "Imperial (ft/in)":
            ti = mm * 0.0393701
            ft = int(ti // 12); inch = int(round(ti % 12))
            return f"{ft}' {inch}\"" if ft else f'{inch}"'
        return f"{mm / 1000:.2f}m"

    def format_pos(self, x, y, z):
        return f"L/R: {self.format_coord(x)} | D: {self.format_coord(y)} | H: {self.format_coord(z)}"

    def format_rot(self, xr, yr, zr):
        return f"T:{xr}° P:{yr}° R:{zr}°"

    def refresh_tree(self):
        self.tree_ui.delete(*self.tree_ui.get_children())
        self.fixture_data.sort(key=lambda x: x["address_sort"])
        for d in self.fixture_data:
            ps = self.format_pos(d["x"], d["y"], d["z"]) if d["in_3d"] else "Not in 3D"
            rs = self.format_rot(d["xr"], d["yr"], d["zr"]) if d["in_3d"] else "N/A"
            self.tree_ui.insert("", tk.END, values=(
                d["name"], f"{d['model']} - {d['mode']}", d["patch"], d["groups"], ps, rs))

    def sort_tree(self, col, rev):
        items = [(self.tree_ui.set(k, col), k) for k in self.tree_ui.get_children('')]
        if col == "Patch":
            def key(t):
                try:
                    p = t[0].replace('U', '').split('.')
                    return int(p[0]), int(p[1])
                except (ValueError, IndexError):
                    return 9999, 9999
            items.sort(key=key, reverse=rev)
        else:
            items.sort(reverse=rev)
        for i, (_, k) in enumerate(items):
            self.tree_ui.move(k, '', i)
        self.tree_ui.heading(col, command=lambda: self.sort_tree(col, not rev))

    def draw_plots(self):
        if not self.fixture_data:
            return
        t = THEMES[self.app.current_theme]
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw <= 1: cw = 1200
        if ch <= 1: ch = 500
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, cw, ch, fill=t["canvas_bg"], outline="")

        xv = [f["x"] for f in self.fixture_data if f["in_3d"]]
        yv = [f["y"] for f in self.fixture_data if f["in_3d"]]
        zv = [f["z"] for f in self.fixture_data if f["in_3d"]]
        if not xv:
            return

        mn_x, mx_x = min(xv), max(xv)
        mn_y, mx_y = min(yv), max(yv)
        mn_z, mx_z = min(zv), max(zv)
        pad = 80
        rx = mx_x - mn_x or 1; ry = mx_y - mn_y or 1; rz = mx_z - mn_z or 1
        sh = ch / 2

        # QLC+ Monitor axes: X=width, Y=height (ceiling↑), Z=depth (audience↓ downstage)
        # TOP VIEW   = X vs Z: upstage(low Z) at top, audience(high Z) at bottom
        # FRONT VIEW = X vs Y: ceiling(high Y) at top, floor(low Y) at bottom
        self._draw_grid(cw, sh, rx, rz, pad, t, "TOP VIEW — Width vs Depth", 0, is_top=True)
        self._draw_grid(cw, sh, rx, ry, pad, t, "FRONT VIEW — Width vs Height", sh, is_top=False)

        r = 10
        for f in self.fixture_data:
            if not f["in_3d"]:
                continue
            nx = pad + ((f["x"] - mn_x) / rx) * (cw - 2 * pad)

            # TOP VIEW: low Z = upstage → top of view; high Z = audience → bottom
            ny_t = pad + ((mx_z - f["z"]) / rz) * (sh - 2 * pad)
            self.canvas.create_oval(nx - r, ny_t - r, nx + r, ny_t + r,
                                    fill=f["color"], outline=t["fg"])
            self.canvas.create_text(nx, ny_t + 22,
                                    text=f"{f['name']}\n[{f['patch']}]",
                                    fill=t["fg"], font=("Helvetica", 7, "bold"), justify="center")

            # FRONT VIEW: high Y = ceiling → top of view; low Y = floor → bottom
            ny_f = sh + pad + ((mx_y - f["y"]) / ry) * (sh - 2 * pad)
            self.canvas.create_oval(nx - r, ny_f - r, nx + r, ny_f + r,
                                    fill=f["color"], outline=t["fg"])
            self.canvas.create_text(nx, ny_f + 22,
                                    text=f"{f['name']}\n[{f['patch']}]",
                                    fill=t["fg"], font=("Helvetica", 7, "bold"), justify="center")

    def _draw_grid(self, cw, sh, rw, rh, pad, t, title, y_off, is_top=False):
        steps = 10
        for i in range(steps + 1):
            x = pad + i * (cw - 2 * pad) / steps
            self.canvas.create_line(x, y_off + pad, x, y_off + sh - pad,
                                    fill=t["grid_line"], dash=(2, 4))
            y = y_off + pad + i * (sh - 2 * pad) / steps
            self.canvas.create_line(pad, y, cw - pad, y,
                                    fill=t["grid_line"], dash=(2, 4))
        self.canvas.create_rectangle(pad, y_off + pad, cw - pad, y_off + sh - pad,
                                     outline=t["stage_lines"], width=2)
        self.canvas.create_text(pad, y_off + pad - 16, text=title,
                                fill=t["fg"], font=("Helvetica", 11, "bold"), anchor="w")

        # Audience / Backstage labels on the TOP VIEW only
        if is_top:
            band_h = 18
            label_x = cw // 2
            # BACKSTAGE banner — top of top-view box (upstage side)
            self.canvas.create_rectangle(pad, y_off + pad, cw - pad, y_off + pad + band_h,
                                         fill=t["surface"], outline="")
            self.canvas.create_text(label_x, y_off + pad + band_h // 2,
                                    text="▲  BACKSTAGE / UPSTAGE  ▲",
                                    fill=t["lbl_gray"], font=("Helvetica", 8, "italic"),
                                    anchor="center")
            # AUDIENCE banner — bottom of top-view box (downstage side)
            self.canvas.create_rectangle(pad, y_off + sh - pad - band_h, cw - pad, y_off + sh - pad,
                                         fill=t["accent2"] if "accent2" in t else t["surface"],
                                         outline="")
            self.canvas.create_text(label_x, y_off + sh - pad - band_h // 2,
                                    text="▼  AUDIENCE / DOWNSTAGE  ▼",
                                    fill=t["bg"], font=("Helvetica", 8, "bold"),
                                    anchor="center")

        # Legend
        lx = cw - pad - 160
        ly = y_off + pad + 15
        self.canvas.create_rectangle(lx - 10, ly - 10, cw - pad - 5,
                                     ly + len(self.model_colors) * 20 + 5,
                                     fill=t["bg"], outline=t["stage_lines"])
        for i, (model, color) in enumerate(self.model_colors.items()):
            self.canvas.create_oval(lx, ly + i * 20, lx + 10, ly + 10 + i * 20,
                                    fill=color, outline=t["fg"])
            trunc = model[:22] + ".." if len(model) > 22 else model
            self.canvas.create_text(lx + 18, ly + 5 + i * 20, text=trunc,
                                    fill=t["fg"], anchor="w", font=("Helvetica", 8))

    def export_txt(self):
        if not self.fixture_data:
            return messagebox.showwarning("Warning", "No fixtures to export!")
        bn = f"{os.path.splitext(os.path.basename(self.app.current_qxw_file))[0]}_Patch" if self.app.current_qxw_file else "Patch_List"
        fp = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")],
                                          title="Export Checklist", initialfile=f"{bn}.txt")
        if not fp:
            return
        try:
            self.fixture_data.sort(key=lambda x: x["address_sort"])
            lines = ["=" * 80, f" PATCH LIST: {os.path.basename(self.app.current_qxw_file)}",
                     f" Units: {self.unit_var.get()}", "=" * 80, ""]
            for f in self.fixture_data:
                ps = self.format_pos(f["x"], f["y"], f["z"]) if f["in_3d"] else "Not in 3D"
                lines.extend([f"☐ {f['patch']}", f"   Name:  {f['name']}  |  Groups: {f['groups']}",
                              f"   Model: {f['model']} ({f['mode']})", f"   Pos:   {ps}", "-" * 80])
            with open(fp, 'w', encoding='utf-8') as file:
                file.write("\n".join(lines))
            messagebox.showinfo("Success", f"Exported to:\n{fp}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n{e}")

    def export_plot(self):
        if not self.fixture_data:
            return messagebox.showwarning("Warning", "No fixtures!")
        bn = f"{os.path.splitext(os.path.basename(self.app.current_qxw_file))[0]}_Blueprint" if self.app.current_qxw_file else "Blueprint"
        fp = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                          title="Export Blueprint PDF", initialfile=f"{bn}.pdf")
        if not fp:
            return
        try:
            paper_sizes = {"A3 Landscape": (1190, 841), "A4 Portrait": (595, 842),
                           "A4 Landscape": (842, 595), "US Letter Portrait": (612, 792),
                           "US Letter Landscape": (792, 612)}
            W, H = paper_sizes.get(self.paper_var.get(), (1190, 841))
            pdf = self._build_blueprint_pdf(float(W), float(H))
            if pdf:
                with open(fp, "wb") as f:
                    f.write(pdf)
                messagebox.showinfo("Success", f"Blueprint PDF exported:\n{fp}")
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            messagebox.showerror("Error", f"Export failed:\n{e}")

    def _build_blueprint_pdf(self, W, H):
        """Minimal single-page blueprint PDF for fixture positions."""
        xv = [f["x"] for f in self.fixture_data if f["in_3d"]]
        yv = [f["y"] for f in self.fixture_data if f["in_3d"]]
        zv = [f["z"] for f in self.fixture_data if f["in_3d"]]
        if not xv:
            return None

        mn_x, mx_x = min(xv), max(xv)
        mn_y, mx_y = min(yv), max(yv)
        mn_z, mx_z = min(zv), max(zv)
        rx = mx_x - mn_x or 1; ry = mx_y - mn_y or 1; rz = mx_z - mn_z or 1

        ln = []
        header_col = (0.12, 0.12, 0.18)
        show_name = self.entry_show.get().strip() or "Untitled"
        doc_date = self.entry_date.get().strip() or datetime.date.today().strftime("%Y-%m-%d")
        TITLE_H = 36
        pad, pad_r, pad_tb = 72, 52, 28
        sec_h = (H - TITLE_H) / 2.0

        def fc(r, g, b): ln.append(f"{r:.4f} {g:.4f} {b:.4f} rg")
        def sc(r, g, b): ln.append(f"{r:.4f} {g:.4f} {b:.4f} RG")
        def lw(w): ln.append(f"{w} w")
        def rfill(x, y, w, h, col): fc(*col); ln.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")
        def seg(x1, y1, x2, y2, col, wd=0.5, dsh=None):
            lw(wd); sc(*col)
            ln.append(f"[{dsh[0]} {dsh[1]}] 0 d" if dsh else "[] 0 d")
            ln.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")
        def circ(cx, cy, r, fcol, scol):
            k = 0.5523 * r; fc(*fcol); sc(*scol); lw(0.6)
            ln.append(f"{cx:.2f} {cy + r:.2f} m "
                      f"{cx + k:.2f} {cy + r:.2f} {cx + r:.2f} {cy + k:.2f} {cx + r:.2f} {cy:.2f} c "
                      f"{cx + r:.2f} {cy - k:.2f} {cx + k:.2f} {cy - r:.2f} {cx:.2f} {cy - r:.2f} c "
                      f"{cx - k:.2f} {cy - r:.2f} {cx - r:.2f} {cy - k:.2f} {cx - r:.2f} {cy:.2f} c "
                      f"{cx - r:.2f} {cy + k:.2f} {cx - k:.2f} {cy + r:.2f} {cx:.2f} {cy + r:.2f} c B")
        def txt(x, y, s, sz=8, bold=False):
            s = str(s).encode('latin-1', errors='replace').decode('latin-1')
            s = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ln.append(f"BT {'/F2' if bold else '/F1'} {sz} Tf {x:.2f} {y:.2f} Td ({s}) Tj ET")
        def txt_c(cx, y, s, sz=8, bold=False):
            txt(cx - len(str(s)) * sz * 0.28, y, str(s), sz, bold)

        def fy(yc): return H - TITLE_H - yc

        # Title
        rfill(0, H - TITLE_H, W, TITLE_H, header_col)
        ln.append("1 1 1 rg")
        txt(10, H - TITLE_H + 14, f"SHOW: {show_name}", sz=14, bold=True)
        txt_c(W / 2, H - TITLE_H + 14, "MASTER BLUEPRINT", sz=9, bold=True)
        ln.append("0.75 0.85 1.0 rg")
        txt(W - 200, H - TITLE_H + 14, f"Date: {doc_date}", sz=8)

        bg = (1.0, 1.0, 1.0)
        grd = (0.9, 0.9, 0.9)
        stg = (0.75, 0.78, 0.82)
        fg = (0.0, 0.0, 0.0)

        # QLC+ Monitor axes: X=width, Y=height (ceiling↑), Z=depth (audience↓ downstage)
        # TOP VIEW   = X vs Z: upstage (low Z) at top, audience (high Z) at bottom
        # FRONT VIEW = X vs Y: ceiling (high Y) at top, floor (low Y) at bottom
        # Draw two sections
        for sec_idx, (mn_v, mx_v, rv, v_axis, title) in enumerate([
            (mn_z, mx_z, rz, "z", "TOP VIEW (Width vs Depth)"),
            (mn_y, mx_y, ry, "y", "FRONT VIEW (Width vs Height)")
        ]):
            y_off = sec_idx * sec_h
            rfill(0, fy(y_off + sec_h), W, sec_h, bg)
            pw = W - pad - pad_r
            ph = sec_h - 2 * pad_tb
            steps = 10
            for i in range(steps + 1):
                frac = i / steps
                gx = pad + frac * pw
                seg(gx, fy(y_off + pad_tb), gx, fy(y_off + sec_h - pad_tb), grd, 0.35, (3, 4))
                gy = y_off + pad_tb + frac * ph
                seg(pad, fy(gy), W - pad_r, fy(gy), grd, 0.35, (3, 4))
            # Box
            sc(*stg); lw(1.5); ln.append(f"{pad:.2f} {fy(y_off + sec_h - pad_tb):.2f} {pw:.2f} {ph:.2f} re S")
            txt(pad, fy(y_off + pad_tb) + 8, title, sz=10, bold=True)

            # Dots
            r_dot = 6
            for f in self.fixture_data:
                if not f["in_3d"]:
                    continue
                fc_col = hex_to_01(f["color"])
                nx = pad + ((f["x"] - mn_x) / rx) * pw
                val = f[v_axis]
                # Both views: high value → top of box (frac_v=0), low value → bottom (frac_v=1)
                # TOP VIEW:   high Z = audience/downstage → bottom ✓  low Z = upstage → top ✓
                # FRONT VIEW: high Y = ceiling → top ✓  low Y = floor → bottom ✓
                frac_v = (mx_v - val) / rv if rv else 0.5
                ny = y_off + pad_tb + frac_v * ph
                circ(nx, fy(ny), r_dot, fc_col, fg)
                txt_c(nx, fy(ny) - r_dot - 9, f["name"], sz=5)
                txt_c(nx, fy(ny) - r_dot - 15, f"[{f['patch']}]", sz=5)

            # Audience / Backstage labels on the TOP VIEW only (sec_idx == 0)
            if sec_idx == 0:
                band_h = 10
                pw2 = W - pad - pad_r
                # bottom band = audience / downstage
                label_y_bot = fy(y_off + sec_h - pad_tb)
                rfill(pad, label_y_bot, pw2, band_h, (0.85, 0.72, 0.90))
                fc(0.2, 0.05, 0.3)
                txt_c(pad + pw2 / 2, label_y_bot + 2, "AUDIENCE / DOWNSTAGE", sz=6)
                # top band = upstage / backstage
                label_y_top = fy(y_off + pad_tb)
                rfill(pad, label_y_top - band_h, pw2, band_h, (0.88, 0.88, 0.92))
                fc(0.25, 0.25, 0.35)
                txt_c(pad + pw2 / 2, label_y_top - band_h + 2, "UPSTAGE / BACKSTAGE", sz=6)

        # Divider
        seg(0, fy(sec_h), W, fy(sec_h), stg, 2.0)

        stream = zlib.compress("\n".join(ln).encode("latin-1"))
        return SetlistManagerTab._assemble_pdf([stream], W, H)


# ██████████████████████████████████████████████████████████████████████████████
#  TAB 4 — TRIGGER MANAGER
# ██████████████████████████████████████████████████████████████████████████████

class TriggerManagerTab:
    def __init__(self, parent, app: QLCSwissKnife):
        self.parent = parent
        self.app = app
        self.trigger_items = {}
        self._build_ui()

    def _build_ui(self):
        top = tk.Frame(self.parent, padx=10, pady=6)
        top.pack(fill=tk.X)

        tk.Label(top, text="🎛 Virtual Console Triggers (Buttons, Cue Lists, Sliders & Knobs)",
                 font=("Helvetica", 10, "bold")).pack(side=tk.LEFT)

        ttk.Button(top, text="⚠ Find Duplicate Keys",
                   command=self.find_duplicate_keys, style="Normal.TButton").pack(side=tk.RIGHT, padx=4)

        self.show_assigned_var = tk.BooleanVar(value=False)
        chk_trig = ttk.Checkbutton(top, text="Assigned Only",
                        variable=self.show_assigned_var,
                        command=self.refresh_tree)
        chk_trig.pack(side=tk.RIGHT, padx=8)
        ToolTip(chk_trig,
                "When checked, hides VC widgets that have no keyboard key "
                "or MIDI input assigned.\n\n"
                "Useful to focus only on widgets that already have hardware triggers.")

        main = tk.Frame(self.parent, padx=10, pady=4)
        main.pack(fill=tk.BOTH, expand=True)

        cols = ("Widget Type", "Caption", "Target Function", "Key", "MIDI Universe", "MIDI Channel")
        self.tree_ui = ttk.Treeview(main, columns=cols, show="headings", selectmode="browse")
        widths = [110, 220, 240, 80, 90, 90]
        for c, w in zip(cols, widths):
            self.tree_ui.heading(c, text=c)
            self.tree_ui.column(c, width=w, anchor="center" if "MIDI" in c or c == "Key" else "w")
        self.tree_ui.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Scrollbar(main, orient="vertical", command=self.tree_ui.yview).pack(side=tk.LEFT, fill=tk.Y)
        self.tree_ui.bind("<<TreeviewSelect>>", self.on_item_select)

        ef = tk.LabelFrame(main, text="Edit Trigger", padx=12, pady=12)
        ef.pack(side=tk.RIGHT, fill=tk.Y, padx=10)

        tk.Label(ef, text="Keyboard Key:").pack(anchor="w")
        self.var_key = tk.StringVar()
        ttk.Entry(ef, textvariable=self.var_key, width=15).pack(anchor="w", pady=(0, 8))

        tk.Label(ef, text="Ext. Input Universe:").pack(anchor="w")
        self.var_uni = tk.StringVar()
        ttk.Entry(ef, textvariable=self.var_uni, width=15).pack(anchor="w", pady=(0, 8))

        tk.Label(ef, text="Ext. Input Channel:").pack(anchor="w")
        self.var_ch = tk.StringVar()
        ttk.Entry(ef, textvariable=self.var_ch, width=15).pack(anchor="w", pady=(0, 16))

        tk.Label(ef, text="* Blank = remove trigger", font=("Helvetica", 8, "italic")).pack(anchor="w", pady=(0, 8))

        ttk.Button(ef, text="⬆ Update", command=self.update_trigger,
                   style="Assign.TButton").pack(fill=tk.X, ipady=4)

        bottom = tk.Frame(self.parent, padx=10, pady=8)
        bottom.pack(fill=tk.X)
        ttk.Button(bottom, text="💾 SAVE EDITED TRIGGERS",
                   command=self.save_qxw, style="Save.TButton").pack(
            side=tk.RIGHT, fill=tk.X, expand=True, ipady=6)

    def on_qxw_loaded(self):
        self.trigger_items.clear()
        vc_root = self.app.qxw_root.find('q:VirtualConsole', NS)
        if vc_root is not None:
            self._parse_triggers(vc_root)
        self.refresh_tree()

    def on_theme_changed(self):
        pass

    def _parse_triggers(self, node):
        tag = node.tag.replace(f"{{{QLC_NS_URI}}}", "")

        if tag == "Button":
            wid = node.get('ID')
            cap = node.get('Caption', 'Unnamed').replace('\n', ' ').strip()
            fn = node.find('q:Function', NS)
            fid = fn.get('ID') if fn is not None else None
            if fid and fid not in ("4294967295", "-1"):
                fname = self.app.func_by_id.get(fid, f"ID {fid}")
                kn = node.find('q:Key', NS)
                inp = node.find('q:Input', NS)
                self.trigger_items[f"btn_{wid}"] = {
                    "type": "Button", "caption": cap, "func": fname,
                    "key": kn.text if kn is not None and kn.text else "",
                    "uni": inp.get('Universe', '') if inp is not None else "",
                    "ch": inp.get('Channel', '') if inp is not None else "",
                    "xml_parent": node}

        elif tag == "CueList":
            wid = node.get('ID')
            cap = node.get('Caption', 'Unnamed CueList').replace('\n', ' ').strip()
            cn = node.find('q:Chaser', NS)
            fid = cn.text if cn is not None else None
            fname = self.app.func_by_id.get(fid, f"ID {fid}") if fid and fid not in ("4294967295", "-1") else "Empty"
            for tt in ('Next', 'Previous', 'Stop'):
                tn = node.find(f'q:{tt}', NS)
                if tn is not None:
                    kn = tn.find('q:Key', NS)
                    inp = tn.find('q:Input', NS)
                    self.trigger_items[f"cl_{wid}_{tt}"] = {
                        "type": f"CueList ({tt})", "caption": cap, "func": fname,
                        "key": kn.text if kn is not None and kn.text else "",
                        "uni": inp.get('Universe', '') if inp is not None else "",
                        "ch": inp.get('Channel', '') if inp is not None else "",
                        "xml_parent": tn}

        elif tag in ("Slider", "Knob", "SpeedDial"):
            wid = node.get('ID')
            cap = node.get('Caption', f'Unnamed {tag}').replace('\n', ' ').strip()
            fn = node.find('q:Function', NS)
            fid = fn.get('ID') if fn is not None else None
            if fid and fid not in ("4294967295", "-1"):
                fname = self.app.func_by_id.get(fid, f"ID {fid}")
            else:
                fname = f"{tag} (Level)"
            inp = node.find('q:Input', NS)
            has_inp = inp is not None and inp.get('Universe', '')
            if (fid and fid not in ("4294967295", "-1")) or has_inp:
                self.trigger_items[f"{tag.lower()}_{wid}"] = {
                    "type": tag, "caption": cap, "func": fname,
                    "key": "",
                    "uni": inp.get('Universe', '') if inp is not None else "",
                    "ch": inp.get('Channel', '') if inp is not None else "",
                    "xml_parent": node}

        for child in node:
            self._parse_triggers(child)

    def refresh_tree(self):
        self.tree_ui.delete(*self.tree_ui.get_children())
        filt = self.show_assigned_var.get()
        for uid, d in self.trigger_items.items():
            has = bool(d["key"] or (d["uni"] and d["ch"]))
            if filt and not has:
                continue
            self.tree_ui.insert("", tk.END, iid=uid, values=(
                d["type"], d["caption"], d["func"], d["key"], d["uni"], d["ch"]))

    def on_item_select(self, event):
        sel = self.tree_ui.selection()
        if not sel:
            return
        d = self.trigger_items[sel[0]]
        self.var_key.set(d["key"]); self.var_uni.set(d["uni"]); self.var_ch.set(d["ch"])

    def update_trigger(self):
        sel = self.tree_ui.selection()
        if not sel:
            return messagebox.showwarning("Notice", "Select a trigger first.")
        uid = sel[0]
        d = self.trigger_items[uid]
        pn = d["xml_parent"]
        nk = self.var_key.get().strip()
        nu = self.var_uni.get().strip()
        nc = self.var_ch.get().strip()

        kn = pn.find('q:Key', NS)
        if nk:
            if kn is None:
                kn = ET.SubElement(pn, f"{{{QLC_NS_URI}}}Key")
            kn.text = nk
        elif kn is not None:
            pn.remove(kn)

        inp = pn.find('q:Input', NS)
        if nu and nc:
            if inp is None:
                inp = ET.SubElement(pn, f"{{{QLC_NS_URI}}}Input", {'ID': '0'})
            inp.set('Universe', nu); inp.set('Channel', nc)
        elif inp is not None:
            pn.remove(inp)

        d["key"] = nk; d["uni"] = nu; d["ch"] = nc
        self.refresh_tree()
        if self.tree_ui.exists(uid):
            self.tree_ui.selection_set(uid)
        messagebox.showinfo("Updated", f"Trigger for '{d['caption']}' updated. Don't forget to SAVE!")

    def find_duplicate_keys(self):
        if not self.trigger_items:
            return messagebox.showwarning("Notice", "Load a QXW first.")
        km = {}
        for d in self.trigger_items.values():
            if d["key"]:
                km.setdefault(d["key"], []).append(f"{d['caption']} ({d['type']})")
        dupes = {k: v for k, v in km.items() if len(v) > 1}
        if not dupes:
            messagebox.showinfo("All Clear", "No duplicate key bindings found!")
        else:
            lines = []
            for key, ws in dupes.items():
                lines.append(f"Key '{key}':")
                for w in ws:
                    lines.append(f"   - {w}")
                lines.append("")
            messagebox.showwarning("Duplicates", "\n".join(lines[:30]))

    def save_qxw(self):
        if not self.app.qxw_root:
            return messagebox.showwarning("Warning", "No QXW loaded!")
        odir = os.path.dirname(self.app.current_qxw_file)
        obn = os.path.splitext(os.path.basename(self.app.current_qxw_file))[0]
        m = re.search(r'_TRIGGERS_EDITED(?:_(\d+))?$', obn)
        if m:
            bn = obn[:m.start()] + f"_TRIGGERS_EDITED_{int(m.group(1) or 1) + 1}"
        else:
            bn = f"{obn}_TRIGGERS_EDITED"
        nf = os.path.join(odir, f"{bn}.qxw")
        try:
            xb = ET.tostring(self.app.qxw_root, encoding="utf-8").decode("utf-8")
            with open(nf, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE Workspace>\n' + xb)
            self.app.current_qxw_file = nf
            t = THEMES[self.app.current_theme]
            self.app.lbl_qxw.config(text=os.path.basename(nf), fg=t["lbl_green"])
            messagebox.showinfo("Success", f"Triggers saved to:\n{os.path.basename(nf)}")
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            messagebox.showerror("Error", f"Save failed:\n{e}")


# ██████████████████████████████████████████████████████████████████████████████
#  TAB 5 — FIXTURE CONFIGURATOR
# ██████████████████████████████████████████████████████████████████████████████

class FixtureConfiguratorTab:
    """
    Stage-rig designer and QXW generator.

    Workflow:
      1. Load one or more .qxf fixture definition files.
      2. Add fixture instances to the rig, naming them and setting stage roles.
      3. Drag fixtures on the top-down stage canvas to set their X/Z position.
      4. Configure Universe / start DMX address (auto-incrementing available).
      5. Load a .qxw template workspace (or re-use the one loaded in the main
         shell).
      6. Generate a new .qxw: the template's Engine/Fixture blocks and
         FixtureGroup are rebuilt, FixtureVal entries in all Functions are
         expanded/cloned to match the new fixture count, and 3-D Monitor
         FxItem positions are updated from the canvas layout.
    """

    # ── internal constants ────────────────────────────────────────────────────
    _CANVAS_PAD   = 40     # pixel padding around the stage area
    _FX_RADIUS    = 18     # fixture icon radius in pixels
    _DEFAULT_UNIVERSE = 0  # 0-indexed (Universe 1)

    def __init__(self, parent, app):
        self.parent = parent
        self.app    = app

        # ── stage dimensions (mm) — driven by UI fields ───────────────────────
        self._stage_w_mm = 8000   # default 8 m wide
        self._stage_d_mm = 6000   # default 6 m deep
        self._stage_h_mm = 4000   # default 4 m tall (max rig height)

        # ── height role names (5 fixed tiers, evenly dividing stage height) ───
        self._height_role_names = ["Floor", "Low-Mid", "Mid", "Top-Mid", "Top"]

        # ── grid configuration ────────────────────────────────────────────────
        self._grid_cols  = 8      # A–H columns (X axis)
        self._grid_rows  = 6      # 1–6 rows    (Z/depth axis)
        # View: "top" = top-down plan, "front" = front elevation, "side" = side elevation
        self._view_mode  = "top"

        # ── data ──────────────────────────────────────────────────────────────
        self.qxf_defs       = {}   # model_key -> parsed qxf dict
        self.rig             = []  # list of rig_entry dicts (ordered)
        self._drag_idx       = None
        self._drag_ox        = 0
        self._drag_oy        = 0
        self._canvas_w       = 600
        self._canvas_h       = 400
        self._template_file  = ""  # separate template path (optional)

        # ── Function assignment state ─────────────────────────────────────────
        # List of dicts: {id, name, type, fixture_slots: [fid,...], desc}
        self._template_funcs = []
        # Map: func_id → list of rig indices (one per template slot)
        # e.g. {0: [0,1,2,3,4,5,6,7]}  means all 8 rig fixtures serve func 0
        self._func_assignments = {}

        self._build_ui()

    # ══════════════════════════════════════════════════════════════════════════
    # UI CONSTRUCTION
    # ══════════════════════════════════════════════════════════════════════════
    def _build_ui(self):
        t = THEMES[self.app.current_theme]

        # ── Toolbar row 1: fixture operations ─────────────────────────────────
        tb1 = tk.Frame(self.parent, padx=10, pady=4)
        tb1.pack(fill=tk.X)

        ttk.Button(tb1, text="➕ Add Fixture",
                   command=self._add_fixture_dialog, style="Assign.TButton").pack(
            side=tk.LEFT, padx=(0, 4))
        ttk.Button(tb1, text="🗑 Remove",
                   command=self._remove_selected, style="Danger.TButton").pack(
            side=tk.LEFT, padx=(0, 4))
        ttk.Button(tb1, text="⬆", command=lambda: self._move_row(-1),
                   style="Normal.TButton").pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(tb1, text="⬇", command=lambda: self._move_row(1),
                   style="Normal.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(tb1, text="⚙ Auto-DMX",
                   command=self._auto_assign_dmx, style="Normal.TButton").pack(
            side=tk.LEFT, padx=(0, 0))

        # Generate + units on the right
        ttk.Button(tb1, text="🚀 GENERATE QXW",
                   command=self._generate_qxw, style="Save.TButton").pack(
            side=tk.RIGHT, padx=(4, 0))
        self._unit_var = tk.StringVar(value="Metric (m/mm)")
        unit_cb = ttk.Combobox(tb1, textvariable=self._unit_var,
                                values=["Metric (m/mm)", "Imperial (ft/in)"],
                                state="readonly", width=14)
        unit_cb.pack(side=tk.RIGHT, padx=(4, 6))
        tk.Label(tb1, text="Units:", font=("Helvetica", 9)).pack(side=tk.RIGHT)
        unit_cb.bind("<<ComboboxSelected>>", self._on_units_changed)

        # ── Toolbar row 2: template + stage size ──────────────────────────────
        tb2 = tk.Frame(self.parent, padx=10, pady=2)
        tb2.pack(fill=tk.X)

        ttk.Button(tb2, text="🗂 Set Template",
                   command=self._load_template_dialog, style="Normal.TButton").pack(
            side=tk.LEFT, padx=(0, 6))
        self.lbl_template = tk.Label(tb2, text='No template \u2014 load a QXW above or use "Set Template"',
                                     font=("Helvetica", 9, "italic"), anchor="w")
        self.lbl_template.pack(side=tk.LEFT, padx=(0, 12))

        # Stage size fields
        self._lbl_stage_w = tk.Label(tb2, text="Stage W:", font=("Helvetica", 9))
        self._lbl_stage_w.pack(side=tk.LEFT)
        self._stage_w_var = tk.StringVar(value="8.0")
        sw_e = ttk.Entry(tb2, textvariable=self._stage_w_var, width=6)
        sw_e.pack(side=tk.LEFT, padx=(2, 6))
        sw_e.bind("<Return>",   self._on_stage_size_changed)
        sw_e.bind("<FocusOut>", self._on_stage_size_changed)

        self._lbl_stage_d = tk.Label(tb2, text="Stage D:", font=("Helvetica", 9))
        self._lbl_stage_d.pack(side=tk.LEFT)
        self._stage_d_var = tk.StringVar(value="6.0")
        sd_e = ttk.Entry(tb2, textvariable=self._stage_d_var, width=6)
        sd_e.pack(side=tk.LEFT, padx=(2, 6))
        sd_e.bind("<Return>",   self._on_stage_size_changed)
        sd_e.bind("<FocusOut>", self._on_stage_size_changed)

        self._lbl_stage_h = tk.Label(tb2, text="Stage H:", font=("Helvetica", 9))
        self._lbl_stage_h.pack(side=tk.LEFT)
        self._stage_h_var = tk.StringVar(value="4.0")
        sh_e = ttk.Entry(tb2, textvariable=self._stage_h_var, width=6)
        sh_e.pack(side=tk.LEFT, padx=(2, 6))
        sh_e.bind("<Return>",   self._on_stage_size_changed)
        sh_e.bind("<FocusOut>", self._on_stage_size_changed)

        self._lbl_stage_unit = tk.Label(tb2, text="m  each",
                                         font=("Helvetica", 9, "italic"))
        self._lbl_stage_unit.pack(side=tk.LEFT)

        # Grid divisions
        tk.Label(tb2, text="   Grid:", font=("Helvetica", 9)).pack(side=tk.LEFT)
        self._grid_cols_var = tk.StringVar(value="8")
        gc_e = ttk.Entry(tb2, textvariable=self._grid_cols_var, width=3)
        gc_e.pack(side=tk.LEFT, padx=(2, 2))
        tk.Label(tb2, text="×", font=("Helvetica", 9)).pack(side=tk.LEFT)
        self._grid_rows_var = tk.StringVar(value="6")
        gr_e = ttk.Entry(tb2, textvariable=self._grid_rows_var, width=3)
        gr_e.pack(side=tk.LEFT, padx=(2, 6))
        for e_ in (gc_e, gr_e):
            e_.bind("<Return>",   self._on_grid_changed)
            e_.bind("<FocusOut>", self._on_grid_changed)

        # Snap to grid checkbox
        self._snap_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(tb2, text="Snap", variable=self._snap_var).pack(
            side=tk.LEFT, padx=(0, 8))

        # View toggle buttons
        self._view_btn_top   = ttk.Button(tb2, text="⬛ Top",
                                           command=lambda: self._set_view("top"),
                                           style="Normal.TButton")
        self._view_btn_front = ttk.Button(tb2, text="⬛ Front",
                                           command=lambda: self._set_view("front"),
                                           style="Normal.TButton")
        self._view_btn_side  = ttk.Button(tb2, text="⬛ Side",
                                           command=lambda: self._set_view("side"),
                                           style="Normal.TButton")
        self._view_btn_top.pack(side=tk.LEFT, padx=(0, 2))
        self._view_btn_front.pack(side=tk.LEFT, padx=(0, 2))
        self._view_btn_side.pack(side=tk.LEFT, padx=(0, 2))

        # ── Main pane: left = table, right = canvas ───────────────────────────
        pane = tk.PanedWindow(self.parent, orient=tk.HORIZONTAL, sashwidth=6)
        pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 0))

        # Left: rig table (column IDs are short keys; headings updated by unit)
        left = tk.Frame(pane)
        pane.add(left, minsize=500)

        cols = ("#", "Name", "Manufacturer", "Model", "Mode",
                "Universe", "Addr", "Stage Role", "X", "Z", "H Role")
        self.tree = ttk.Treeview(left, columns=cols, show="headings",
                                 selectmode="browse")
        widths = [28, 130, 100, 120, 78, 66, 56, 120, 74, 74, 110]
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center")
        self.tree.column("Name",  anchor="w")
        self.tree.column("Model", anchor="w")

        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.LEFT, fill=tk.Y)

        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Right: stage canvas
        right = tk.Frame(pane)
        pane.add(right, minsize=280)

        self.canvas = tk.Canvas(right, bg=t["canvas_bg"], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>",      self._on_canvas_configure)
        self.canvas.bind("<ButtonPress-1>",  self._on_canvas_press)
        self.canvas.bind("<B1-Motion>",      self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)

        # ── Status / info strip ───────────────────────────────────────────────
        bot = tk.Frame(self.parent, padx=10, pady=3)
        bot.pack(fill=tk.X)
        self.lbl_info = tk.Label(
            bot,
            text="Load a QXW workspace — existing fixtures appear automatically. Use ➕ to add more.",
            font=("Helvetica", 9), anchor="w")
        self.lbl_info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lbl_qxf_loaded = tk.Label(bot, text="",
                                       font=("Helvetica", 9, "italic"))
        self.lbl_qxf_loaded.pack(side=tk.RIGHT)

        # ── Function Assignment panel (collapsible) ───────────────────────────
        self.assign_tab = FunctionAssignPanel(self.parent, self)
        self.assign_tab.pack(fill=tk.BOTH, expand=False, padx=10, pady=(2, 4))

        # Set initial column headings with unit labels
        self._update_col_headings()
        # Mark Top view as active on startup
        self._set_view("top")

    # ══════════════════════════════════════════════════════════════════════════
    # THEME / QXW NOTIFICATIONS
    # ══════════════════════════════════════════════════════════════════════════
    def on_theme_changed(self):
        t = THEMES[self.app.current_theme]
        self.canvas.configure(bg=t["canvas_bg"])
        self.lbl_info.configure(bg=t["bg"], fg=t["lbl_gray"])
        self.lbl_qxf_loaded.configure(bg=t["bg"], fg=t["accent"])
        self.lbl_template.configure(bg=t["bg"], fg=t["lbl_gray"])
        self.lbl_stage_unit_refresh(t)
        if hasattr(self, 'assign_tab'):
            self.assign_tab.on_theme_changed()
        self._draw_canvas()

    def lbl_stage_unit_refresh(self, t=None):
        if t is None:
            t = THEMES[self.app.current_theme]
        for lbl in (self._lbl_stage_w, self._lbl_stage_d,
                    self._lbl_stage_h, self._lbl_stage_unit):
            lbl.configure(bg=t["bg"], fg=t["fg"])

    def on_qxw_loaded(self):
        """When the main workspace loads, adopt it as template and pre-load its fixtures."""
        if not self._template_file:
            # Sync the template label to the main workspace name
            self.lbl_template.config(
                text=f"template: {os.path.basename(self.app.current_qxw_file)}"
            )
            # Pre-populate the rig from the main workspace
            self._import_fixtures_from_qxw(self.app.qxw_root)

    # ── Units ─────────────────────────────────────────────────────────────────
    def _is_imperial(self):
        return "Imperial" in self._unit_var.get()

    def _mm_to_display(self, mm):
        """Convert internal mm value to display string in current units."""
        if self._is_imperial():
            total_in = mm / 25.4
            ft = int(total_in // 12)
            inch = round(total_in % 12, 1)
            if ft == 0:
                return f'{inch}"'
            return f"{ft}'{inch}\""
        return str(int(mm))

    def _display_to_mm(self, text):
        """Parse a display-unit string back to mm (int). Returns None on error."""
        text = text.strip()
        if self._is_imperial():
            # Accept formats: 5'3", 5'3.5", 63", 63.5
            try:
                # feet'inches" format
                m = re.match(r"(\d+)'([\d.]+)\"?", text)
                if m:
                    return int((int(m.group(1)) * 12 + float(m.group(2))) * 25.4)
                # plain inches
                m2 = re.match(r"([\d.]+)\"?$", text)
                if m2:
                    return int(float(m2.group(1)) * 25.4)
            except Exception:
                pass
            return None
        else:
            try:
                return max(0, int(text))
            except ValueError:
                return None

    def _stage_dim_to_display(self, mm):
        """Convert stage dimension mm → display unit string for the entry fields."""
        if self._is_imperial():
            return f"{mm / 304.8:.2f}"   # feet with 2 decimals
        return f"{mm / 1000:.1f}"         # metres with 1 decimal

    def _stage_display_to_mm(self, text):
        """Parse stage entry field back to mm. Returns None on parse error."""
        try:
            val = float(text)
        except ValueError:
            return None
        if self._is_imperial():
            return int(val * 304.8)       # feet → mm
        return int(val * 1000)            # metres → mm

    def _update_col_headings(self):
        u = "in" if self._is_imperial() else "mm"
        self.tree.heading("X",      text=f"X ({u})")
        self.tree.heading("Z",      text=f"Z ({u})")
        self.tree.heading("H Role", text="Height Role")

    def _on_units_changed(self, event=None):
        """Switch units: convert stage fields and refresh table + canvas labels."""
        u = self._unit_var.get()
        is_imp = "Imperial" in u

        # Update stage W/D/H entry fields to new unit
        self._stage_w_var.set(self._stage_dim_to_display(self._stage_w_mm))
        self._stage_d_var.set(self._stage_dim_to_display(self._stage_d_mm))
        self._stage_h_var.set(self._stage_dim_to_display(self._stage_h_mm))

        # Update the "each" unit label and stage field labels
        dim_unit = "ft" if is_imp else "m"
        self._lbl_stage_unit.config(text=f"{dim_unit}  each")
        self._lbl_stage_w.config(text="Stage W:")
        self._lbl_stage_d.config(text="Stage D:")

        self._update_col_headings()
        self._refresh_tree()
        self._draw_canvas()

    def _on_stage_size_changed(self, event=None):
        """Parse W/D/H fields (in current units) and redraw canvas."""
        w = self._stage_display_to_mm(self._stage_w_var.get())
        if w is not None and w >= 500:
            self._stage_w_mm = w
        d = self._stage_display_to_mm(self._stage_d_var.get())
        if d is not None and d >= 500:
            self._stage_d_mm = d
        h = self._stage_display_to_mm(self._stage_h_var.get())
        if h is not None and h >= 200:
            self._stage_h_mm = h
        # Clamp existing fixtures to new bounds
        for e in self.rig:
            e["x_mm"] = max(0, min(self._stage_w_mm, e["x_mm"]))
            e["z_mm"] = max(0, min(self._stage_d_mm, e["z_mm"]))
            # Re-snap y_mm to closest tier in new height scale
            tier_idx = self._mm_to_height_tier(e.get("y_mm", 0))
            e["y_mm"] = self._height_tiers[tier_idx]
        self._refresh_tree()
        self._draw_canvas()

    def _on_grid_changed(self, event=None):
        try:
            c = int(self._grid_cols_var.get())
            if 2 <= c <= 26:
                self._grid_cols = c
        except ValueError:
            pass
        try:
            r = int(self._grid_rows_var.get())
            if 2 <= r <= 20:
                self._grid_rows = r
        except ValueError:
            pass
        self._draw_canvas()

    def _set_view(self, mode):
        self._view_mode = mode
        self._draw_canvas()
        # Visual feedback: update button labels
        labels = {"top": ("● Top", "⬛ Front", "⬛ Side"),
                  "front": ("⬛ Top", "● Front", "⬛ Side"),
                  "side":  ("⬛ Top", "⬛ Front", "● Side")}
        t_lbl, f_lbl, s_lbl = labels.get(mode, labels["top"])
        self._view_btn_top.config(text=t_lbl)
        self._view_btn_front.config(text=f_lbl)
        self._view_btn_side.config(text=s_lbl)

    # ── Grid coordinate helpers ────────────────────────────────────────────────
    # ── Grid coordinate system ────────────────────────────────────────────────
    # Intersections, not cells.  Column lines: A=SL edge … H=SR edge (+ cols).
    # Row lines: 1=downstage edge (audience) … N=upstage edge.
    # So "A1" = front-left corner, "H1" = front-right, "A6" = back-left, etc.
    # A fixture sits ON a grid intersection, not in a cell centre.
    # "A1.5" or non-integer positions sit between lines — we round to nearest.

    def _mm_to_grid(self, x_mm, z_mm):
        """
        Convert mm position to intersection label e.g. 'C3'.
        col 0..cols maps to letters A..Z along stage width (A=SL).
        row 0..rows maps to numbers 1..N+1 from DOWNSTAGE (audience) to UPSTAGE.
        We clamp to valid intersections.
        """
        # Intersections: cols+1 vertical lines, rows+1 horizontal lines
        n_vcols = self._grid_cols + 1   # number of vertical lines (A … last letter)
        n_hrows = self._grid_rows + 1   # number of horizontal lines (1 … last number)

        # Nearest vertical line index (0=SL edge)
        col_idx = round(x_mm / self._stage_w_mm * self._grid_cols)
        col_idx = max(0, min(self._grid_cols, col_idx))

        # Nearest horizontal line index
        # z_mm=stage_d_mm → downstage → row 1 → canvas bottom → row_idx=0
        # z_mm=0          → upstage   → row N+1→ canvas top   → row_idx=rows
        row_idx = round(z_mm / self._stage_d_mm * self._grid_rows)
        row_idx = max(0, min(self._grid_rows, row_idx))

        col_letter = chr(ord('A') + col_idx)
        # row_idx=rows → downstage edge → row 1
        # row_idx=0    → upstage edge   → row rows+1
        row_number = self._grid_rows - row_idx + 1
        return f"{col_letter}{row_number}"

    def _grid_to_mm(self, grid_ref):
        """
        Parse intersection ref 'C3' → (x_mm, z_mm).
        Row 1 = downstage (audience side), row N = upstage.
        Returns None on error.
        """
        grid_ref = grid_ref.strip().upper()
        if not grid_ref or not grid_ref[0].isalpha():
            return None
        col_letter = grid_ref[0]
        row_str    = grid_ref[1:]
        try:
            col_idx = ord(col_letter) - ord('A')
            row_num = int(row_str)
            row_idx = row_num - 1   # 0-indexed
        except ValueError:
            return None
        if not (0 <= col_idx <= self._grid_cols and 0 <= row_idx <= self._grid_rows):
            return None
        # Column line x position
        x_mm = int(col_idx / self._grid_cols * self._stage_w_mm)
        # Row line z position:
        # row 1   = downstage = z_mm = stage_d_mm  → row_idx = rows
        # row N+1 = upstage   = z_mm = 0            → row_idx = 0
        row_idx = self._grid_rows - row_num + 1
        z_mm = int(row_idx / self._grid_rows * self._stage_d_mm)
        return x_mm, z_mm

    def _snap_to_grid(self, x_mm, z_mm):
        """Snap a position to the nearest grid intersection."""
        ref = self._mm_to_grid(x_mm, z_mm)
        result = self._grid_to_mm(ref)
        return result if result else (x_mm, z_mm)

    @property
    def _height_tiers(self):
        """5 evenly-spaced heights from 0 to stage_h_mm: Floor/Low-Mid/Mid/Top-Mid/Top."""
        n = len(self._height_role_names)   # always 5
        return [int(self._stage_h_mm * i / (n - 1)) for i in range(n)]

    @property
    def _height_labels(self):
        """Labels for the 5 tiers, including current mm value."""
        tiers = self._height_tiers
        names = self._height_role_names
        if self._is_imperial():
            def fmt(mm): return f"{mm/25.4:.0f}\""
        else:
            def fmt(mm): return f"{mm/1000:.2f}m"
        return [f"{names[i]} ({fmt(tiers[i])})" for i in range(len(names))]

    def _mm_to_height_tier(self, y_mm):
        """Return the index (0–4) of the closest height tier."""
        tiers = self._height_tiers
        best, best_dist = 0, abs(y_mm - tiers[0])
        for i, h in enumerate(tiers[1:], 1):
            d = abs(y_mm - h)
            if d < best_dist:
                best_dist, best = d, i
        return best

    def _height_role_to_mm(self, role_name):
        """Return the y_mm for a named height role (e.g. 'Mid')."""
        try:
            idx = self._height_role_names.index(role_name)
            return self._height_tiers[idx]
        except ValueError:
            return 0

    def _mm_to_height_role(self, y_mm):
        """Return the name of the closest height tier for a given y_mm."""
        return self._height_role_names[self._mm_to_height_tier(y_mm)]

    def _role_to_grid(self, role):
        """
        Return the grid intersection ref string for a named stage role.
        Front = row 1 (downstage/audience), Back = row N+1 (upstage).
        Left = col A (SL), Right = col last (SR), Center = mid col.
        """
        cols = self._grid_cols
        rows = self._grid_rows
        mid_col = chr(ord('A') + cols // 2)   # middle column letter
        sl_col  = 'A'
        sr_col  = chr(ord('A') + cols)        # last column (SR edge)
        front_row = 1                          # downstage = row 1
        back_row  = rows + 1                   # upstage  = row N+1
        mid_row   = rows // 2 + 1

        mapping = {
            "Front Left":   f"{sl_col}{front_row}",
            "Front Center": f"{mid_col}{front_row}",
            "Front Right":  f"{sr_col}{front_row}",
            "Back Left":    f"{sl_col}{back_row}",
            "Back Center":  f"{mid_col}{back_row}",
            "Back Right":   f"{sr_col}{back_row}",
            "Side Left":    f"{sl_col}{mid_row}",
            "Side Right":   f"{sr_col}{mid_row}",
            "Center":       f"{mid_col}{mid_row}",
        }
        return mapping.get(role)

    def _role_to_mm(self, role):
        """Return (x_mm, z_mm) for a named stage role via the grid system."""
        ref = self._role_to_grid(role)
        if ref:
            result = self._grid_to_mm(ref)
            if result:
                return result
        return None

    # ══════════════════════════════════════════════════════════════════════════
    # QXF LOADING
    # ══════════════════════════════════════════════════════════════════════════
    def _load_qxf(self):
        files = filedialog.askopenfilenames(
            title="Select Fixture Definition File(s)",
            filetypes=[("QLC+ Fixture Def", "*.qxf"), ("All Files", "*.*")]
        )
        for path in files:
            try:
                self._parse_qxf(path)
            except Exception as e:
                messagebox.showerror("QXF Parse Error",
                                     f"Could not parse {os.path.basename(path)}:\n{e}")
        if self.qxf_defs:
            n_types = len(self.qxf_defs)
            self.lbl_qxf_loaded.config(
                text=f"{n_types} fixture type(s) • {len(self.rig)} in rig")
            self._set_info(f"{n_types} fixture type(s) available.")

    def _parse_qxf(self, path):
        """Parse a .qxf file and store its definition."""
        QXF_NS = "http://www.qlcplus.org/FixtureDefinition"
        ns = {"f": QXF_NS}
        tree = ET.parse(path)
        root = tree.getroot()

        mfg   = root.findtext("f:Manufacturer", default="Unknown", namespaces=ns)
        model = root.findtext("f:Model",        default="Unknown", namespaces=ns)
        ftype = root.findtext("f:Type",         default="Color Changer", namespaces=ns)

        # Collect modes and their channel counts
        modes = {}
        for mode_el in root.findall("f:Mode", ns):
            mname = mode_el.get("Name", "Default")
            ch_count = len(mode_el.findall("f:Channel", ns))
            modes[mname] = ch_count

        # Collect channels list (for reference)
        channels = []
        for ch_el in root.findall("f:Channel", ns):
            channels.append(ch_el.get("Name", "?"))

        key = f"{mfg}::{model}"
        self.qxf_defs[key] = {
            "manufacturer": mfg,
            "model":        model,
            "type":         ftype,
            "modes":        modes,   # {mode_name: channel_count}
            "channels":     channels,
            "path":         path,
        }

    def _import_fixtures_from_qxw(self, qxw_root):
        """
        Read Fixture elements from a QXW root and populate the rig table.
        Skips fixtures whose model is not in qxf_defs (logs a warning).
        Merges with existing rig — won't duplicate fixtures already present
        (matched by name + address).
        """
        if qxw_root is None:
            return

        existing_keys = {(e["name"], e["address"], e["universe"]) for e in self.rig}

        # Read Monitor positions for 3D coordinates
        monitor_pos = {}
        for fxi in qxw_root.findall(".//q:Monitor/q:FxItem", NS):
            fid = fxi.get("ID")
            monitor_pos[fid] = {
                "x": float(fxi.get("XPos", "0")),
                "y": float(fxi.get("YPos", "0")),
                "z": float(fxi.get("ZPos", "0")),
            }

        imported = 0
        for fix in qxw_root.findall("q:Engine/q:Fixture", NS):
            id_node = fix.find("q:ID", NS)
            fid     = id_node.text if id_node is not None else None
            name_n  = fix.find("q:Name", NS)
            name    = (name_n.text or "").strip() if name_n is not None else ""
            if not name:
                name = f"Fixture {fid}"
            mfg_n   = fix.find("q:Manufacturer", NS)
            mfg     = mfg_n.text if mfg_n is not None else "Unknown"
            model_n = fix.find("q:Model", NS)
            model   = model_n.text if model_n is not None else "Unknown"
            mode_n  = fix.find("q:Mode", NS)
            mode    = mode_n.text if mode_n is not None else "Default"
            uni_n   = fix.find("q:Universe", NS)
            universe = int(uni_n.text) if uni_n is not None else 0
            addr_n  = fix.find("q:Address", NS)
            address = int(addr_n.text) if addr_n is not None else 0
            ch_n    = fix.find("q:Channels", NS)
            ch_count = int(ch_n.text) if ch_n is not None else 7

            # Skip duplicates
            if (name, address, universe) in existing_keys:
                continue

            # Get 3D position if available
            pos = monitor_pos.get(fid, {"x": 0, "y": 0, "z": 0})

            key = f"{mfg}::{model}"
            # Register fixture type in qxf_defs if not already there
            # (so the user can add more of the same type without loading the .qxf first)
            if key not in self.qxf_defs:
                self.qxf_defs[key] = {
                    "manufacturer": mfg,
                    "model":        model,
                    "type":         "Color Changer",
                    "modes":        {mode: ch_count},
                    "channels":     [],
                    "path":         "",   # no .qxf file on disk
                }
            else:
                # Ensure this mode is registered
                if mode not in self.qxf_defs[key]["modes"]:
                    self.qxf_defs[key]["modes"][mode] = ch_count

            entry = {
                "key":          key,
                "manufacturer": mfg,
                "model":        model,
                "mode":         mode,
                "ch_count":     ch_count,
                "name":         name,
                "role":         "Custom",
                "universe":     universe,
                "address":      address,
                "x_mm":         int(pos["x"]),
                "z_mm":         int(pos["z"]),
                "y_mm":         int(pos["y"]),
            }
            self.rig.append(entry)
            existing_keys.add((name, address, universe))
            imported += 1

        if imported:
            n_types = len(self.qxf_defs)
            self.lbl_qxf_loaded.config(
                text=f"{n_types} fixture type(s) • {len(self.rig)} in rig")
            self._refresh_tree()
            self._draw_canvas()
            self._set_info(f"Imported {imported} fixture(s) from workspace.")

        # Always read stage dims and parse functions, even if no new fixtures
        self._read_stage_dims_from_qxw(qxw_root)
        self._parse_template_funcs(qxw_root)
        if hasattr(self, 'assign_tab'):
            self.assign_tab.refresh()

    def _read_stage_dims_from_qxw(self, qxw_root):
        """Read Monitor Grid Width/Height/Depth and populate stage dimension fields."""
        if qxw_root is None:
            return
        grid = qxw_root.find('.//q:Monitor/q:Grid', NS)
        if grid is None:
            return
        # QLC+ Grid units: 0 = m (stored as integer metres), 1 = ft
        units = int(grid.get('Units', '0'))
        try:
            w = float(grid.get('Width',  str(self._stage_w_mm // 1000)))
            d = float(grid.get('Depth',  str(self._stage_d_mm // 1000)))
            h = float(grid.get('Height', str(self._stage_h_mm // 1000)))
        except (ValueError, TypeError):
            return
        if units == 1:  # feet
            self._stage_w_mm = int(w * 304.8)
            self._stage_d_mm = int(d * 304.8)
            self._stage_h_mm = int(h * 304.8)
        else:           # metres
            self._stage_w_mm = int(w * 1000)
            self._stage_d_mm = int(d * 1000)
            self._stage_h_mm = int(h * 1000)
        # Update UI fields
        self._stage_w_var.set(self._stage_dim_to_display(self._stage_w_mm))
        self._stage_d_var.set(self._stage_dim_to_display(self._stage_d_mm))
        self._stage_h_var.set(self._stage_dim_to_display(self._stage_h_mm))

    def _parse_template_funcs(self, qxw_root):
        """
        Parse all Functions from the template that reference fixtures
        (Scenes and RGBMatrices) plus container functions (Collections, Chasers).
        Stores in self._template_funcs and builds default assignments.
        """
        if qxw_root is None:
            return
        self._template_funcs.clear()

        # Get descriptions from Dictionary tab if available
        dict_map = {}
        if hasattr(self.app, 'dict_mgr'):
            try:
                dict_map = {e['name']: e.get('description', '')
                            for e in self.app.dict_mgr.dict_data.values()
                            if isinstance(e, dict) and 'name' in e}
            except Exception:
                pass

        for func in qxw_root.findall('q:Engine/q:Function', NS):
            fid   = func.get('ID')
            fname = func.get('Name', f'Function {fid}')
            ftype = func.get('Type', '')

            # Fixture slots: list of template fixture IDs referenced
            slots = []
            if ftype in ('Scene',):
                for fv in func.findall('q:FixtureVal', NS):
                    slot_id = fv.get('ID')
                    if slot_id is not None and slot_id not in slots:
                        slots.append(slot_id)
            elif ftype == 'RGBMatrix':
                fg = func.find('q:FixtureGroup', NS)
                if fg is not None:
                    fg_id = fg.get('ID')
                    # Find fixture IDs in this group
                    group_el = qxw_root.find(
                        f'q:Engine/q:FixtureGroup[@ID="{fg_id}"]', NS)
                    if group_el is not None:
                        for head in group_el.findall('q:Head', NS):
                            fid_h = head.get('Fixture')
                            if fid_h and fid_h not in slots:
                                slots.append(fid_h)

            desc = dict_map.get(fname, '')

            self._template_funcs.append({
                'id':     fid,
                'name':   fname,
                'type':   ftype,
                'slots':  slots,   # template fixture IDs
                'desc':   desc,
            })

        # Build default assignments: each template slot → matching rig fixture
        # by position (closest) or by order if no positional data
        self._build_default_assignments(qxw_root)

    def _build_default_assignments(self, qxw_root):
        """
        For each function, assign rig fixtures to template slots.

        Strategy (in priority order for each slot):
          1. Exact name match — if a rig fixture has the same name as the
             template fixture for that slot, use it directly.
          2. Role match — if the template fixture's name contains a role keyword
             (Front Left, Back Right, etc.) and a rig fixture has that role, use it.
          3. Position proximity — use the X/Z position from the Monitor 3D view
             to find the closest rig fixture that hasn't been used yet in this
             function.
          4. Sequential fallback — assign rig fixtures in order (0, 1, 2, …).

        Extra rig fixtures beyond the template slot count are appended at the
        end of each function's assignment list in position order.
        """
        if not self.rig:
            return

        # ── Build template fixture info map ───────────────────────────────────
        # id → {name, x, z}
        tmpl_info = {}
        for fix in qxw_root.findall('q:Engine/q:Fixture', NS):
            fid_n = fix.find('q:ID', NS)
            fid   = fid_n.text if fid_n is not None else fix.get('ID')
            name_n = fix.find('q:Name', NS)
            name   = (name_n.text or '').strip() if name_n is not None else ''
            tmpl_info[fid] = {'name': name, 'x': 0.0, 'z': 0.0}

        for fxi in qxw_root.findall('.//q:Monitor/q:FxItem', NS):
            fid = fxi.get('ID')
            if fid in tmpl_info:
                tmpl_info[fid]['x'] = float(fxi.get('XPos', 0))
                tmpl_info[fid]['z'] = float(fxi.get('ZPos', 0))

        # ── Role keyword extraction ────────────────────────────────────────────
        _role_keys = ["Front Left", "Front Center", "Front Right",
                      "Back Left",  "Back Center",  "Back Right",
                      "Side Left",  "Side Right",   "Center"]

        def _extract_role(name):
            """Return the first role keyword found in a fixture name, or None."""
            name_up = name.upper()
            for rk in _role_keys:
                if rk.upper() in name_up:
                    return rk
            return None

        # ── Pre-build rig lookup structures ───────────────────────────────────
        rig_by_name = {e['name']: i for i, e in enumerate(self.rig)}
        rig_by_role = {}  # role → list of rig indices with that role
        for i, e in enumerate(self.rig):
            r = e.get('role', 'Custom')
            rig_by_role.setdefault(r, []).append(i)

        def _closest_unused(tmpl_x, tmpl_z, used):
            """Return the rig index closest to (tmpl_x, tmpl_z) not in used."""
            best_i, best_d = -1, float('inf')
            for i, e in enumerate(self.rig):
                if i in used:
                    continue
                d = ((e['x_mm'] - tmpl_x) ** 2 + (e['z_mm'] - tmpl_z) ** 2) ** 0.5
                if d < best_d:
                    best_d, best_i = d, i
            # If all used, fall back to global closest
            if best_i == -1:
                for i, e in enumerate(self.rig):
                    d = ((e['x_mm'] - tmpl_x) ** 2 + (e['z_mm'] - tmpl_z) ** 2) ** 0.5
                    if d < best_d:
                        best_d, best_i = d, i
            return best_i

        # ── Assign per function ───────────────────────────────────────────────
        self._func_assignments.clear()
        for tf in self._template_funcs:
            slots = tf['slots']
            n_rig = len(self.rig)

            if not slots:
                # Chaser / Collection — all rig fixtures in position order
                self._func_assignments[tf['id']] = list(range(n_rig))
                continue

            assigned = []
            used     = set()

            for slot_id in slots:
                info     = tmpl_info.get(slot_id, {'name': '', 'x': 0.0, 'z': 0.0})
                t_name   = info['name']
                t_x, t_z = info['x'], info['z']
                ri = -1

                # 1. Exact name match
                if t_name and t_name in rig_by_name:
                    candidate = rig_by_name[t_name]
                    if candidate not in used:
                        ri = candidate

                # 2. Role match (pick first unused rig fixture with matching role)
                if ri == -1:
                    role = _extract_role(t_name)
                    if role:
                        for candidate in rig_by_role.get(role, []):
                            if candidate not in used:
                                ri = candidate
                                break

                # 3. Position proximity (closest unused)
                if ri == -1:
                    ri = _closest_unused(t_x, t_z, used)

                # 4. Sequential fallback (should rarely be needed)
                if ri == -1:
                    ri = len(assigned) % n_rig

                assigned.append(ri)
                used.add(ri)

            # Append remaining rig fixtures (extras) in position order
            for i in range(n_rig):
                if i not in used:
                    assigned.append(i)

            self._func_assignments[tf['id']] = assigned

    # ══════════════════════════════════════════════════════════════════════════
    # ADD / REMOVE / REORDER FIXTURES
    # ══════════════════════════════════════════════════════════════════════════
    def _add_fixture_dialog(self):
        # qxf_defs is populated automatically from the QXW on load.
        # If still empty, the user can still add a fixture with manual channel count.

        dlg = tk.Toplevel(self.parent)
        dlg.title("Add Fixture to Rig")
        dlg.resizable(False, False)
        dlg.grab_set()
        t = THEMES[self.app.current_theme]
        dlg.configure(bg=t["bg"])

        def lbl(parent, text, **kw):
            return tk.Label(parent, text=text, bg=t["bg"], fg=t["fg"],
                            font=("Helvetica", 10), **kw)

        def row(parent, label_text, widget_factory):
            f = tk.Frame(parent, bg=t["bg"])
            f.pack(fill=tk.X, padx=14, pady=4)
            lbl(f, label_text, width=16, anchor="w").pack(side=tk.LEFT)
            w = widget_factory(f)
            w.pack(side=tk.LEFT, fill=tk.X, expand=True)
            return w

        # ── Fixture type selector ─────────────────────────────────────────────
        # Populated from types already known (from QXW), plus a "Custom" option.
        CUSTOM_KEY = "__custom__"
        def_keys   = list(self.qxf_defs.keys()) + [CUSTOM_KEY]
        def_labels = [f"{self.qxf_defs[k]['manufacturer']} — {self.qxf_defs[k]['model']}"
                      for k in def_keys if k != CUSTOM_KEY]
        def_labels.append("Custom (enter details manually)")

        sel_def = tk.StringVar(value=def_labels[0] if len(def_labels) > 1 else def_labels[-1])

        def make_combo_def(parent):
            cb = ttk.Combobox(parent, textvariable=sel_def, values=def_labels,
                              state="readonly", width=36)
            return cb
        combo_def = row(dlg, "Fixture Type:", make_combo_def)

        # ── Mode / channel count ──────────────────────────────────────────────
        sel_mode    = tk.StringVar()
        ch_count_var = tk.StringVar(value="7")
        mode_combo_ref = [None]
        ch_entry_ref   = [None]
        manual_frame_ref = [None]

        def _current_key():
            lbl_val = sel_def.get()
            if lbl_val == "Custom (enter details manually)":
                return CUSTOM_KEY
            idx = def_labels.index(lbl_val) if lbl_val in def_labels else 0
            if idx < len(def_keys) - 1:
                return def_keys[idx]
            return CUSTOM_KEY

        def update_mode_widgets(*_):
            key = _current_key()
            is_custom = key == CUSTOM_KEY
            if mode_combo_ref[0]:
                if is_custom:
                    mode_combo_ref[0].config(state="disabled")
                    sel_mode.set("Default")
                else:
                    modes = list(self.qxf_defs[key]["modes"].keys())
                    mode_combo_ref[0].config(state="readonly", values=modes)
                    if modes:
                        sel_mode.set(modes[0])
                    ch_count_var.set(str(self.qxf_defs[key]["modes"].get(sel_mode.get(), 7)))
            if ch_entry_ref[0]:
                ch_entry_ref[0].config(state="normal" if is_custom else "disabled")
                if not is_custom:
                    key2 = _current_key()
                    modes = list(self.qxf_defs[key2]["modes"].keys())
                    ch_count_var.set(str(self.qxf_defs[key2]["modes"].get(
                        sel_mode.get(), modes[0] if modes else 7)))
            # Show/hide manual detail fields
            if manual_frame_ref[0]:
                if is_custom:
                    manual_frame_ref[0].pack(fill=tk.X, padx=14, pady=2)
                else:
                    manual_frame_ref[0].pack_forget()

        def update_ch_on_mode(*_):
            key = _current_key()
            if key != CUSTOM_KEY:
                ch = self.qxf_defs[key]["modes"].get(sel_mode.get(), 7)
                ch_count_var.set(str(ch))

        def make_combo_mode(parent):
            cb = ttk.Combobox(parent, textvariable=sel_mode, state="readonly", width=36)
            mode_combo_ref[0] = cb
            cb.bind("<<ComboboxSelected>>", update_ch_on_mode)
            return cb
        row(dlg, "Mode:", make_combo_mode)

        def make_ch_entry(parent):
            e = ttk.Entry(parent, textvariable=ch_count_var, width=8, state="disabled")
            ch_entry_ref[0] = e
            return e
        row(dlg, "Ch count:", make_ch_entry)

        # Manual fields (hidden unless Custom)
        mf = tk.Frame(dlg, bg=t["bg"])
        manual_frame_ref[0] = mf
        mfg_var   = tk.StringVar(value="Generic")
        model_var = tk.StringVar(value="PAR")
        tk.Frame(mf, bg=t["bg"]).pack()  # spacer
        def _mrow(label, var, width=20):
            r = tk.Frame(mf, bg=t["bg"])
            r.pack(fill=tk.X, pady=2)
            tk.Label(r, text=label, width=16, anchor="w",
                     bg=t["bg"], fg=t["fg"],
                     font=("Helvetica", 10)).pack(side=tk.LEFT)
            ttk.Entry(r, textvariable=var, width=width).pack(side=tk.LEFT)
        _mrow("Manufacturer:", mfg_var)
        _mrow("Model:", model_var)

        combo_def.bind("<<ComboboxSelected>>", update_mode_widgets)
        update_mode_widgets()  # populate initially

        # Quantity
        qty_var = tk.StringVar(value="1")
        row(dlg, "Quantity:", lambda p: ttk.Entry(p, textvariable=qty_var, width=6))

        # Name prefix
        name_var = tk.StringVar(value="Par")
        row(dlg, "Name Prefix:", lambda p: ttk.Entry(p, textvariable=name_var, width=20))

        # Stage role preset — labels updated dynamically with current grid refs
        def _role_labels():
            return [
                f"Front Left  [{self._role_to_grid('Front Left') or '?'}]",
                f"Front Center  [{self._role_to_grid('Front Center') or '?'}]",
                f"Front Right  [{self._role_to_grid('Front Right') or '?'}]",
                f"Back Left  [{self._role_to_grid('Back Left') or '?'}]",
                f"Back Center  [{self._role_to_grid('Back Center') or '?'}]",
                f"Back Right  [{self._role_to_grid('Back Right') or '?'}]",
                f"Side Left  [{self._role_to_grid('Side Left') or '?'}]",
                f"Side Right  [{self._role_to_grid('Side Right') or '?'}]",
                f"Center  [{self._role_to_grid('Center') or '?'}]",
                "Custom",
            ]
        _role_keys = ["Front Left", "Front Center", "Front Right",
                      "Back Left",  "Back Center",  "Back Right",
                      "Side Left",  "Side Right",   "Center", "Custom"]
        sel_role_lbl = tk.StringVar(value=_role_labels()[0])
        def make_role_combo(parent):
            cb = ttk.Combobox(parent, textvariable=sel_role_lbl,
                               values=_role_labels(), state="readonly", width=28)
            return cb
        row(dlg, "Stage Role:", make_role_combo)

        # Universe
        uni_var = tk.StringVar(value="1")
        row(dlg, "Universe:", lambda p: ttk.Entry(p, textvariable=uni_var, width=6))

        # Start DMX address
        addr_var = tk.StringVar(value=str(self._next_dmx_address()))
        row(dlg, "Start DMX Addr:", lambda p: ttk.Entry(p, textvariable=addr_var, width=6))

        # Height role — 5 tiers derived from stage height
        def _h_role_labels():
            tiers = self._height_tiers
            opts = []
            for i, n in enumerate(self._height_role_names):
                y_disp = self._mm_to_display(tiers[i])
                u = "in" if self._is_imperial() else "mm"
                opts.append(f"{n}  [{y_disp}{u}]")
            return opts
        sel_h_role = tk.StringVar(value=_h_role_labels()[0])  # default: Floor
        def make_h_role_combo(parent):
            return ttk.Combobox(parent, textvariable=sel_h_role,
                                values=_h_role_labels(), state="readonly", width=22)
        row(dlg, "Height Role:", make_h_role_combo)
        tk.Label(dlg, text=f"  Stage H = {self._stage_dim_to_display(self._stage_h_mm)}"
                            f"{'ft' if self._is_imperial() else 'm'}  "
                            f"(change in toolbar)",
                 bg=t["bg"], fg=t["lbl_gray"],
                 font=("Helvetica", 8, "italic")).pack(anchor="w", padx=28, pady=(0, 4))

        # Buttons
        bf = tk.Frame(dlg, bg=t["bg"])
        bf.pack(fill=tk.X, padx=14, pady=(8, 12))

        def do_add():
            try:
                qty = max(1, int(qty_var.get()))
            except ValueError:
                qty = 1
            try:
                universe = max(1, int(uni_var.get())) - 1  # 0-indexed internally
            except ValueError:
                universe = 0
            try:
                addr = max(1, int(addr_var.get())) - 1  # 0-indexed internally
            except ValueError:
                addr = 0

            key  = _current_key()
            if key == CUSTOM_KEY:
                mfg   = mfg_var.get().strip() or "Generic"
                model = model_var.get().strip() or "PAR"
                mode  = sel_mode.get() or "Default"
                try:
                    ch_count = max(1, int(ch_count_var.get()))
                except ValueError:
                    ch_count = 7
                # Register as a known type so it persists in qxf_defs
                custom_key = f"{mfg}::{model}"
                if custom_key not in self.qxf_defs:
                    self.qxf_defs[custom_key] = {
                        "manufacturer": mfg, "model": model,
                        "type": "Color Changer",
                        "modes": {mode: ch_count},
                        "channels": [], "path": "",
                    }
                key = custom_key
            else:
                defn     = self.qxf_defs[key]
                mfg      = defn["manufacturer"]
                model    = defn["model"]
                mode     = sel_mode.get() or list(defn["modes"].keys())[0]
                ch_count = defn["modes"].get(mode, 7)
            prefix = name_var.get().strip() or "Par"
            # Extract bare role key from "Front Left  [A1]" style label
            lbl = sel_role_lbl.get()
            role = lbl.split("  [")[0].strip() if "  [" in lbl else lbl

            # Spread roles automatically if qty > 1 and role is one of the
            # directional presets
            role_spread = {
                "Front Left":  [("Front Left",   800, 5000),
                                 ("Front Center", 4000, 5000),
                                 ("Front Right",  7200, 5000)],
                "Back Left":   [("Back Left",    800, 500),
                                 ("Back Center",  4000, 500),
                                 ("Back Right",   7200, 500)],
            }

            lbl_h = sel_h_role.get()
            h_role_name = lbl_h.split("  [")[0].strip() if "  [" in lbl_h else lbl_h
            height_mm = self._height_role_to_mm(h_role_name)

            for i in range(qty):
                # Default position: evenly spread across stage width
                x_mm = int(self._stage_w_mm * (i + 1) / (qty + 1))
                z_mm = int(self._stage_d_mm * 0.8) if "Front" in role else (
                       int(self._stage_d_mm * 0.15) if "Back"  in role else
                       int(self._stage_d_mm * 0.5))

                name = f"{prefix} {len(self.rig) + 1}"

                entry = {
                    "key":          key,
                    "manufacturer": mfg,
                    "model":        model,
                    "mode":         mode,
                    "ch_count":     ch_count,
                    "name":         name,
                    "role":         role,
                    "universe":     universe,
                    "address":      addr + i * ch_count,
                    "x_mm":         x_mm,
                    "z_mm":         z_mm,
                    "y_mm":         height_mm,
                }
                self.rig.append(entry)

            self._refresh_tree()
            self._draw_canvas()
            dlg.destroy()

        ttk.Button(bf, text="Add", command=do_add,
                   style="Save.TButton").pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(bf, text="Cancel", command=dlg.destroy,
                   style="Normal.TButton").pack(side=tk.RIGHT)

    def _next_dmx_address(self):
        """Returns the next free 1-indexed DMX address on universe 1."""
        if not self.rig:
            return 1
        last = max(self.rig, key=lambda e: e["address"] + e["universe"] * 512)
        return last["address"] + last["ch_count"] + 1  # 0-indexed+1 = 1-indexed

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if 0 <= idx < len(self.rig):
            self.rig.pop(idx)
            self._refresh_tree()
            self._draw_canvas()

    def _move_row(self, direction):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        new_idx = idx + direction
        if 0 <= new_idx < len(self.rig):
            self.rig[idx], self.rig[new_idx] = self.rig[new_idx], self.rig[idx]
            self._refresh_tree()
            self.tree.selection_set(self.tree.get_children()[new_idx])

    def _auto_assign_dmx(self):
        """Re-assign DMX addresses sequentially, respecting universe per fixture."""
        if not self.rig:
            return
        # Group by universe, assign in order within each universe
        by_uni = {}
        for e in self.rig:
            by_uni.setdefault(e["universe"], []).append(e)
        for uni, entries in by_uni.items():
            addr = 0
            for e in entries:
                e["address"] = addr
                addr += e["ch_count"]
        self._refresh_tree()
        self._set_info("DMX addresses auto-assigned sequentially per universe.")

    # ══════════════════════════════════════════════════════════════════════════
    # TREE / INLINE EDIT
    # ══════════════════════════════════════════════════════════════════════════
    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i, e in enumerate(self.rig):
            grid_ref  = self._mm_to_grid(e["x_mm"], e["z_mm"])
            role_disp = f"{e['role']}  [{grid_ref}]"
            y_mm      = e.get("y_mm", 0)
            h_role    = self._mm_to_height_role(y_mm)
            y_disp    = self._mm_to_display(y_mm)
            u         = "in" if self._is_imperial() else "mm"
            h_disp    = f"{h_role}  [{y_disp}{u}]"
            self.tree.insert("", "end", values=(
                i + 1,
                e["name"],
                e["manufacturer"],
                e["model"],
                e["mode"],
                e["universe"] + 1,
                e["address"] + 1,
                role_disp,
                self._mm_to_display(e["x_mm"]),
                self._mm_to_display(e["z_mm"]),
                h_disp,
            ))

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if sel:
            idx = self.tree.index(sel[0])
            self._draw_canvas(highlight=idx)

    def _on_tree_double_click(self, event):
        """Inline edit of Name, Universe, Address, Role, X, Z."""
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        col_idx = int(col.replace("#", "")) - 1
        editable = {1: "name", 5: "universe_disp", 6: "address_disp",
                    7: "role", 8: "x_mm", 9: "z_mm", 10: "h_role"}
        if col_idx not in editable:
            return

        row_idx = self.tree.index(row_id)
        entry = self.rig[row_idx]
        field = editable[col_idx]

        # Get current value
        if field == "universe_disp":
            cur = str(entry["universe"] + 1)
        elif field == "address_disp":
            cur = str(entry["address"] + 1)
        elif field == "h_role":
            cur = self._mm_to_height_role(entry.get("y_mm", 0))
        else:
            cur = str(entry[field])

        # Pop up a small edit entry
        bbox = self.tree.bbox(row_id, col)
        if not bbox:
            return
        x, y, w, h = bbox

        var = tk.StringVar(value=cur)
        edit = tk.Entry(self.tree, textvariable=var, font=("Helvetica", 10))
        edit.place(x=x, y=y, width=max(w, 80), height=h)
        edit.focus_set()
        edit.select_range(0, tk.END)

        # Role options with current grid refs embedded
        _role_keys = ["Front Left", "Front Center", "Front Right",
                      "Back Left",  "Back Center",  "Back Right",
                      "Side Left",  "Side Right",   "Center", "Custom"]
        def _role_opts_with_refs():
            opts = []
            for rk in _role_keys:
                ref = self._role_to_grid(rk)
                opts.append(f"{rk}  [{ref}]" if ref else rk)
            return opts

        def commit(event=None):
            val = var.get().strip()
            edit.destroy()
            if field == "universe_disp":
                try:
                    entry["universe"] = max(0, int(val) - 1)
                except ValueError:
                    pass
            elif field == "address_disp":
                try:
                    entry["address"] = max(0, int(val) - 1)
                except ValueError:
                    pass
            elif field in ("x_mm", "z_mm"):
                mm = self._display_to_mm(val)
                if mm is not None:
                    entry[field] = mm
            elif field == "name":
                entry["name"] = val
            elif field == "role":
                entry["role"] = val
            self._refresh_tree()
            self._draw_canvas()

        def cancel(event=None):
            edit.destroy()

        edit.bind("<Return>",  commit)
        edit.bind("<Escape>",  cancel)
        edit.bind("<FocusOut>", commit)

        # Height role field: show 5-tier dropdown with mm values
        if field == "h_role":
            edit.destroy()
            h_opts = [f"{n}  [{self._mm_to_display(self._height_tiers[i])}"
                      f"{'in' if self._is_imperial() else 'mm'}]"
                      for i, n in enumerate(self._height_role_names)]
            h_role_var = tk.StringVar(value=cur)
            hcb = ttk.Combobox(self.tree, textvariable=h_role_var,
                                values=h_opts, state="readonly",
                                font=("Helvetica", 10))
            hcb.place(x=x, y=y, width=max(w, 180), height=h)
            hcb.focus_set()
            hcb.event_generate('<Button-1>')

            def commit_h_role(ev=None):
                lbl = h_role_var.get()
                role_name = lbl.split("  [")[0].strip() if "  [" in lbl else lbl
                entry["y_mm"] = self._height_role_to_mm(role_name)
                hcb.destroy()
                self._refresh_tree()
                self._draw_canvas()

            hcb.bind("<<ComboboxSelected>>", commit_h_role)
            hcb.bind("<FocusOut>", commit_h_role)

        # Stage role field: show dropdown with grid refs
        elif field == "role":
            edit.destroy()
            role_var = tk.StringVar(value=cur)
            cb = ttk.Combobox(self.tree, textvariable=role_var,
                               values=_role_opts_with_refs(), state="readonly",
                               font=("Helvetica", 10))
            cb.place(x=x, y=y, width=max(w, 180), height=h)
            cb.focus_set()
            cb.event_generate('<Button-1>')

            def commit_role(ev=None):
                lbl = role_var.get()
                # Extract bare role key from "Front Left  [A1]" style
                new_role = lbl.split("  [")[0].strip() if "  [" in lbl else lbl
                entry["role"] = new_role
                cb.destroy()
                # Snap to the role's canonical grid intersection
                coords = self._role_to_mm(new_role)
                if coords:
                    x_mm, z_mm = coords
                    if self._snap_var.get():
                        x_mm, z_mm = self._snap_to_grid(x_mm, z_mm)
                    entry["x_mm"] = x_mm
                    entry["z_mm"] = z_mm
                self._refresh_tree()
                self._draw_canvas()

            cb.bind("<<ComboboxSelected>>", commit_role)
            cb.bind("<FocusOut>", commit_role)

    # ══════════════════════════════════════════════════════════════════════════
    # CANVAS — top-down stage view
    # ══════════════════════════════════════════════════════════════════════════
    def _on_canvas_configure(self, event):
        self._canvas_w = event.width
        self._canvas_h = event.height
        self._draw_canvas()

    def _world_to_canvas(self, x_mm, z_mm):
        """Convert world mm to canvas px for top-down view (uses grid rect)."""
        pad = self._CANVAS_PAD
        sx0 = pad + 18
        sy0 = pad + 18
        sw  = self._canvas_w - pad - sx0
        sh  = self._canvas_h - pad - 20 - sy0
        return self._world_to_canvas_grid(x_mm, z_mm, sx0, sy0, sw, sh)

    def _canvas_to_world(self, px, py):
        """Convert canvas pixels back to world mm (top-down view)."""
        pad = self._CANVAS_PAD
        sx0 = pad + 18
        sy0 = pad + 18
        sw  = self._canvas_w - pad - sx0
        sh  = self._canvas_h - pad - 20 - sy0
        if sw <= 0 or sh <= 0:
            return 0, 0
        x_mm = int((px - sx0) / sw * self._stage_w_mm)
        z_mm = int((py - sy0) / sh * self._stage_d_mm)
        x_mm = max(0, min(self._stage_w_mm, x_mm))
        z_mm = max(0, min(self._stage_d_mm, z_mm))
        return x_mm, z_mm

    def _fixture_at(self, px, py):
        """Return the index of the fixture whose icon contains (px,py)."""
        r = self._FX_RADIUS
        if self._view_mode == "top":
            for i, e in enumerate(self.rig):
                fx, fy = self._world_to_canvas(e["x_mm"], e["z_mm"])
                if abs(px - fx) <= r and abs(py - fy) <= r:
                    return i
        # In elevation views dragging is not supported; clicking selects
        else:
            pad = self._CANVAS_PAD
            sx0 = pad + 60
            sy0 = pad + 18
            sw  = self._canvas_w - pad - sx0
            sh  = self._canvas_h - pad - 20 - sy0
            max_h_mm = max(self._height_tiers) + 500
            for i, e in enumerate(self.rig):
                y_mm = e.get("y_mm", 0)
                if self._view_mode == "front":
                    pos_mm = e["x_mm"]
                    h_total = self._stage_w_mm
                    n_cells = self._grid_cols
                else:
                    pos_mm = e["z_mm"]
                    h_total = self._stage_d_mm
                    n_cells = self._grid_rows
                cell_idx = max(0, min(n_cells - 1,
                               int(pos_mm / h_total * n_cells)))
                cell_px = sw / n_cells
                fx = int(sx0 + (cell_idx + 0.5) * cell_px)
                fy = self._h_to_canvas(y_mm, sy0, sy0 + sh, max_h_mm)
                if abs(px - fx) <= r and abs(py - fy) <= r:
                    return i
        return None

    def _draw_canvas(self, highlight=None):
        if self._view_mode == "top":
            self._draw_top_view(highlight)
        elif self._view_mode == "front":
            self._draw_elevation_view(highlight, axis="front")
        else:
            self._draw_elevation_view(highlight, axis="side")

    def _draw_top_view(self, highlight=None):
        t   = THEMES[self.app.current_theme]
        c   = self.canvas
        r   = self._FX_RADIUS
        pad = self._CANVAS_PAD
        c.delete("all")

        # Layout constants
        AUDIENCE_H = 22   # height of audience band at bottom
        LEFT_MARGIN  = 30  # room for row labels (right of this = stage left edge)
        TOP_MARGIN   = 28  # room for col labels + "UPSTAGE" text
        BOT_MARGIN   = AUDIENCE_H + 18  # audience band + hint text

        stage_x0 = pad + LEFT_MARGIN
        stage_y0 = pad + TOP_MARGIN
        stage_x1 = self._canvas_w - pad - 4
        stage_y1 = self._canvas_h - pad - BOT_MARGIN
        sw = stage_x1 - stage_x0
        sh = stage_y1 - stage_y0
        if sw <= 0 or sh <= 0:
            return

        cols = self._grid_cols   # number of cells horizontally
        rows = self._grid_rows   # number of cells vertically

        # Intersection line spacing
        col_px = sw / cols   # space between vertical lines
        row_py = sh / rows   # space between horizontal lines

        # ── Cell fills (between intersections) ───────────────────────────────
        for ci in range(cols):
            for ri in range(rows):
                x0 = stage_x0 + ci * col_px
                y0 = stage_y0 + ri * row_py
                shade = t["canvas_bg"] if (ci + ri) % 2 == 0 else t["surface"]
                c.create_rectangle(x0, y0, x0 + col_px, y0 + row_py,
                                   fill=shade, outline="")

        # ── Audience band (downstage edge, highlighted) ───────────────────────
        aud_y0 = stage_y1
        aud_y1 = stage_y1 + AUDIENCE_H
        c.create_rectangle(stage_x0, aud_y0, stage_x1, aud_y1,
                           fill=t["yellow"], outline="", stipple="gray50")
        c.create_text((stage_x0 + stage_x1) // 2, aud_y0 + AUDIENCE_H // 2,
                      text="▲  AUDIENCE / DOWNSTAGE  ▲",
                      fill=t["bg"], font=("Helvetica", 8, "bold"))

        # ── Upstage label ─────────────────────────────────────────────────────
        c.create_text((stage_x0 + stage_x1) // 2, stage_y0 - 14,
                      text="UPSTAGE", fill=t["lbl_gray"],
                      font=("Helvetica", 8, "italic"))

        # ── SL / SR edge labels ───────────────────────────────────────────────
        c.create_text(stage_x0 - 14, (stage_y0 + stage_y1) // 2,
                      text="SL", fill=t["lbl_gray"],
                      font=("Helvetica", 8, "bold"), angle=90)
        c.create_text(stage_x1 + 10, (stage_y0 + stage_y1) // 2,
                      text="SR", fill=t["lbl_gray"],
                      font=("Helvetica", 8, "bold"), angle=90)

        # ── Grid lines (intersections = cols+1 vertical, rows+1 horizontal) ──
        # Vertical lines: A at x=stage_x0, last at x=stage_x1
        for ci in range(cols + 1):
            x = stage_x0 + ci * col_px
            c.create_line(x, stage_y0, x, stage_y1,
                          fill=t["dim_line"], width=1 if ci in (0, cols) else 1,
                          dash=() if ci in (0, cols) else (3, 4))

        # Horizontal lines: row1 at y=stage_y1, last at y=stage_y0
        for ri in range(rows + 1):
            y = stage_y0 + ri * row_py
            c.create_line(stage_x0, y, stage_x1, y,
                          fill=t["dim_line"], width=1 if ri in (0, rows) else 1,
                          dash=() if ri in (0, rows) else (3, 4))

        # ── Column letter labels on INTERSECTION lines ────────────────────────
        # Label sits above stage_y0, centred on each vertical line
        for ci in range(cols + 1):
            x = stage_x0 + ci * col_px
            lbl = chr(ord("A") + ci)
            c.create_text(x, stage_y0 - 5, text=lbl,
                          fill=t["accent"], font=("Helvetica", 8, "bold"),
                          anchor="s")

        # ── Row number labels on INTERSECTION lines ───────────────────────────
        # ri=0 = top of canvas = upstage → label rows+1
        # ri=rows = bottom of canvas = downstage/audience → label 1
        for ri in range(rows + 1):
            y = stage_y0 + ri * row_py
            row_num = rows - ri + 1  # ri=0 → rows+1 (upstage), ri=rows → 1 (downstage)
            c.create_text(stage_x0 - 4, y, text=str(row_num),
                          fill=t["accent"], font=("Helvetica", 8, "bold"),
                          anchor="e")

        # ── Intersection dot labels (e.g. "A1" at corner of stage) ───────────
        # Only draw corner labels to keep it uncluttered
        corners = [
            (0,    rows, "A1\n(Front SL)"),
            (cols, rows, f"{chr(ord('A')+cols)}1\n(Front SR)"),
            (0,    0,    f"A{rows+1}\n(Back SL)"),
            (cols, 0,    f"{chr(ord('A')+cols)}{rows+1}\n(Back SR)"),
        ]
        for ci, ri, lbl in corners:
            cx = stage_x0 + ci * col_px
            cy = stage_y0 + ri * row_py
            anchors = {(0, rows): "nw", (cols, rows): "ne",
                       (0, 0): "sw", (cols, 0): "se"}
            anch = anchors.get((ci, ri), "center")
            # Small offset so text doesn't overlap the border
            ox = 3 if "w" in anch else -3
            oy = 3 if "n" in anch else -3
            c.create_text(cx + ox, cy + oy, text=lbl,
                          fill=t["lbl_gray"], font=("Helvetica", 6),
                          anchor=anch, justify="center")

        # ── Stage border ─────────────────────────────────────────────────────
        c.create_rectangle(stage_x0, stage_y0, stage_x1, stage_y1,
                           outline=t["stage_lines"], width=2)

        # ── Dimension labels ──────────────────────────────────────────────────
        if self._is_imperial():
            w_label = f"{self._stage_w_mm/304.8:.1f} ft"
            d_label = f"{self._stage_d_mm/304.8:.1f} ft"
        else:
            w_label = f"{self._stage_w_mm/1000:.1f} m"
            d_label = f"{self._stage_d_mm/1000:.1f} m"
        c.create_text((stage_x0+stage_x1)//2, aud_y1 + 8,
                      text=f"◄─── {w_label} ───►",
                      fill=t["lbl_gray"], font=("Helvetica", 7, "italic"))
        c.create_text(stage_x0 - 22, (stage_y0+stage_y1)//2,
                      text=d_label, fill=t["lbl_gray"],
                      font=("Helvetica", 7, "italic"), angle=90)

        # ── Fixtures ─────────────────────────────────────────────────────────
        for i, e in enumerate(self.rig):
            px, py = self._world_to_canvas_grid(e["x_mm"], e["z_mm"],
                                                 stage_x0, stage_y0, sw, sh)
            is_hl  = (i == highlight)
            color  = t["accent"] if is_hl else t["accent2"]
            border = t["fg"]     if is_hl else t["border"]
            c.create_oval(px-r, py-r, px+r, py+r,
                          fill=color, outline=border, width=2 if is_hl else 1,
                          tags=(f"fx_{i}",))
            c.create_text(px, py, text=str(i+1),
                          fill=t["bg"], font=("Helvetica", 9, "bold"),
                          tags=(f"fxlbl_{i}",))
            grid_ref = self._mm_to_grid(e["x_mm"], e["z_mm"])
            y_mm     = e.get("y_mm", 0)
            h_role   = self._mm_to_height_role(y_mm)
            y_disp   = self._mm_to_display(y_mm)
            u        = "in" if self._is_imperial() else "mm"
            # Show role + grid ref + height role
            role_short = e.get("role", "")
            lbl    = f"{e['name']}\n{role_short} [{grid_ref}]  ↕{h_role}"
            # Place label above or below depending on position
            lbl_y  = py - r - 12 if py > (stage_y0 + stage_y1) // 2 else py + r + 12
            lbl_anchor = "s" if py > (stage_y0 + stage_y1) // 2 else "n"
            c.create_text(px, lbl_y, text=lbl,
                          fill=t["accent"] if is_hl else t["fg"],
                          font=("Helvetica", 7), justify="center",
                          anchor=lbl_anchor, tags=(f"fxname_{i}",))

        # ── Hint ─────────────────────────────────────────────────────────────
        c.create_text(stage_x0, aud_y1 + 18,
                      text="Drag to move  |  dbl-click table cells to edit  |  changing role snaps to intersection",
                      fill=t["lbl_gray"], font=("Helvetica", 7), anchor="w")

    def _world_to_canvas_grid(self, x_mm, z_mm, sx0, sy0, sw, sh):
        """Map world mm → canvas px within the given stage rect.
        x_mm=0 → left (SL), x_mm=stage_w → right (SR).
        z_mm=0 → top (upstage), z_mm=stage_d → bottom (downstage/audience).
        """
        px = sx0 + int(x_mm / self._stage_w_mm * sw)
        py = sy0 + int(z_mm / self._stage_d_mm * sh)
        return px, py

    def _draw_elevation_view(self, highlight=None, axis="front"):
        t   = THEMES[self.app.current_theme]
        c   = self.canvas
        r   = self._FX_RADIUS
        pad = self._CANVAS_PAD
        c.delete("all")

        stage_x0 = pad + 60   # room for tier labels
        stage_y0 = pad + 18
        stage_x1 = self._canvas_w - pad
        stage_y1 = self._canvas_h - pad - 20
        sw = stage_x1 - stage_x0
        sh = stage_y1 - stage_y0
        if sw <= 0 or sh <= 0:
            return

        n_tiers  = len(self._height_tiers)
        max_h_mm = max(self._height_tiers) + 500

        if axis == "front":
            n_h_cells = self._grid_cols
            h_labels  = [chr(ord("A") + i) for i in range(n_h_cells)]
            h_total   = self._stage_w_mm
            axis_title = f"FRONT ELEVATION  ({self._grid_cols} columns × {n_tiers} height tiers)"
        else:
            n_h_cells = self._grid_rows
            h_labels  = [str(i+1) for i in range(n_h_cells)]
            h_total   = self._stage_d_mm
            axis_title = f"SIDE ELEVATION  ({self._grid_rows} rows × {n_tiers} height tiers)"

        cell_px = sw / n_h_cells

        # Height tier bands
        tier_fills = [t["canvas_bg"], t["surface"]]
        for ti in range(n_tiers - 1):
            y0t = self._h_to_canvas(self._height_tiers[ti+1], stage_y0, stage_y1, max_h_mm)
            y1t = self._h_to_canvas(self._height_tiers[ti],   stage_y0, stage_y1, max_h_mm)
            c.create_rectangle(stage_x0, y0t, stage_x1, y1t,
                               fill=tier_fills[ti % 2], outline="")

        # Vertical grid lines
        for ci in range(n_h_cells + 1):
            x = stage_x0 + ci * cell_px
            c.create_line(x, stage_y0, x, stage_y1,
                          fill=t["grid_line"], width=1)

        # Height tier lines + labels
        for ti, h_mm in enumerate(self._height_tiers):
            y = self._h_to_canvas(h_mm, stage_y0, stage_y1, max_h_mm)
            c.create_line(stage_x0, y, stage_x1, y,
                          fill=t["stage_lines"], width=1, dash=(4, 3))
            lbl = self._height_labels[ti] if ti < len(self._height_labels) else f"{h_mm}mm"
            c.create_text(stage_x0 - 4, y, text=lbl,
                          fill=t["accent"], font=("Helvetica", 7), anchor="e")

        # Column/row letters
        for ci, lbl in enumerate(h_labels):
            x = stage_x0 + (ci + 0.5) * cell_px
            c.create_text(x, stage_y0 - 9, text=lbl,
                          fill=t["fg"], font=("Helvetica", 8, "bold"))

        # Stage border
        c.create_rectangle(stage_x0, stage_y0, stage_x1, stage_y1,
                           outline=t["stage_lines"], width=2)

        c.create_text((stage_x0+stage_x1)//2, stage_y1 + 12,
                      text=axis_title, fill=t["lbl_gray"],
                      font=("Helvetica", 8, "italic"))

        # Fixtures
        for i, e in enumerate(self.rig):
            y_mm = e.get("y_mm", 0)
            pos_mm = e["x_mm"] if axis == "front" else e["z_mm"]
            cell_idx = int(pos_mm / h_total * n_h_cells)
            cell_idx = max(0, min(n_h_cells - 1, cell_idx))
            px = int(stage_x0 + (cell_idx + 0.5) * cell_px)
            py = self._h_to_canvas(y_mm, stage_y0, stage_y1, max_h_mm)

            is_hl  = (i == highlight)
            color  = t["accent"] if is_hl else t["accent2"]
            border = t["fg"]     if is_hl else t["border"]
            c.create_oval(px-r, py-r, px+r, py+r,
                          fill=color, outline=border,
                          width=2 if is_hl else 1, tags=(f"fx_{i}",))
            c.create_text(px, py, text=str(i+1),
                          fill=t["bg"], font=("Helvetica", 9, "bold"),
                          tags=(f"fxlbl_{i}",))
            grid_ref = self._mm_to_grid(e["x_mm"], e["z_mm"])
            h_role   = self._mm_to_height_role(e.get("y_mm", 0))
            c.create_text(px, py - r - 8,
                          text=f"{e['name']}  {grid_ref}  ↕{h_role}",
                          fill=t["accent"] if is_hl else t["fg"],
                          font=("Helvetica", 7), justify="center",
                          tags=(f"fxname_{i}",))

    def _h_to_canvas(self, h_mm, y0, y1, max_h):
        frac = h_mm / max_h if max_h > 0 else 0
        return int(y1 - frac * (y1 - y0))

    def _on_canvas_press(self, event):
        idx = self._fixture_at(event.x, event.y)
        if idx is not None:
            if self._view_mode == "top":
                self._drag_idx = idx
                fx, fy = self._world_to_canvas(
                    self.rig[idx]["x_mm"], self.rig[idx]["z_mm"])
                self._drag_ox = event.x - fx
                self._drag_oy = event.y - fy
            # Highlight in table regardless of view
            children = self.tree.get_children()
            if idx < len(children):
                self.tree.selection_set(children[idx])
                self._draw_canvas(highlight=idx)

    def _best_role_for_position(self, x_mm, z_mm):
        """
        Return the named stage role whose canonical position is closest
        (Euclidean distance) to (x_mm, z_mm).  Falls back to 'Custom'.
        """
        named_roles = ["Front Left", "Front Center", "Front Right",
                       "Back Left",  "Back Center",  "Back Right",
                       "Side Left",  "Side Right",   "Center"]
        best_role = "Custom"
        best_dist = float("inf")
        for role in named_roles:
            coords = self._role_to_mm(role)
            if coords is None:
                continue
            rx, rz = coords
            dist = ((x_mm - rx) ** 2 + (z_mm - rz) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_role = role
        return best_role

    def _on_canvas_drag(self, event):
        if self._drag_idx is None:
            return
        x_mm, z_mm = self._canvas_to_world(
            event.x - self._drag_ox, event.y - self._drag_oy)
        e = self.rig[self._drag_idx]
        e["x_mm"] = x_mm
        e["z_mm"] = z_mm
        # Live-update role while dragging
        e["role"] = self._best_role_for_position(x_mm, z_mm)
        self._draw_canvas(highlight=self._drag_idx)

    def _on_canvas_release(self, event):
        if self._drag_idx is not None:
            e = self.rig[self._drag_idx]
            if self._snap_var.get():
                e["x_mm"], e["z_mm"] = self._snap_to_grid(e["x_mm"], e["z_mm"])
            # Final role assignment after snap
            e["role"] = self._best_role_for_position(e["x_mm"], e["z_mm"])
            self._refresh_tree()
        self._drag_idx = None

    # ══════════════════════════════════════════════════════════════════════════
    # TEMPLATE LOADING
    # ══════════════════════════════════════════════════════════════════════════
    def _load_template_dialog(self):
        path = filedialog.askopenfilename(
            title="Select Template QXW Workspace",
            filetypes=[("QLC+ Workspace", "*.qxw"), ("All Files", "*.*")]
        )
        if path:
            self._template_file = path
            self.lbl_template.config(
                text=f"template: {os.path.basename(path)}")
            self._set_info(f"Template set to: {os.path.basename(path)}")
            # Pre-populate rig from this template
            try:
                tree = ET.parse(path)
                self._import_fixtures_from_qxw(tree.getroot())
            except Exception as e:
                self._set_info(f"Template loaded (could not read fixtures: {e})")

    def _get_template_root(self):
        """Returns a deep-copy of the template XML root (from file or main workspace)."""
        if self._template_file and os.path.exists(self._template_file):
            tree = ET.parse(self._template_file)
            return copy.deepcopy(tree.getroot())
        elif self.app.qxw_root is not None:
            return copy.deepcopy(self.app.qxw_root)
        return None

    # ══════════════════════════════════════════════════════════════════════════
    # QXW GENERATION CORE
    # ══════════════════════════════════════════════════════════════════════════
    def _generate_qxw(self):
        if not self.rig:
            messagebox.showwarning("Empty Rig", "Add at least one fixture before generating.")
            return

        root = self._get_template_root()
        if root is None:
            messagebox.showwarning("No Template",
                                   "Load a template .qxw workspace first (or load one "
                                   "in the main toolbar).")
            return

        try:
            new_root = self._build_qxw(root)
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            messagebox.showerror("Generation Error", f"Failed to generate QXW:\n{e}")
            return

        # Save dialog
        default_name = "rig_" + datetime.date.today().strftime("%Y%m%d") + ".qxw"
        save_path = filedialog.asksaveasfilename(
            title="Save Generated QXW",
            initialfile=default_name,
            filetypes=[("QLC+ Workspace", "*.qxw"), ("All Files", "*.*")],
            defaultextension=".qxw"
        )
        if not save_path:
            return

        try:
            xml_str = ET.tostring(new_root, encoding="utf-8").decode("utf-8")
            with open(save_path, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<!DOCTYPE Workspace>\n' + xml_str)
            messagebox.showinfo("Success",
                                f"QXW generated and saved to:\n{os.path.basename(save_path)}")
            self._set_info(f"Generated: {os.path.basename(save_path)}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not write file:\n{e}")

    def _build_qxw(self, template_root):
        """
        Core logic: rebuild the Engine's Fixture / FixtureGroup blocks and
        adapt all Function FixtureVal entries to the new fixture count.
        """
        QWS_NS = QLC_NS_URI
        ns     = NS
        root   = template_root

        engine = root.find("q:Engine", ns)
        if engine is None:
            raise ValueError("Template has no <Engine> element.")

        # ── 1. Determine old fixture count from template ───────────────────
        old_fixtures = engine.findall("q:Fixture", ns)
        old_count    = len(old_fixtures)
        new_count    = len(self.rig)

        # Collect old fixture IDs in order (for function remapping)
        old_ids = []
        for fx in old_fixtures:
            id_node = fx.find("q:ID", ns)
            old_ids.append(id_node.text if id_node is not None else "?")

        # ── 2. Remove existing Fixture elements ───────────────────────────
        for fx in old_fixtures:
            engine.remove(fx)

        # ── 3. Remove existing FixtureGroup elements ─────────────────────
        for fg in engine.findall("q:FixtureGroup", ns):
            engine.remove(fg)

        # ── 4. Insert new Fixture elements ────────────────────────────────
        # Find the insertion point: after InputOutputMap
        iom = engine.find("q:InputOutputMap", ns)
        insert_after = list(engine).index(iom) + 1 if iom is not None else 0

        for i, e in enumerate(self.rig):
            fx_el = ET.Element(f"{{{QWS_NS}}}Fixture")
            _sub  = lambda tag, text: ET.SubElement(
                fx_el, f"{{{QWS_NS}}}{tag}").text.__setattr__  # noqa: helper

            def sub(tag, text, parent=fx_el):
                el = ET.SubElement(parent, f"{{{QWS_NS}}}{tag}")
                el.text = str(text)
                return el

            sub("Manufacturer", e["manufacturer"])
            sub("Model",        e["model"])
            sub("Mode",         e["mode"])
            sub("ID",           str(i))
            sub("Name",         e["name"])
            sub("Universe",     str(e["universe"]))
            sub("Address",      str(e["address"]))
            sub("Channels",     str(e["ch_count"]))
            engine.insert(insert_after + i, fx_el)

        # ── 5. Build a single FixtureGroup with all fixtures ──────────────
        fg_el = ET.SubElement(engine, f"{{{QWS_NS}}}FixtureGroup")
        fg_el.set("ID", "0")
        name_el = ET.SubElement(fg_el, f"{{{QWS_NS}}}Name")
        name_el.text = ""
        size_el = ET.SubElement(fg_el, f"{{{QWS_NS}}}Size")
        size_el.set("X", str(new_count))
        size_el.set("Y", "1")
        for i in range(new_count):
            head_el = ET.SubElement(fg_el, f"{{{QWS_NS}}}Head")
            head_el.set("X", str(i))
            head_el.set("Y", "0")
            head_el.set("Fixture", str(i))
            head_el.text = "0"

        # ── 6. Adapt Function FixtureVal entries using assignments ────────
        #   self._func_assignments[func_id] = flat list of rig fixture indices.
        #   The first N entries correspond to the N template slots in order.
        #   Extra entries broadcast the same channel values to additional fixtures.

        for func in engine.findall("q:Function", ns):
            func_id   = func.get("ID")
            old_vals  = func.findall("q:FixtureVal", ns)
            if not old_vals:
                continue

            # Ordered list of (template_slot_id, val_text)
            old_slot_vals = []
            for fv in old_vals:
                fv_id = int(fv.get("ID", "0"))
                old_slot_vals.append((fv_id, fv.text or ""))
                func.remove(fv)
            n_slots = len(old_slot_vals)

            assignment = self._func_assignments.get(func_id, list(range(new_count)))

            for rig_pos, rig_fixture_idx in enumerate(assignment):
                if rig_fixture_idx >= new_count:
                    continue
                tmpl_slot = rig_pos % n_slots if n_slots > 0 else 0
                if tmpl_slot < len(old_slot_vals):
                    _, val_text = old_slot_vals[tmpl_slot]
                else:
                    val_text = ""
                fv_new = ET.SubElement(func, f"{{{QWS_NS}}}FixtureVal")
                fv_new.set("ID", str(rig_fixture_idx))
                fv_new.text = val_text

        # ── 7. Update Monitor FxItem positions + stage dimensions ─────────
        monitor = root.find(".//q:Monitor", ns)
        if monitor is not None:
            # Update Grid stage dimensions
            grid_el = monitor.find(f"{{{QWS_NS}}}Grid")
            if grid_el is None:
                grid_el = ET.SubElement(monitor, f"{{{QWS_NS}}}Grid")
            grid_el.set("Width",  str(int(self._stage_w_mm / 1000)))
            grid_el.set("Height", str(int(self._stage_h_mm / 1000)))
            grid_el.set("Depth",  str(int(self._stage_d_mm / 1000)))
            grid_el.set("Units",  "0")

            for fxi in monitor.findall(f"{{{QWS_NS}}}FxItem"):
                monitor.remove(fxi)

            for i, e in enumerate(self.rig):
                fxi = ET.SubElement(monitor, f"{{{QWS_NS}}}FxItem")
                fxi.set("ID",   str(i))
                fxi.set("XPos", str(int(e["x_mm"])))
                fxi.set("YPos", str(int(e.get("y_mm", 0))))
                fxi.set("ZPos", str(int(e["z_mm"])))
                fxi.set("XRot", "65")
                fxi.set("YRot", "0")
                fxi.set("ZRot", "0")

        # ── 8. Update VC Sliders ──────────────────────────────────────────
        vc = root.find("q:VirtualConsole", ns)
        if vc is not None:
            self._update_vc_sliders(vc, new_count)

        return root

    def _update_vc_sliders(self, vc_node, new_count):
        """
        For each Slider in Level mode, rebuild the Channel sub-elements to
        cover all new_count fixtures (preserving the channel number pattern
        from the existing entries).
        """
        ns = NS
        QWS_NS = QLC_NS_URI

        for slider in vc_node.iter(f"{{{QWS_NS}}}Slider"):
            level_el = slider.find(f"{{{QWS_NS}}}Level")
            if level_el is None:
                continue
            old_channels = level_el.findall(f"{{{QWS_NS}}}Channel")
            if not old_channels:
                continue

            # Collect unique channel numbers from old entries
            ch_nums = list(dict.fromkeys(
                int(ch.get("Channel", ch.text or "0"))
                for ch in old_channels
            ))
            # Remove old channel entries
            for ch in old_channels:
                level_el.remove(ch)
            # Add new entries for all new fixtures × those channel numbers
            for fix_i in range(new_count):
                for ch_num in ch_nums:
                    ch_el = ET.SubElement(level_el, f"{{{QWS_NS}}}Channel")
                    ch_el.set("Fixture", str(fix_i))
                    ch_el.text = str(ch_num)

    # ══════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════════════
    def _set_info(self, msg):
        self.lbl_info.config(text=msg)


# ██████████████████████████████████████████████████████████████████████████████
#  FUNCTION ASSIGNMENT PANEL (used inside FixtureConfiguratorTab)
# ██████████████████████████████████████████████████████████████████████████████

class FunctionAssignPanel(tk.Frame):
    """
    Collapsible panel below the stage canvas that shows all functions from the
    template and lets you edit which rig fixtures are assigned to each one.

    Layout (when expanded):
    ┌─────────────────────────────────────────────────────────────┐
    │ ▼ Function Assignments  [Auto-Assign All]  [?] legend        │
    ├────────────────────────┬────────────────────────────────────┤
    │ Function list (left)   │  Fixture slot editor (right)       │
    │  Type  Name  #slots    │  Slot 0 → [combobox: Par 1]        │
    │  ...                   │  Slot 1 → [combobox: Par 2]        │
    │                        │  Slot 2 → [combobox: Par 3]  ...   │
    │                        │  ─────────────────────────────     │
    │                        │  Dictionary description (italic)   │
    └────────────────────────┴────────────────────────────────────┘
    """

    _TYPE_ICONS = {
        'Scene':     '🎨',
        'Chaser':    '▶',
        'RGBMatrix': '🌈',
        'Collection':'📦',
    }

    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.cfg = cfg   # FixtureConfiguratorTab reference
        self._expanded = True
        self._selected_func_id = None
        self._slot_combos = []   # list of (label_widget, combo_widget, slot_idx)
        self._build_ui()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        t = THEMES[self.cfg.app.current_theme]
        self.configure(bg=t["bg"])

        # ── Header row ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=t["border"], height=1)
        hdr.pack(fill=tk.X, pady=(4, 0))

        self._hdr_btn = tk.Label(
            self, text="▼  Function Assignments",
            font=("Helvetica", 10, "bold"),
            cursor="hand2", bg=t["bg"], fg=t["accent"])
        self._hdr_btn.pack(anchor="w", padx=10, pady=(2, 2))
        self._hdr_btn.bind("<Button-1>", self._toggle)

        self._hdr_hint = tk.Label(
            self,
            text="Shows which rig fixtures are assigned to each Scene/RGBMatrix. "
                 "Click a function to edit its slot→fixture mapping.",
            font=("Helvetica", 8, "italic"),
            bg=t["bg"], fg=t["lbl_gray"], anchor="w")
        self._hdr_hint.pack(fill=tk.X, padx=14, pady=(0, 4))

        # ── Body (collapsible) ────────────────────────────────────────────────
        self._body = tk.Frame(self, bg=t["bg"])
        self._body.pack(fill=tk.BOTH, expand=True)

        # Toolbar
        tb = tk.Frame(self._body, bg=t["bg"], padx=6, pady=2)
        tb.pack(fill=tk.X)
        ttk.Button(tb, text="⚡ Auto-Assign All",
                   command=self._auto_assign_all,
                   style="Normal.TButton").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(tb, text="↺ Reset This",
                   command=self._reset_selected,
                   style="Normal.TButton").pack(side=tk.LEFT, padx=(0, 6))
        self._lbl_count = tk.Label(tb, text="", font=("Helvetica", 8, "italic"),
                                   bg=t["bg"], fg=t["lbl_gray"])
        self._lbl_count.pack(side=tk.LEFT)

        # Split pane
        pane = tk.PanedWindow(self._body, orient=tk.HORIZONTAL,
                              sashwidth=5, bg=t["bg"])
        pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))

        # Left: function list
        left = tk.Frame(pane, bg=t["bg"])
        pane.add(left, minsize=360)

        func_cols = ("Icon", "Name", "Slots", "Assigned")
        self._func_tree = ttk.Treeview(left, columns=func_cols,
                                        show="headings", selectmode="browse",
                                        height=8)
        self._func_tree.heading("Icon",     text="")
        self._func_tree.heading("Name",     text="Function")
        self._func_tree.heading("Slots",    text="Tmpl")
        self._func_tree.heading("Assigned", text="→ Rig fixtures")
        self._func_tree.column("Icon",     width=26,  anchor="center", stretch=False)
        self._func_tree.column("Name",     width=220, anchor="w")
        self._func_tree.column("Slots",    width=40,  anchor="center", stretch=False)
        self._func_tree.column("Assigned", width=180, anchor="w")
        vsb_f = ttk.Scrollbar(left, orient="vertical",
                               command=self._func_tree.yview)
        self._func_tree.configure(yscrollcommand=vsb_f.set)
        self._func_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb_f.pack(side=tk.LEFT, fill=tk.Y)
        self._func_tree.bind("<<TreeviewSelect>>", self._on_func_select)

        # Right: slot editor + description
        right = tk.Frame(pane, bg=t["bg"])
        pane.add(right, minsize=280)

        self._right_title = tk.Label(
            right, text="← Select a function to edit its fixture assignment",
            font=("Helvetica", 9, "italic"),
            bg=t["bg"], fg=t["lbl_gray"], anchor="w", wraplength=280)
        self._right_title.pack(fill=tk.X, padx=6, pady=(4, 2))

        # Scrollable slot area
        slot_outer = tk.Frame(right, bg=t["bg"])
        slot_outer.pack(fill=tk.BOTH, expand=True, padx=6)
        slot_vsb = ttk.Scrollbar(slot_outer, orient="vertical")
        slot_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._slot_canvas = tk.Canvas(slot_outer, bg=t["surface"],
                                       highlightthickness=0,
                                       yscrollcommand=slot_vsb.set)
        self._slot_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        slot_vsb.configure(command=self._slot_canvas.yview)
        self._slot_frame = tk.Frame(self._slot_canvas, bg=t["surface"])
        self._slot_frame_id = self._slot_canvas.create_window(
            (0, 0), window=self._slot_frame, anchor="nw")
        self._slot_frame.bind("<Configure>", self._on_slot_frame_configure)
        self._slot_canvas.bind("<Configure>", self._on_slot_canvas_configure)

        # Description label
        self._desc_label = tk.Label(
            right, text="", font=("Helvetica", 8, "italic"),
            bg=t["bg"], fg=t["lbl_gray"],
            anchor="w", justify="left", wraplength=280)
        self._desc_label.pack(fill=tk.X, padx=6, pady=(4, 4))

    def _on_slot_frame_configure(self, event=None):
        self._slot_canvas.configure(
            scrollregion=self._slot_canvas.bbox("all"))

    def _on_slot_canvas_configure(self, event=None):
        self._slot_canvas.itemconfig(
            self._slot_frame_id, width=event.width if event else 200)

    # ── Theme ─────────────────────────────────────────────────────────────────
    def on_theme_changed(self):
        t = THEMES[self.cfg.app.current_theme]
        self.configure(bg=t["bg"])
        self._hdr_btn.configure(bg=t["bg"], fg=t["accent"])
        self._hdr_hint.configure(bg=t["bg"], fg=t["lbl_gray"])
        self._body.configure(bg=t["bg"])
        self._lbl_count.configure(bg=t["bg"], fg=t["lbl_gray"])
        self._right_title.configure(bg=t["bg"], fg=t["lbl_gray"])
        self._desc_label.configure(bg=t["bg"], fg=t["lbl_gray"])
        self._slot_canvas.configure(bg=t["surface"])
        self._slot_frame.configure(bg=t["surface"])

    # ── Collapse/expand ───────────────────────────────────────────────────────
    def _toggle(self, event=None):
        if self._expanded:
            self._body.pack_forget()
            self._hdr_hint.pack_forget()
            self._hdr_btn.config(text="▶  Function Assignments  (click to expand)")
        else:
            self._hdr_btn.config(text="▼  Function Assignments")
            self._hdr_hint.pack(fill=tk.X, padx=14, pady=(0, 4))
            self._body.pack(fill=tk.BOTH, expand=True)
        self._expanded = not self._expanded

    # ── Populate ──────────────────────────────────────────────────────────────
    def refresh(self):
        """Rebuild the function list from cfg._template_funcs."""
        t = THEMES[self.cfg.app.current_theme]
        self._func_tree.delete(*self._func_tree.get_children())

        funcs = self.cfg._template_funcs
        assignments = self.cfg._func_assignments

        for tf in funcs:
            icon    = self._TYPE_ICONS.get(tf['type'], '•')
            n_slots = len(tf['slots'])
            assign  = assignments.get(tf['id'], [])
            # Short rig names for the assigned column
            rig_names = []
            for ri in assign:
                if 0 <= ri < len(self.cfg.rig):
                    rig_names.append(self.cfg.rig[ri]['name'])
            assigned_str = ", ".join(rig_names[:4])
            if len(rig_names) > 4:
                assigned_str += f" +{len(rig_names)-4}"

            self._func_tree.insert("", "end", iid=tf['id'], values=(
                icon, tf['name'], n_slots or "—", assigned_str
            ))

        n = len(funcs)
        self._lbl_count.config(text=f"{n} function(s) in template")

        # Re-select if possible
        if self._selected_func_id:
            try:
                self._func_tree.selection_set(self._selected_func_id)
                self._populate_slots(self._selected_func_id)
            except Exception:
                self._selected_func_id = None

    def _on_func_select(self, event=None):
        sel = self._func_tree.selection()
        if not sel:
            return
        fid = sel[0]
        self._selected_func_id = fid
        self._populate_slots(fid)

    def _populate_slots(self, func_id):
        """Build the slot→fixture comboboxes for the selected function."""
        t  = THEMES[self.cfg.app.current_theme]

        # Find function info
        tf = next((f for f in self.cfg._template_funcs if f['id'] == func_id), None)
        if tf is None:
            return

        # Update title + description
        icon = self._TYPE_ICONS.get(tf['type'], '•')
        self._right_title.config(
            text=f"{icon}  {tf['name']}  ({tf['type']})",
            fg=t["fg"])
        desc = tf.get('desc', '')
        self._desc_label.config(
            text=f"📖  {desc}" if desc else "No description in dictionary.")

        # Clear old slot widgets
        for w in self._slot_frame.winfo_children():
            w.destroy()
        self._slot_combos.clear()

        assignment = list(self.cfg._func_assignments.get(func_id, []))
        rig_names = [e['name'] for e in self.cfg.rig] if self.cfg.rig else ["(no fixtures)"]
        none_opt = "— unassigned —"
        combo_values = [none_opt] + rig_names

        n_slots = len(tf['slots'])
        if n_slots == 0:
            # Chaser / Collection: just show which fixtures are "in scope"
            n_slots = max(1, len(self.cfg.rig))

        # Header row
        hdr_frame = tk.Frame(self._slot_frame, bg=t["surface"])
        hdr_frame.pack(fill=tk.X, padx=4, pady=(4, 2))
        tk.Label(hdr_frame, text="Slot", width=6,
                 font=("Helvetica", 8, "bold"),
                 bg=t["surface"], fg=t["lbl_gray"]).pack(side=tk.LEFT)
        tk.Label(hdr_frame, text="Template fixture",
                 font=("Helvetica", 8, "bold"), width=16,
                 bg=t["surface"], fg=t["lbl_gray"]).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(hdr_frame, text="→ Assign to rig fixture",
                 font=("Helvetica", 8, "bold"),
                 bg=t["surface"], fg=t["lbl_gray"]).pack(side=tk.LEFT)

        # One row per slot
        tmpl_fixture_map = self.cfg.app.fixture_map  # id→{name,...}

        for slot_i in range(n_slots):
            slot_id = tf['slots'][slot_i] if slot_i < len(tf['slots']) else None
            tmpl_name = ""
            if slot_id is not None:
                tmpl_info = tmpl_fixture_map.get(slot_id, {})
                tmpl_name = tmpl_info.get('name', f'#{slot_id}')

            # Current assignment
            cur_rig_idx = assignment[slot_i] if slot_i < len(assignment) else None

            row_frame = tk.Frame(self._slot_frame, bg=t["surface"])
            row_frame.pack(fill=tk.X, padx=4, pady=1)

            tk.Label(row_frame, text=f"#{slot_i+1}", width=4,
                     font=("Helvetica", 9, "bold"),
                     bg=t["surface"], fg=t["accent"]).pack(side=tk.LEFT)
            tk.Label(row_frame,
                     text=tmpl_name if tmpl_name else "(none)",
                     width=16, anchor="w",
                     font=("Helvetica", 8),
                     bg=t["surface"], fg=t["fg"]).pack(side=tk.LEFT, padx=(0, 4))

            var = tk.StringVar()
            if cur_rig_idx is not None and 0 <= cur_rig_idx < len(rig_names):
                var.set(rig_names[cur_rig_idx])
            else:
                var.set(none_opt)

            cb = ttk.Combobox(row_frame, textvariable=var,
                               values=combo_values, state="readonly", width=22)
            cb.pack(side=tk.LEFT)

            def make_callback(fi=func_id, si=slot_i, v=var):
                def cb_changed(event=None):
                    self._on_slot_changed(fi, si, v.get())
                return cb_changed

            cb.bind("<<ComboboxSelected>>", make_callback())
            self._slot_combos.append((slot_i, var, cb))

        # "Extra fixtures" section (rig fixtures beyond the slot count)
        extra_start = n_slots
        n_rig = len(self.cfg.rig)
        if n_rig > extra_start:
            sep = tk.Label(self._slot_frame,
                           text=f"── Additional rig fixtures (broadcast: inherit slot values cyclically) ──",
                           font=("Helvetica", 7, "italic"),
                           bg=t["surface"], fg=t["lbl_gray"])
            sep.pack(fill=tk.X, padx=4, pady=(6, 2))
            for slot_i in range(extra_start, n_rig):
                cur_rig_idx = assignment[slot_i] if slot_i < len(assignment) else slot_i
                row_frame = tk.Frame(self._slot_frame, bg=t["surface"])
                row_frame.pack(fill=tk.X, padx=4, pady=1)
                tk.Label(row_frame, text=f"#{slot_i+1}", width=4,
                         font=("Helvetica", 9), fg=t["lbl_gray"],
                         bg=t["surface"]).pack(side=tk.LEFT)
                tk.Label(row_frame, text="(extra)", width=16, anchor="w",
                         font=("Helvetica", 8, "italic"),
                         fg=t["lbl_gray"], bg=t["surface"]).pack(side=tk.LEFT, padx=(0, 4))
                var = tk.StringVar()
                if 0 <= cur_rig_idx < len(rig_names):
                    var.set(rig_names[cur_rig_idx])
                else:
                    var.set(none_opt)
                cb = ttk.Combobox(row_frame, textvariable=var,
                                   values=combo_values, state="readonly", width=22)
                cb.pack(side=tk.LEFT)

                def make_extra_cb(fi=func_id, si=slot_i, v=var):
                    def _changed(event=None):
                        self._on_slot_changed(fi, si, v.get())
                    return _changed

                cb.bind("<<ComboboxSelected>>", make_extra_cb())

        self._slot_canvas.yview_moveto(0)

    def _on_slot_changed(self, func_id, slot_idx, rig_name):
        """Update _func_assignments when user picks a different rig fixture."""
        none_opt = "— unassigned —"
        if rig_name == none_opt:
            new_rig_idx = -1
        else:
            new_rig_idx = next(
                (i for i, e in enumerate(self.cfg.rig) if e['name'] == rig_name), -1)

        assign = list(self.cfg._func_assignments.get(func_id, []))
        # Extend if needed
        while len(assign) <= slot_idx:
            assign.append(len(assign) % max(1, len(self.cfg.rig)))
        assign[slot_idx] = new_rig_idx
        self.cfg._func_assignments[func_id] = assign

        # Refresh the assigned column in the function list
        rig_names = [self.cfg.rig[ri]['name']
                     for ri in assign if 0 <= ri < len(self.cfg.rig)]
        assigned_str = ", ".join(rig_names[:4])
        if len(rig_names) > 4:
            assigned_str += f" +{len(rig_names)-4}"
        try:
            tf = next(f for f in self.cfg._template_funcs if f['id'] == func_id)
            self._func_tree.item(func_id, values=(
                self._TYPE_ICONS.get(tf['type'], '•'),
                tf['name'],
                len(tf['slots']) or "—",
                assigned_str
            ))
        except (StopIteration, Exception):
            pass

    def _auto_assign_all(self):
        """Re-run the default proximity-based assignment for all functions."""
        root = self.cfg._get_template_root()
        if root is None:
            messagebox.showwarning("No Template", "Load a template QXW first.")
            return
        self.cfg._build_default_assignments(root)
        self.refresh()
        if self._selected_func_id:
            self._populate_slots(self._selected_func_id)

    def _reset_selected(self):
        """Reset just the selected function's assignment."""
        if not self._selected_func_id:
            return
        root = self.cfg._get_template_root()
        if root is None:
            return
        # Re-run just for this function
        tf = next((f for f in self.cfg._template_funcs
                   if f['id'] == self._selected_func_id), None)
        if tf is None:
            return
        # Sequential fallback
        n = len(self.cfg.rig)
        self.cfg._func_assignments[self._selected_func_id] = list(range(n))
        self.refresh()
        self._populate_slots(self._selected_func_id)


# ██████████████████████████████████████████████████████████████████████████████
#  ENTRY POINT
# ██████████████████████████████████████████████████████████████████████████████

if __name__ == "__main__":
    root = tk.Tk()
    app = QLCSwissKnife(root)

    # Handle window resize for blueprint canvas
    def _on_resize(event):
        if event.widget == root:
            if hasattr(app.setup_mgr, '_resize_timer') and app.setup_mgr._resize_timer:
                root.after_cancel(app.setup_mgr._resize_timer)
            app.setup_mgr._resize_timer = root.after(300, app.setup_mgr.draw_plots)

    root.bind("<Configure>", _on_resize)
    root.mainloop()
