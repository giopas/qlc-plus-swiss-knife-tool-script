#!/usr/bin/env python3
"""
================================================================================
  QLC+ SWISS KNIFE — Unified Live Console Toolkit (v0.4)
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
            g_name = g_name_node.text if g_name_node is not None else f"Group {g_id}"
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
            f_name = f_name.text if f_name is not None else f"Fixture {f_id}"

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
            self._parse_vc_node(vc_root, "Virtual Console")

    def _parse_vc_node(self, node, current_frame="[No Frame]"):
        tag_name = node.tag.replace(f"{{{QLC_NS_URI}}}", "")

        if tag_name in ["Frame", "SoloFrame"]:
            current_frame = node.get('Caption', current_frame)
            self.available_frames.add(current_frame)

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
                    self.vc_buttons[f_id]['frames'].add(current_frame)

        for child in node:
            self._parse_vc_node(child, current_frame)

    def set_status(self, msg):
        self.lbl_status.config(text=msg)


# ██████████████████████████████████████████████████████████████████████████████
#  TAB 1 — SETLIST MANAGER
# ██████████████████████████████████████████████████████████████████████████████

class SetlistManagerTab:
    def __init__(self, parent, app: QLCSwissKnife):
        self.parent = parent
        self.app = app

        self.setlist_data = []
        self.current_txt_file = ""
        self.current_desc_file = ""

        self._build_ui()

    def _build_ui(self):
        # ── Top bar: TXT + Desc loading ───────────────────────────────────────
        top = tk.Frame(self.parent, padx=10, pady=6)
        top.pack(fill=tk.X)

        ttk.Button(top, text="📄 Load Setlist TXT",
                   command=self.load_txt_dialog, style="Normal.TButton").pack(side=tk.LEFT)
        self.lbl_txt = tk.Label(top, text="No setlist", font=("Helvetica", 9, "bold"))
        self.lbl_txt.pack(side=tk.LEFT, padx=(5, 15))

        ttk.Button(top, text="📄 Load Dictionary TXT",
                   command=self.load_desc_dialog, style="Normal.TButton").pack(side=tk.LEFT)
        self.lbl_desc = tk.Label(top, text="No dictionary", font=("Helvetica", 9, "bold"))
        self.lbl_desc.pack(side=tk.LEFT, padx=(5, 15))

        # Chaser target
        tk.Label(top, text="Target Chaser:", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=(20, 4))
        self.chaser_var = tk.StringVar(value="[ Create New Master Chaser ]")
        self.combo_chaser = ttk.Combobox(top, textvariable=self.chaser_var,
                                         state="readonly", width=32, font=("Helvetica", 9))
        self.combo_chaser.pack(side=tk.LEFT, padx=(0, 8))
        self.combo_chaser.bind("<<ComboboxSelected>>", self.on_chaser_change)

        self.enforce_naming_var = tk.BooleanVar(value=False)
        chk_enforce = ttk.Checkbutton(top, text="Enforce VC Naming",
                        variable=self.enforce_naming_var)
        chk_enforce.pack(side=tk.LEFT, padx=8)
        ToolTip(chk_enforce,
                "When checked, on SAVE the script renames all base pool "
                "functions to match their Virtual Console button captions.\n\n"
                "Unassigned functions get tagged as '[ID] Type - Unassigned'.\n"
                "This keeps your QLC+ pool tidy but modifies original names.")

        ttk.Button(top, text="🧹 Find Orphans",
                   command=self.find_orphans, style="Normal.TButton").pack(side=tk.RIGHT)

        # ── Main split ────────────────────────────────────────────────────────
        main = tk.Frame(self.parent, padx=10, pady=4)
        main.pack(fill=tk.BOTH, expand=True)

        # LEFT — Setlist
        left = tk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(left, text="🎵 Setlist Cue Order",
                 font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(0, 4))

        cols_l = ("#", "Song (TXT)", "ID", "QLC+ Cue", "In", "Hold", "Out")
        self.tree_left = ttk.Treeview(left, columns=cols_l, show="headings",
                                       selectmode="browse")
        widths_l = [32, 160, 40, 200, 50, 50, 50]
        for col, w in zip(cols_l, widths_l):
            self.tree_left.heading(col, text=col)
            self.tree_left.column(col, width=w,
                                  anchor="center" if w <= 50 else "w")
        self.tree_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Scrollbar(left, orient="vertical",
                      command=self.tree_left.yview).pack(side=tk.LEFT, fill=tk.Y)
        self.tree_left.config(yscrollcommand=lambda *a: None)  # linked below
        self.tree_left.bind("<<TreeviewSelect>>", self.on_left_select)

        # MIDDLE — Actions
        mid = tk.Frame(main, padx=8)
        mid.pack(side=tk.LEFT, fill=tk.Y)
        tk.Frame(mid, height=80).pack()
        ttk.Button(mid, text="◀ ASSIGN", command=self.assign_cue,
                   style="Assign.TButton").pack(pady=6, ipady=4, fill=tk.X)
        ttk.Button(mid, text="Unassign", command=self.unassign_cue,
                   style="Danger.TButton").pack(pady=4, fill=tk.X)
        ttk.Button(mid, text="✕ Delete", command=self.delete_item,
                   style="Danger.TButton").pack(pady=12, fill=tk.X)
        ttk.Button(mid, text="▲ Up", command=self.move_up,
                   style="Normal.TButton").pack(pady=4, fill=tk.X)
        ttk.Button(mid, text="▼ Down", command=self.move_down,
                   style="Normal.TButton").pack(pady=4, fill=tk.X)

        # RIGHT — Pool
        right = tk.Frame(main)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)

        rtop = tk.Frame(right)
        rtop.pack(fill=tk.X, pady=(0, 4))

        tk.Label(rtop, text="🎛 QLC+ Function Pool",
                 font=("Helvetica", 10, "bold")).pack(side=tk.LEFT)

        tk.Label(rtop, text="Search:", font=("Helvetica", 8)).pack(side=tk.LEFT, padx=(12, 2))
        self.search_var = tk.StringVar()
        ttk.Entry(rtop, textvariable=self.search_var, width=14).pack(side=tk.LEFT)
        self.search_var.trace_add("write", lambda *a: self.populate_right_tree())

        self.frame_filter_var = tk.StringVar(value="All Frames")
        self.combo_frame_filter = ttk.Combobox(rtop, textvariable=self.frame_filter_var,
                                                state="readonly", width=16)
        self.combo_frame_filter.pack(side=tk.RIGHT, padx=4)
        self.combo_frame_filter.bind("<<ComboboxSelected>>", lambda e: self.populate_right_tree())
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

        tree_c = tk.Frame(right)
        tree_c.pack(fill=tk.BOTH, expand=True)

        cols_r = ("ID", "Contains", "Uses", "VC Button", "Description")
        self.tree_right = ttk.Treeview(tree_c, columns=cols_r, selectmode="browse")
        self.tree_right.heading("#0", text="Function Name")
        for c in cols_r:
            self.tree_right.heading(c, text=c)
        self.tree_right.column("#0", width=200, minwidth=180)
        self.tree_right.column("ID", width=48, anchor="center")
        self.tree_right.column("Contains", width=65, anchor="center")
        self.tree_right.column("Uses", width=50, anchor="center")
        self.tree_right.column("VC Button", width=140, anchor="w")
        self.tree_right.column("Description", width=300, anchor="w")

        ttk.Scrollbar(tree_c, orient="vertical",
                      command=self.tree_right.yview).pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ── Bottom bar ────────────────────────────────────────────────────────
        bottom = tk.Frame(self.parent, padx=10, pady=8)
        bottom.pack(fill=tk.X)

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

        ttk.Button(bottom, text="💾 SAVE & GENERATE CLONES",
                   command=self.save_qxw, style="Save.TButton").pack(
            side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 0), ipady=6)
        ttk.Button(bottom, text="🖨️ PDF",
                   command=self.export_setlist_pdf, style="Export.TButton").pack(
            side=tk.RIGHT, padx=(8, 0), ipady=6)
        ttk.Button(bottom, text="📝 Dict",
                   command=self.export_dictionary, style="Export.TButton").pack(
            side=tk.RIGHT, padx=(8, 0), ipady=6)
        ttk.Button(bottom, text="📄 XML TXT",
                   command=self.export_txt, style="Export.TButton").pack(
            side=tk.RIGHT, padx=(8, 0), ipady=6)

    # ── Callbacks from shell ──────────────────────────────────────────────────
    def on_qxw_loaded(self):
        self.combo_frame_filter['values'] = ["All Frames"] + sorted(list(self.app.available_frames))
        self.frame_filter_var.set("All Frames")
        self.populate_right_tree()
        self.update_chaser_dropdown()

    def on_theme_changed(self):
        t = THEMES[self.app.current_theme]
        self.tree_left.tag_configure("missing", foreground=t["missing"], background=t["tree_bg"])
        self.tree_left.tag_configure("ok", foreground=t["tree_fg"], background=t["tree_bg"])
        self.tree_right.tag_configure("used", foreground=t["lbl_green"])

    # ── Descriptions ──────────────────────────────────────────────────────────
    def load_desc_dialog(self):
        fn = filedialog.askopenfilename(title="Select Descriptions TXT",
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
            # Sync to Dictionary tab: data + label
            self.app.dict_mgr.sync_from_shared_descriptions()
            self.app.dict_mgr.current_txt_file = filename
            self.app.dict_mgr.lbl_txt.config(text=os.path.basename(filename))
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            messagebox.showerror("Error", f"Failed to load Descriptions:\n{e}")

    # ── Setlist loading ───────────────────────────────────────────────────────
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
                match_name, match_id = self.find_best_match(line)
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

    def find_best_match(self, query):
        fbn = self.app.func_by_name
        if not fbn:
            return "", ""
        if query in fbn:
            return query, fbn[query]
        q_lower = query.lower()
        matches = [(n, i) for n, i in fbn.items() if q_lower in n.lower()]
        if len(matches) == 1:
            return matches[0]
        trans = str.maketrans(string.punctuation, ' ' * len(string.punctuation))
        q_tokens = set(query.translate(trans).lower().split())
        best, best_id, max_ov = "", "", 0
        for name, fid in fbn.items():
            ov = len(q_tokens.intersection(set(name.translate(trans).lower().split())))
            if ov > max_ov:
                max_ov, best, best_id = ov, name, fid
        mn = min(2, len(q_tokens)) if q_tokens else 1
        if max_ov >= mn:
            return best, best_id
        if matches:
            return matches[0]
        close = difflib.get_close_matches(q_lower, [n.lower() for n in fbn], n=1, cutoff=0.6)
        if close:
            for name, fid in fbn.items():
                if name.lower() == close[0]:
                    return name, fid
        return "", ""

    # ── Trees ─────────────────────────────────────────────────────────────────
    def refresh_left_tree(self):
        self.tree_left.delete(*self.tree_left.get_children())
        for i, d in enumerate(self.setlist_data):
            tag = "missing" if not d["qxw_id"] else "ok"
            self.tree_left.insert("", tk.END, values=(
                f"{i + 1:02d}", d['txt_name'] or f"[Step {i}]",
                d['qxw_id'] or "---", d['qxw_name'],
                format_time_for_ui(d['in']), format_time_for_ui(d['hold']),
                format_time_for_ui(d['out'])
            ), tags=(tag,))
        self.refresh_usage_counts()
        self.update_duration_display()

    def populate_right_tree(self):
        self.tree_right.delete(*self.tree_right.get_children())
        fd = self.app.func_detailed
        unique_types = sorted(set(d['type'] for d in fd.values()))

        usage_counts = {}
        for d in self.setlist_data:
            if d["qxw_id"]:
                usage_counts[d["qxw_id"]] = usage_counts.get(d["qxw_id"], 0) + 1

        fvc = self.show_vc_only_var.get()
        ff = self.frame_filter_var.get()
        st = self.search_var.get().lower().strip()

        for f_type in unique_types:
            items = [(fid, det) for fid, det in fd.items() if det['type'] == f_type]
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
            parent = self.tree_right.insert("", tk.END, text=f"📂 {f_type}s", open=True)
            filtered.sort(key=lambda x: int(x[0]))
            for fid, det in filtered:
                desc = self.app.shared_descriptions.get(fid, "")
                uses = usage_counts.get(fid, 0)
                btn_info = self.app.vc_buttons.get(fid)
                vc_btn = " | ".join(sorted(btn_info['captions'])) if btn_info else ""
                tags = (fid, "used") if uses > 0 else (fid,)
                uses_d = f"★ {uses}" if uses > 0 else str(uses)
                self.tree_right.insert(parent, tk.END, text=f" {det['name']}",
                                       values=(fid, det['contains'], uses_d, vc_btn, desc),
                                       tags=tags)

    def refresh_usage_counts(self):
        if not self.tree_right.get_children():
            return
        usage_counts = {}
        for d in self.setlist_data:
            if d["qxw_id"]:
                usage_counts[d["qxw_id"]] = usage_counts.get(d["qxw_id"], 0) + 1

        def _update(node):
            tags = self.tree_right.item(node, "tags")
            if tags:
                fid = tags[0]
                uses = usage_counts.get(fid, 0)
                vals = list(self.tree_right.item(node, "values"))
                while len(vals) < 5:
                    vals.append("")
                vals[2] = f"★ {uses}" if uses > 0 else str(uses)
                ntags = (fid, "used") if uses > 0 else (fid,)
                self.tree_right.item(node, values=vals, tags=ntags)
            for c in self.tree_right.get_children(node):
                _update(c)

        for it in self.tree_right.get_children():
            _update(it)

    def update_duration_display(self):
        total_ms = 0
        for d in self.setlist_data:
            try:
                h = int(d.get("hold", 0))
                fi = int(d.get("in", 0))
                fo = int(d.get("out", 0))
                if h < 4000000000:
                    total_ms += h
                if fi < 4000000000:
                    total_ms += fi
                if fo < 4000000000:
                    total_ms += fo
            except ValueError:
                pass
        s = (total_ms // 1000) % 60
        m = (total_ms // 60000) % 60
        hr = total_ms // 3600000
        self.lbl_duration.config(text=f"Runtime: {hr:02d}:{m:02d}:{s:02d}")

    def update_chaser_dropdown(self):
        options = ["[ Create New Master Chaser ]"] + sorted(self.app.chasers.keys())
        self.combo_chaser['values'] = options
        detected = "[ Create New Master Chaser ]"
        for name in self.app.chasers:
            if any(kw in name.lower() for kw in ("master", "setlist", "gig")):
                detected = name
                break
        self.chaser_var.set(detected)

    # ── Actions ───────────────────────────────────────────────────────────────
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
        sl = self.tree_left.selection()
        sr = self.tree_right.selection()
        if not sl:
            return messagebox.showwarning("Notice", "Select a row on the LEFT first.")
        if not sr:
            return messagebox.showwarning("Notice", "Select a function on the RIGHT first.")
        tags = self.tree_right.item(sr[0], "tags")
        if not tags:
            return messagebox.showwarning("Notice", "Select a specific function, not a folder.")
        fid = tags[0]
        fname = self.app.func_detailed[fid]['name']
        idx = self.tree_left.index(sl[0])
        self.setlist_data[idx]["qxw_name"] = fname
        self.setlist_data[idx]["qxw_id"] = fid
        self.refresh_left_tree()
        children = self.tree_left.get_children()
        if idx + 1 < len(children):
            self.tree_left.selection_set(children[idx + 1])

    def unassign_cue(self):
        sel = self.tree_left.selection()
        if sel:
            idx = self.tree_left.index(sel[0])
            self.setlist_data[idx]["qxw_name"] = "--- Unassigned ---"
            self.setlist_data[idx]["qxw_id"] = ""
            self.refresh_left_tree()

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
                self.setlist_data[idx]["in"] = fi
                self.setlist_data[idx]["hold"] = fh
                self.setlist_data[idx]["out"] = fo
            self.refresh_left_tree()
        except ValueError:
            messagebox.showerror("Input Error", "Timings must be numeric or 'Inf'.")

    def move_up(self):
        sel = self.tree_left.selection()
        if not sel:
            return
        idx = self.tree_left.index(sel[0])
        if idx > 0:
            self.setlist_data[idx], self.setlist_data[idx - 1] = self.setlist_data[idx - 1], self.setlist_data[idx]
            self.refresh_left_tree()
            self.tree_left.selection_set(self.tree_left.get_children()[idx - 1])

    def move_down(self):
        sel = self.tree_left.selection()
        if not sel:
            return
        idx = self.tree_left.index(sel[0])
        if idx < len(self.setlist_data) - 1:
            self.setlist_data[idx], self.setlist_data[idx + 1] = self.setlist_data[idx + 1], self.setlist_data[idx]
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
                self.tree_left.selection_set(children[min(idx, len(children) - 1)])

    def on_chaser_change(self, event):
        cn = self.chaser_var.get()
        if cn == "[ Create New Master Chaser ]":
            return
        cid = self.app.chasers.get(cn)
        if not cid:
            return
        if self.setlist_data and event is not None:
            if not messagebox.askyesno("Load Chaser", "Replace current setlist with this Chaser's steps?"):
                return
        self.setlist_data.clear()
        chaser_node = self.app.qxw_root.find(f"q:Engine/q:Function[@ID='{cid}']", NS)
        if chaser_node is not None:
            id_to_name = {v: k for k, v in self.app.func_by_name.items()}
            for step in chaser_node.findall('q:Step', NS):
                fid = step.text
                qn = id_to_name.get(fid, f"Unknown ID {fid}")
                self.setlist_data.append({
                    "txt_name": qn, "qxw_name": qn, "qxw_id": fid,
                    "in": step.get('FadeIn', '0'),
                    "hold": step.get('Hold', '4294967294'),
                    "out": step.get('FadeOut', '0')
                })
        self.refresh_left_tree()

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
            messagebox.showinfo("Orphans Found", f"Disconnected functions:\n\n{msg}")

    # ── Exports ───────────────────────────────────────────────────────────────
    def export_dictionary(self):
        fd = self.app.func_detailed
        if not fd:
            return messagebox.showwarning("Notice", "Load a QXW workspace first.")
        bn = os.path.splitext(os.path.basename(self.app.current_qxw_file))[0] if self.app.current_qxw_file else "Untitled"
        fp = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text", "*.txt")],
            title="Export ID Dictionary", initialfile=f"{bn}_ID_description.txt")
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

    def export_txt(self):
        if not self.setlist_data:
            return messagebox.showwarning("Warning", "Setlist is empty.")
        fp = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text", "*.txt")],
            title="Export XML Code", initialfile="Gig_Code_Export.txt")
        if not fp:
            return
        try:
            xl = ['', '<Function ID="NEW_ID" Type="Chaser" Name="Master Chaser Setlist">',
                  ' <Speed FadeIn="0" FadeOut="0" Duration="4294967294"/>',
                  ' <Direction>Forward</Direction>', ' <RunOrder>Loop</RunOrder>',
                  ' <SpeedModes FadeIn="PerStep" FadeOut="PerStep" Duration="Common"/>']
            sc = 0
            for d in self.setlist_data:
                if d["qxw_id"]:
                    xl.append(f' <Step Number="{sc}" FadeIn="{d["in"]}" Hold="{d["hold"]}" FadeOut="{d["out"]}">{d["qxw_id"]}</Step>')
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

        # ── Column Picker Dialog ──────────────────────────────────────────────
        dlg = tk.Toplevel(self.parent)
        dlg.title("PDF Column Settings")
        dlg.geometry("340x370")
        dlg.resizable(False, False)
        dlg.grab_set()

        t = THEMES[self.app.current_theme]
        dlg.configure(bg=t["bg"])

        tk.Label(dlg, text="Select columns to include:",
                 font=("Helvetica", 11, "bold"),
                 bg=t["bg"], fg=t["fg"]).pack(anchor="w", padx=16, pady=(14, 8))

        # Available columns: key -> (label, default_on)
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

        # Paper size
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
            result["go"] = True
            dlg.destroy()

        btn_frame = tk.Frame(dlg, bg=t["bg"])
        btn_frame.pack(fill=tk.X, padx=16, pady=14)
        ttk.Button(btn_frame, text="Cancel", style="Normal.TButton",
                   command=dlg.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(btn_frame, text="Export PDF", style="Save.TButton",
                   command=on_export).pack(side=tk.RIGHT)

        dlg.wait_window()
        if not result["go"]:
            return

        # Build selected column list
        selected = []
        for key, label, _ in col_defs:
            if col_vars[key].get():
                selected.append((key, label))
        if not selected:
            return messagebox.showwarning("Warning", "Select at least one column!")

        paper_sizes = {
            "A4 Portrait": (595.0, 842.0), "A4 Landscape": (842.0, 595.0),
            "US Letter Portrait": (612.0, 792.0), "US Letter Landscape": (792.0, 612.0),
        }
        W, H = paper_sizes.get(paper_var.get(), (595.0, 842.0))

        bn = os.path.splitext(os.path.basename(self.app.current_qxw_file))[0] if self.app.current_qxw_file else "Gig"
        fp = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            title="Export PDF", initialfile=f"{bn}_Setlist.pdf")
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
        """Builds a setlist PDF with user-chosen columns and optional Notes column."""
        if not self.setlist_data:
            return None

        header_col = (0.12, 0.12, 0.18)
        row_alt = (0.95, 0.97, 1.00)
        show_name = os.path.basename(self.app.current_qxw_file) if self.app.current_qxw_file else "Untitled"
        doc_date = datetime.date.today().strftime("%Y-%m-%d")

        pages, cur_ln = [], []

        def sc(r, g, b): cur_ln.append(f"{r:.4f} {g:.4f} {b:.4f} RG")
        def fc(r, g, b): cur_ln.append(f"{r:.4f} {g:.4f} {b:.4f} rg")
        def lw(w): cur_ln.append(f"{w} w")
        def rfill(x, y, w, h, col): fc(*col); cur_ln.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")
        def rbox(x, y, w, h, fcol, scol, wd=0.5):
            fc(*fcol); sc(*scol); lw(wd); cur_ln.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re B")
        def txt(x, y, s, sz=8, bold=False):
            s = str(s).encode('latin-1', errors='replace').decode('latin-1')
            s = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            cur_ln.append(f"BT {'/F2' if bold else '/F1'} {sz} Tf {x:.2f} {y:.2f} Td ({s}) Tj ET")

        # ── Layout constants (bigger for readability) ─────────────────────────
        TITLE_H = 40
        T_PAD = 14
        ROW_H = 24          # taller rows
        HDR_H = 26           # taller header
        BODY_SZ = 10         # body text size (was 8)
        HDR_SZ = 10          # header text size (was 9)
        NUM_SZ = 11          # step number size
        dark_hdr = (0.22, 0.30, 0.45)

        # ── Build dynamic column geometry ─────────────────────────────────────
        # Base widths per column key (points). Text columns get more space.
        base_widths = {
            "num": 28, "song": 0, "cue": 0,
            "fade_in": 48, "hold": 48, "fade_out": 48,
        }
        usable_w = W - 2 * T_PAD
        # Fixed-width columns consume their space first
        fixed_used = sum(base_widths.get(k, 0) for k, _ in selected_cols if base_widths.get(k, 0) > 0)
        # Count "flexible" columns (song, cue) that share remaining space
        flex_keys = [k for k, _ in selected_cols if base_widths.get(k, 0) == 0]
        notes_min_w = 100 if include_notes else 0
        remaining = usable_w - fixed_used - notes_min_w
        if flex_keys:
            flex_w = max(60, remaining / len(flex_keys))
        else:
            flex_w = 0

        col_labels = []
        col_w = []
        for key, label in selected_cols:
            col_labels.append(label)
            bw = base_widths.get(key, 0)
            col_w.append(bw if bw > 0 else flex_w)

        if include_notes:
            # Notes column gets whatever space is left
            used = sum(col_w)
            notes_w = max(notes_min_w, usable_w - used)
            col_labels.append("Notes")
            col_w.append(notes_w)

        # Compute x positions
        col_x = []
        cx = T_PAD
        for w in col_w:
            col_x.append(cx)
            cx += w

        # ── Build data accessor per column key ────────────────────────────────
        def get_row_values(ri, d):
            vals = []
            for key, _ in selected_cols:
                if key == "num":
                    vals.append(f"{ri + 1:02d}")
                elif key == "song":
                    max_chars = int(flex_w / (BODY_SZ * 0.5))
                    vals.append((d["txt_name"] or "")[:max_chars])
                elif key == "cue":
                    max_chars = int(flex_w / (BODY_SZ * 0.5))
                    vals.append((d["qxw_name"] or "")[:max_chars])
                elif key == "fade_in":
                    vals.append(format_time_for_ui(d['in']))
                elif key == "hold":
                    vals.append(format_time_for_ui(d['hold']))
                elif key == "fade_out":
                    vals.append(format_time_for_ui(d['out']))
            if include_notes:
                vals.append("")  # empty notes cell for handwriting
            return vals

        def finish_page():
            if cur_ln:
                pages.append(zlib.compress("\n".join(cur_ln).encode("latin-1")))
                cur_ln.clear()

        def draw_header(pn):
            rfill(0, H - TITLE_H, W, TITLE_H, header_col)
            cur_ln.append("1 1 1 rg")
            txt(14, H - TITLE_H + 14, f"SETLIST: {show_name}", sz=15, bold=True)
            txt(W - 200, H - TITLE_H + 22, f"Date: {doc_date}", sz=9)
            txt(W - 200, H - TITLE_H + 10, f"Page {pn}", sz=9)
            T_TOP = H - TITLE_H - T_PAD
            hy = T_TOP - HDR_H
            for cx2, cw2 in zip(col_x, col_w):
                rbox(cx2, hy, cw2, HDR_H, dark_hdr, (0.1, 0.2, 0.35), 0.3)
            cur_ln.append("1 1 1 rg")
            for lbl, cx2 in zip(col_labels, col_x):
                txt(cx2 + 4, hy + 8, lbl, sz=HDR_SZ, bold=True)
            return hy

        pn = 1
        cy = draw_header(pn)
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
                sz = NUM_SZ if is_num else BODY_SZ
                b = is_num
                txt(col_x[vi] + 5, cy + 7, v, sz=sz, bold=b)
        finish_page()
        return self._assemble_pdf(pages, W, H)

    @staticmethod
    def _assemble_pdf(pages, W, H):
        raw = "%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        offsets = []
        def add(s):
            nonlocal raw; offsets.append(len(raw)); raw += s
        def obj(n, c): return f"{n} 0 obj\n{c}\nendobj\n"
        def sobj(n, data):
            body = data.decode("latin-1")
            return obj(n, f"<< /Length {len(data)} /Filter /FlateDecode >>\nstream\n{body}\nendstream")
        font_res = "<< /Font << /F1 3 0 R /F2 4 0 R >> >>"
        kids, po, so = [], [], []
        cid = 5
        for ps in pages:
            kids.append(f"{cid} 0 R")
            po.append(obj(cid, f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {W:.2f} {H:.2f}] /Contents {cid + 1} 0 R /Resources {font_res} >>"))
            so.append(sobj(cid + 1, ps))
            cid += 2
        add(obj(1, "<< /Type /Catalog /Pages 2 0 R >>"))
        add(obj(2, f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"))
        add(obj(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"))
        add(obj(4, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"))
        for p, s in zip(po, so):
            add(p); add(s)
        n = cid - 1
        xoff = len(raw)
        raw += f"xref\n0 {n + 1}\n0000000000 65535 f \n"
        for o in offsets:
            raw += f"{o:010d} 00000 n \n"
        raw += f"trailer\n<< /Size {n + 1} /Root 1 0 R >>\nstartxref\n{xoff}\n%%EOF\n"
        return raw.encode("latin-1")

    # ── Clone generator & save ────────────────────────────────────────────────
    def save_qxw(self):
        if not self.app.qxw_root:
            return messagebox.showwarning("Warning", "No QXW loaded!")
        unassigned = sum(1 for d in self.setlist_data if not d["qxw_id"])
        if unassigned > 0:
            if not messagebox.askyesno("Warning", f"{unassigned} unassigned cues will be skipped.\nSave anyway?"):
                return

        target_name = self.chaser_var.get()
        engine = self.app.qxw_root.find('q:Engine', NS)

        master_chaser = None
        linked = False
        mc_id = None

        if target_name == "[ Create New Master Chaser ]":
            self.app.highest_func_id += 1
            mc_id = str(self.app.highest_func_id)
            master_chaser = ET.SubElement(engine, f"{{{QLC_NS_URI}}}Function",
                                         {'ID': mc_id, 'Type': "Chaser", 'Name': "Master Setlist Chaser (Auto)"})
            ET.SubElement(master_chaser, f"{{{QLC_NS_URI}}}Speed",
                          {'FadeIn': "0", 'FadeOut': "0", 'Duration': "4294967294"})
            ET.SubElement(master_chaser, f"{{{QLC_NS_URI}}}Direction").text = "Forward"
            ET.SubElement(master_chaser, f"{{{QLC_NS_URI}}}RunOrder").text = "Loop"
            ET.SubElement(master_chaser, f"{{{QLC_NS_URI}}}SpeedModes",
                          {'FadeIn': "PerStep", 'FadeOut': "PerStep", 'Duration': "Common"})
            for cl in self.app.qxw_root.findall('.//q:CueList', NS):
                cn = cl.find('q:Chaser', NS)
                if cn is not None and cn.text in ("4294967295", "-1"):
                    cn.text = mc_id; linked = True
        else:
            mc_id = self.app.chasers.get(target_name)
            master_chaser = engine.find(f"q:Function[@ID='{mc_id}']", NS)
            if master_chaser is not None:
                for step in master_chaser.findall('q:Step', NS):
                    master_chaser.remove(step)

        if master_chaser is None:
            return

        if self.enforce_naming_var.get():
            for func in engine.findall('q:Function', NS):
                fid = func.get('ID'); fname = func.get('Name', '')
                if fid == mc_id or "(Auto-Clone)" in fname or "(Setlist)" in fname:
                    continue
                bi = self.app.vc_buttons.get(fid)
                if bi and bi['captions']:
                    func.set('Name', " | ".join(sorted(bi['captions'])))
                else:
                    func.set('Name', f"[{fid}] {func.get('Type', 'Function')} - Unassigned")

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
            self.app.highest_func_id += 1
            cid = str(self.app.highest_func_id)
            active_ids.add(cid)
            clone = copy.deepcopy(base)
            clone.set('ID', cid); clone.set('Name', f"{txt_n} (Setlist)")
            engine.append(clone)
            sa = {'Number': str(step_count), 'FadeIn': d['in'], 'Hold': d['hold'], 'FadeOut': d['out']}
            ns = ET.SubElement(master_chaser, f"{{{QLC_NS_URI}}}Step", sa)
            ns.text = cid; ns.tail = "\n   "
            step_count += 1

        for func in engine.findall('q:Function', NS):
            fn = func.get('Name', '')
            if ("(Auto-Clone)" in fn or "(Setlist)" in fn) and func.get('ID') not in active_ids:
                engine.remove(func)

        odir = os.path.dirname(self.app.current_qxw_file)
        obn = os.path.splitext(os.path.basename(self.app.current_qxw_file))[0]
        m = re.search(r'(\d+)$', obn)
        if m:
            ns2 = m.group(1)
            bn = obn[:m.start()] + str(int(ns2) + 1).zfill(len(ns2))
        else:
            bn = f"{obn}_GIG_READY"
        nf = os.path.join(odir, bn + ".qxw")

        if os.path.exists(nf):
            ans = messagebox.askyesnocancel("Exists", f"'{bn}.qxw' exists.\n\nYes=Overwrite, No=New file, Cancel=Abort")
            if ans is None:
                return
            if not ans:
                while os.path.exists(nf):
                    m2 = re.search(r'(\d+)$', bn)
                    bn = (bn[:m2.start()] + str(int(m2.group(1)) + 1).zfill(len(m2.group(1)))) if m2 else bn + "_1"
                    nf = os.path.join(odir, bn + ".qxw")

        try:
            xb = ET.tostring(self.app.qxw_root, encoding="utf-8").decode("utf-8")
            with open(nf, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE Workspace>\n' + xb)
            self.app.current_qxw_file = nf
            t = THEMES[self.app.current_theme]
            self.app.lbl_qxw.config(text=os.path.basename(nf), fg=t["lbl_green"])
            msg = f"Saved {step_count} cues to:\n{os.path.basename(nf)}"
            if linked:
                msg += "\n\nAuto-linked to empty Virtual Console Cue List!"
            messagebox.showinfo("Success", msg)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed:\n{e}")


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
            gn = gn.text if gn is not None else "Unknown"
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
            name = name.text if name is not None else f"Fixture {fid}"
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

        self._draw_grid(cw, sh, rx, ry, pad, t, "TOP VIEW — Width vs Depth", 0)
        self._draw_grid(cw, sh, rx, rz, pad, t, "FRONT VIEW — Width vs Height", sh)

        r = 10
        for f in self.fixture_data:
            if not f["in_3d"]:
                continue
            nx = pad + ((f["x"] - mn_x) / rx) * (cw - 2 * pad)
            ny_t = pad + ((mx_y - f["y"]) / ry) * (sh - 2 * pad)
            self.canvas.create_oval(nx - r, ny_t - r, nx + r, ny_t + r,
                                    fill=f["color"], outline=t["fg"])
            self.canvas.create_text(nx, ny_t + 22,
                                    text=f"{f['name']}\n[{f['patch']}]",
                                    fill=t["fg"], font=("Helvetica", 7, "bold"), justify="center")

            ny_f = sh + pad + ((mx_z - f["z"]) / rz) * (sh - 2 * pad)
            self.canvas.create_oval(nx - r, ny_f - r, nx + r, ny_f + r,
                                    fill=f["color"], outline=t["fg"])
            self.canvas.create_text(nx, ny_f + 22,
                                    text=f"{f['name']}\n[{f['patch']}]",
                                    fill=t["fg"], font=("Helvetica", 7, "bold"), justify="center")

    def _draw_grid(self, cw, sh, rw, rh, pad, t, title, y_off):
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

        # Draw two sections
        for sec_idx, (mn_v, mx_v, rv, title) in enumerate([
            (mn_y, mx_y, ry, "TOP VIEW (Width vs Depth)"),
            (mn_z, mx_z, rz, "FRONT VIEW (Width vs Height)")
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
                frac_v = (mx_v - (f["y"] if sec_idx == 0 else f["z"])) / rv if rv else 0.5
                ny = y_off + pad_tb + frac_v * ph
                circ(nx, fy(ny), r_dot, fc_col, fg)
                txt_c(nx, fy(ny) - r_dot - 9, f["name"], sz=5)
                txt_c(nx, fy(ny) - r_dot - 15, f"[{f['patch']}]", sz=5)

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
