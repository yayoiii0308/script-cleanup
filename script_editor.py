"""Script Editor: a small Tkinter GUI for cleaning up speaker-transcript
.txt files.

Expected block format in each source file, separated by blank lines::

    [16:32:55:00 - 16:32:55:13]
    PRODUCER:
     Cool.

Features:
- Wrap each block's dialogue text to a given width without inserting
  extra blank lines (exactly one blank line between blocks, always).
- Find & replace a speaker name across the whole script.
- Remove every line belonging to a given speaker.
- Insert or update a custom title (with a dashed banner) on the first
  line of the file.
- Browse a folder of scripts, edit one at a time, or select several to
  batch-apply the same edit to all of them at once.
- Export a combined version of several selected files, stitched
  together in an order you choose.
"""

import fnmatch
import os
import re
import textwrap
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

DEFAULT_WRAP_WIDTH = 85
TITLE_RULE = '-' * 50

_BLOCK_SPLIT_RE = re.compile(r'\n\s*\n')
_DASH_RE = re.compile(r'^-{3,}$')

# A single timecode: HH:MM:SS then a frame/millis field, tolerating the
# common frame separators ':' (Resolve/Premiere), ';' (drop-frame) and '.'.
_TIMECODE = r'\d{1,2}:\d{2}:\d{2}[:;.]\d{2,3}'
# A timestamp line: one timecode, or a "start - end" range, with the
# surrounding brackets OPTIONAL. Resolve brackets its timestamps
# ("[16:32:55:00 - 16:32:55:13]"); Premiere does not
# ("08:39:16:04 - 08:39:38:03"). Both must be recognized as the same shape.
_TIMESTAMP_RE = re.compile(
    r'^\s*\[?\s*' + _TIMECODE + r'(?:\s*[-–]\s*' + _TIMECODE + r')?\s*\]?\s*$'
)


def _is_timestamp_line(line):
    """True if `line` is a block's timecode line, whether or not it is
    bracketed. This is what lets one parser handle every source NLE's
    export -- the bracket is the only thing that differs between them."""
    return _TIMESTAMP_RE.match(line) is not None


def split_blocks(text):
    text = text.strip('\n')
    if not text:
        return []
    return [b for b in _BLOCK_SPLIT_RE.split(text) if b.strip()]


def _block_lines(block):
    return [line for line in block.splitlines() if line.strip() != '']


def block_speaker(block):
    """Return the speaker name for a [timestamp]/SPEAKER/text block, or None
    if this block has no speaker line (e.g. a bare [timestamp]/text cue like
    "(Music)")."""
    lines = _block_lines(block)
    if len(lines) >= 3 and _is_timestamp_line(lines[0]):
        return lines[1].strip().rstrip(':').strip()
    return None


def _wrap_text(body, width):
    """Wrap `body` to `width`, breaking ONLY at existing spaces. Hyphenated
    words are never split and a word longer than `width` overflows rather
    than being broken, so the words themselves are never altered and
    re-wrapping is lossless (rejoining wrapped lines reproduces `body`)."""
    return textwrap.wrap(body, width=width,
                         break_on_hyphens=False, break_long_words=False)


def wrap_script(text, width=DEFAULT_WRAP_WIDTH):
    """Re-wrap dialogue text in each block to `width` characters.

    Non-block content (e.g. a title banner) is left untouched. Blocks
    stay separated by exactly one blank line, with no blank lines
    inserted inside a block. Handles both [timestamp]/SPEAKER/text blocks
    and speaker-less [timestamp]/text cues (e.g. "(Music)").
    """
    out_blocks = []
    for block in split_blocks(text):
        lines = _block_lines(block)
        if not lines:
            continue
        # A dashed title banner is not dialogue -- never reflow it.
        if _DASH_RE.match(lines[0].strip()):
            out_blocks.append('\n'.join(lines))
            continue
        if not _is_timestamp_line(lines[0]):
            # No timecode line => assume no speaker label either, so the
            # whole block is dialogue and is safe to wrap. This is what
            # lets plain .txt files with no timecodes get wrapped too.
            body = ' '.join(line.strip() for line in lines)
            out_blocks.append('\n'.join(_wrap_text(body, width)))
            continue
        timestamp_line = lines[0].strip()
        if len(lines) >= 3:
            speaker_line = lines[1].strip()
            body = ' '.join(line.strip() for line in lines[2:])
            wrapped = _wrap_text(body, width) if body else []
            out_blocks.append('\n'.join([timestamp_line, speaker_line] + wrapped))
        elif len(lines) == 2:
            wrapped = _wrap_text(lines[1].strip(), width)
            out_blocks.append('\n'.join([timestamp_line] + wrapped))
        else:
            out_blocks.append(timestamp_line)
    return '\n\n'.join(out_blocks) + '\n' if out_blocks else ''


def remove_speaker_label(text, speaker_pattern):
    """Strip the speaker-label line from every block whose speaker matches
    `speaker_pattern`, leaving that block's timestamp and dialogue text
    completely untouched -- this never deletes script content, only the
    label line itself. A block with its label removed becomes a bare
    [timestamp]/text cue, same as an unlabeled block like "(Music)".

    `speaker_pattern` may use `*` (any characters) and `?` (one character)
    as wildcards, e.g. "Speaker *" matches "Speaker 3", "Speaker 30", etc.
    A pattern with no wildcard characters matches only that exact name."""
    target = speaker_pattern.strip().rstrip(':').strip().lower()
    if not target:
        return text

    out_blocks = []
    for block in split_blocks(text):
        raw_lines = block.splitlines()
        non_blank = [i for i, l in enumerate(raw_lines) if l.strip() != '']
        if len(non_blank) >= 3 and _is_timestamp_line(raw_lines[non_blank[0]]):
            speaker_idx = non_blank[1]
            speaker_text = raw_lines[speaker_idx].strip()
            speaker_norm = speaker_text.rstrip(':').strip().lower()
            if fnmatch.fnmatchcase(speaker_norm, target):
                del raw_lines[speaker_idx]
                block = '\n'.join(raw_lines)
        out_blocks.append(block)
    return '\n\n'.join(out_blocks) + '\n' if out_blocks else ''


def rename_speaker(text, old_name, new_name):
    """Rename a speaker by rewriting only the exact speaker-label line of
    blocks whose speaker matches `old_name`. Timestamps and dialogue text
    are left byte-for-byte untouched, in matching and non-matching blocks
    alike -- this never touches script content, and never matches on a
    numeric prefix (renaming "Speaker 3" cannot affect "Speaker 30").

    Whether the new label ends in a colon is controlled by `new_name` as
    typed (e.g. "Producer:" keeps the colon, "Producer" omits it) --
    independent of whether the old label had one."""
    target = old_name.strip().rstrip(':').strip().lower()
    new_stripped = new_name.strip()
    new_wants_colon = new_stripped.endswith(':')
    new_label = new_stripped.rstrip(':').strip()
    if not target or not new_label:
        return text

    out_blocks = []
    for block in split_blocks(text):
        raw_lines = block.splitlines()
        non_blank = [i for i, l in enumerate(raw_lines) if l.strip() != '']
        if len(non_blank) >= 3 and _is_timestamp_line(raw_lines[non_blank[0]]):
            speaker_idx = non_blank[1]
            speaker_text = raw_lines[speaker_idx].strip()
            if speaker_text.rstrip(':').strip().lower() == target:
                raw_lines[speaker_idx] = f"{new_label}:" if new_wants_colon else new_label
                block = '\n'.join(raw_lines)
        out_blocks.append(block)
    return '\n\n'.join(out_blocks) + '\n' if out_blocks else ''


def _strip_existing_title(lines):
    """If `lines` starts with a dashed-rule / title / dashed-rule banner,
    return the lines after it. Otherwise return `lines` unchanged."""
    i, n = 0, len(lines)
    if i < n and _DASH_RE.match(lines[i].strip()):
        while i < n and _DASH_RE.match(lines[i].strip()):
            i += 1
        if i < n:
            i += 1  # skip the title line itself
            while i < n and _DASH_RE.match(lines[i].strip()):
                i += 1
            return lines[i:]
    return lines


def set_title(text, title):
    """Insert `title` as a dashed banner at the top of the document,
    replacing any existing title banner rather than stacking a new one."""
    title = title.strip()
    if not title:
        return text
    lines = text.lstrip('\n').split('\n')
    rest = '\n'.join(_strip_existing_title(lines)).lstrip('\n')
    banner = '\n'.join([TITLE_RULE, TITLE_RULE, title, TITLE_RULE, TITLE_RULE])
    return f"{banner}\n\n{rest}"


class ScriptEditorApp:
    def __init__(self, root):
        self.root = root
        root.title("Script Editor")
        root.geometry("1150x720")

        self.current_path = None
        self.folder_files = []
        self.selected_paths = []
        self.buffers = {}  # path -> current (possibly edited, unsaved-to-original) text
        self.mode = None  # None | 'single' | 'batch'
        self.last_action = None  # snapshot of the most recent transform, for one-level Undo

        self._build_menu()
        self._build_layout()

    # ---------- layout ----------

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open File...", command=self.open_file)
        file_menu.add_command(label="Open Folder...", command=self.open_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Save As...", command=self.save_as)
        file_menu.add_command(label="Export Combined...", command=self.do_export_combined)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo Last Action", command=self.do_undo)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        self.root.config(menu=menubar)

    def _build_layout(self):
        left = ttk.Frame(self.root, width=260)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)
        ttk.Label(left, text="Folder Files").pack(anchor='w', padx=6, pady=(6, 0))
        ttk.Label(
            left,
            text="Click for one file. Cmd/Shift-click\nto select several for batch edits.",
            foreground="#666",
        ).pack(anchor='w', padx=6, pady=(0, 4))
        self.file_listbox = tk.Listbox(left, selectmode=tk.EXTENDED)
        self.file_listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.file_listbox.bind('<<ListboxSelect>>', self.on_select_file)

        right = ttk.Frame(self.root)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(right)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=6, pady=6)

        title_row = ttk.Frame(toolbar)
        title_row.pack(fill=tk.X, pady=2)
        ttk.Label(title_row, text="Title:").pack(side=tk.LEFT)
        self.title_var = tk.StringVar()
        ttk.Entry(title_row, textvariable=self.title_var, width=45).pack(side=tk.LEFT, padx=4)
        ttk.Button(title_row, text="Insert/Update Title", command=self.do_set_title).pack(side=tk.LEFT, padx=4)

        fr_row = ttk.Frame(toolbar)
        fr_row.pack(fill=tk.X, pady=2)
        ttk.Label(fr_row, text="Rename speaker:").pack(side=tk.LEFT)
        self.find_var = tk.StringVar()
        ttk.Entry(fr_row, textvariable=self.find_var, width=18).pack(side=tk.LEFT, padx=4)
        ttk.Label(fr_row, text="to:").pack(side=tk.LEFT)
        self.replace_var = tk.StringVar()
        ttk.Entry(fr_row, textvariable=self.replace_var, width=18).pack(side=tk.LEFT, padx=4)
        ttk.Button(fr_row, text="Rename", command=self.do_rename_speaker).pack(side=tk.LEFT, padx=4)
        ttk.Label(fr_row, text='(add ":" in "to:" to keep it, e.g. "Producer:")', foreground="#666").pack(
            side=tk.LEFT, padx=4
        )

        ex_row = ttk.Frame(toolbar)
        ex_row.pack(fill=tk.X, pady=2)
        ttk.Label(ex_row, text="Remove speaker label (keeps dialogue):").pack(side=tk.LEFT)
        self.exclude_var = tk.StringVar()
        ttk.Entry(ex_row, textvariable=self.exclude_var, width=18).pack(side=tk.LEFT, padx=4)
        ttk.Button(ex_row, text="Remove Label", command=self.do_remove_speaker_label).pack(side=tk.LEFT, padx=4)
        ttk.Label(ex_row, text='(wildcards ok, e.g. "Speaker *")', foreground="#666").pack(side=tk.LEFT, padx=4)

        wrap_row = ttk.Frame(toolbar)
        wrap_row.pack(fill=tk.X, pady=2)
        ttk.Label(wrap_row, text="Wrap width:").pack(side=tk.LEFT)
        self.width_var = tk.StringVar(value=str(DEFAULT_WRAP_WIDTH))
        ttk.Entry(wrap_row, textvariable=self.width_var, width=6).pack(side=tk.LEFT, padx=4)
        ttk.Button(wrap_row, text="Wrap Script", command=self.do_wrap).pack(side=tk.LEFT, padx=4)
        ttk.Label(
            wrap_row,
            text="(With multiple files selected, all actions above apply to every selected file"
                 " and auto-save as '<name>_CP.txt'.)",
            foreground="#666",
        ).pack(side=tk.LEFT, padx=12)

        ttk.Separator(right).pack(fill=tk.X, padx=6, pady=4)

        text_frame = ttk.Frame(right)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.text = tk.Text(text_frame, wrap='none', undo=True, font=('Menlo', 12))
        yscroll = ttk.Scrollbar(text_frame, orient='vertical', command=self.text.yview)
        xscroll = ttk.Scrollbar(text_frame, orient='horizontal', command=self.text.xview)
        self.text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.text.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        bottom = ttk.Frame(right)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=6)
        ttk.Button(bottom, text="Open File...", command=self.open_file).pack(side=tk.LEFT)
        ttk.Button(bottom, text="Open Folder...", command=self.open_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="Save As...", command=self.save_as).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="Export Combined...", command=self.do_export_combined).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="Undo", command=self.do_undo).pack(side=tk.LEFT, padx=4)
        self.status_var = tk.StringVar(value="No file loaded.")
        ttk.Label(bottom, textvariable=self.status_var).pack(side=tk.LEFT, padx=12)

    # ---------- buffer helpers ----------

    def _get_buffer(self, path):
        if path not in self.buffers:
            with open(path, 'r', encoding='utf-8') as f:
                self.buffers[path] = f.read()
        return self.buffers[path]

    def _sync_current_buffer(self):
        """Persist the text widget's current contents into the in-memory
        buffer for the single file it represents, before navigating away."""
        if self.mode == 'single' and self.current_path:
            self.buffers[self.current_path] = self.text.get('1.0', 'end-1c')

    @staticmethod
    def _cp_path(path):
        base, ext = os.path.splitext(path)
        return f"{base}_CP{ext}"

    # ---------- file ops ----------

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self._sync_current_buffer()
            self.buffers.pop(path, None)  # force a fresh read from disk
            self._load_path(path)

    def open_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        self._sync_current_buffer()
        files = sorted(f for f in os.listdir(folder) if f.lower().endswith('.txt'))
        self.folder_files = [os.path.join(folder, f) for f in files]
        self.file_listbox.delete(0, tk.END)
        for f in files:
            self.file_listbox.insert(tk.END, f)
        if not files:
            messagebox.showinfo("No files", "No .txt files found in that folder.")

    def on_select_file(self, event):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        self._sync_current_buffer()
        paths = [self.folder_files[i] for i in sel]
        if len(paths) == 1:
            self._load_path(paths[0])
        else:
            self._load_batch(paths)

    def _load_path(self, path):
        try:
            content = self._get_buffer(path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file:\n{e}")
            return
        self.current_path = path
        self.selected_paths = [path]
        self.mode = 'single'
        self.text.configure(state='normal')
        self.text.delete('1.0', tk.END)
        self.text.insert('1.0', content)
        self.status_var.set(f"Loaded: {os.path.basename(path)}")

    def _load_batch(self, paths):
        self.current_path = None
        self.selected_paths = paths
        self.mode = 'batch'
        names = '\n'.join(os.path.basename(p) for p in paths)
        self.text.configure(state='normal')
        self.text.delete('1.0', tk.END)
        self.text.insert(
            '1.0',
            f"{len(paths)} files selected for batch editing:\n\n{names}\n\n"
            "Toolbar actions (Title / Rename / Remove / Wrap) will apply to all of "
            "these and auto-save each as '<name>_CP.txt' next to the original.\n\n"
            "Select a single file in the list to hand-edit its text, or use "
            "'Export Combined...' to stitch these files together.",
        )
        self.text.configure(state='disabled')
        self.status_var.set(f"{len(paths)} files selected for batch editing.")

    def save_as(self):
        if self.mode == 'batch':
            messagebox.showinfo(
                "Save As",
                "Multiple files are selected. Use 'Export Combined...' to stitch them "
                "together, or select a single file to save it individually.",
            )
            return
        if self.current_path:
            default_name = os.path.basename(self._cp_path(self.current_path))
            initial_dir = os.path.dirname(self.current_path)
        else:
            default_name = "script_CP.txt"
            initial_dir = os.getcwd()
        path = filedialog.asksaveasfilename(
            initialfile=default_name,
            initialdir=initial_dir,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.text.get('1.0', 'end-1c'))
            self.status_var.set(f"Saved: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")

    # ---------- combined export ----------

    def do_export_combined(self):
        self._sync_current_buffer()
        paths = self.selected_paths
        if len(paths) < 2:
            messagebox.showinfo("Export Combined", "Select two or more files in the folder list first.")
            return
        order = self._ask_combine_order(paths)
        if not order:
            return
        try:
            pieces = [self._get_buffer(p).strip('\n') for p in order]
        except Exception as e:
            messagebox.showerror("Error", f"Could not read a selected file:\n{e}")
            return
        combined = '\n\n'.join(pieces) + '\n'
        out_path = filedialog.asksaveasfilename(
            initialfile="combined_CP.txt",
            initialdir=os.path.dirname(order[0]),
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not out_path:
            return
        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(combined)
            self.status_var.set(f"Exported combined file: {os.path.basename(out_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save combined file:\n{e}")

    def _ask_combine_order(self, paths):
        """Modal dialog to reorder `paths`. Returns the chosen order, or None if cancelled."""
        order = list(paths)
        result = {'paths': None}

        dialog = tk.Toplevel(self.root)
        dialog.title("Choose Combine Order")
        dialog.geometry("440x380")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Reorder files (top = first in combined output):").pack(
            anchor='w', padx=8, pady=(8, 4)
        )

        listbox = tk.Listbox(dialog, selectmode=tk.SINGLE)
        listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        for p in order:
            listbox.insert(tk.END, os.path.basename(p))
        listbox.selection_set(0)

        def move(delta):
            sel = listbox.curselection()
            if not sel:
                return
            i = sel[0]
            j = i + delta
            if j < 0 or j >= len(order):
                return
            order[i], order[j] = order[j], order[i]
            label = listbox.get(i)
            listbox.delete(i)
            listbox.insert(j, label)
            listbox.selection_set(j)

        btn_row = ttk.Frame(dialog)
        btn_row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Button(btn_row, text="Move Up", command=lambda: move(-1)).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Move Down", command=lambda: move(1)).pack(side=tk.LEFT, padx=4)

        action_row = ttk.Frame(dialog)
        action_row.pack(fill=tk.X, padx=8, pady=(4, 8))

        def on_export():
            result['paths'] = list(order)
            dialog.destroy()

        ttk.Button(action_row, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
        ttk.Button(action_row, text="Export", command=on_export).pack(side=tk.RIGHT, padx=4)

        dialog.wait_window()
        return result['paths']

    # ---------- editing ops ----------

    def _apply_transform(self, description, fn, *args, **kwargs):
        """Apply fn(content, *args, **kwargs) -> new_content either to the
        single loaded file (in the text widget, unsaved) or to every
        selected file in batch mode (saved immediately as '<name>_CP.txt').
        Snapshots the pre-transform state into self.last_action so Undo can
        revert exactly this one action."""
        if self.mode == 'single':
            old_content = self.text.get('1.0', 'end-1c')
            new_content = fn(old_content, *args, **kwargs)
            self.text.delete('1.0', tk.END)
            self.text.insert('1.0', new_content)
            if self.current_path:
                self.buffers[self.current_path] = new_content
            self.status_var.set(description)
            self.last_action = {
                'mode': 'single',
                'path': self.current_path,
                'old_content': old_content,
                'description': description,
            }
        elif self.mode == 'batch':
            pre_state = {path: self._get_buffer(path) for path in self.selected_paths}
            saved, failed, reverted = [], [], {}
            for path in self.selected_paths:
                try:
                    new_content = fn(pre_state[path], *args, **kwargs)
                    self.buffers[path] = new_content
                    out_path = self._cp_path(path)
                    with open(out_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    saved.append(os.path.basename(out_path))
                    reverted[path] = pre_state[path]
                except Exception as e:
                    failed.append(f"{os.path.basename(path)}: {e}")
            msg = f"{description} Saved {len(saved)} file(s)."
            if failed:
                msg += f" {len(failed)} failed."
                messagebox.showerror("Some files failed", "\n".join(failed))
            self.status_var.set(msg)
            if reverted:
                self.last_action = {
                    'mode': 'batch',
                    'old_buffers': reverted,
                    'description': description,
                }
        else:
            messagebox.showinfo("No file", "Open a file, or open a folder and select file(s), first.")

    def do_undo(self):
        action = self.last_action
        if not action:
            messagebox.showinfo("Undo", "Nothing to undo.")
            return
        if action['mode'] == 'single':
            path = action['path']
            if path:
                self.buffers[path] = action['old_content']
            if self.mode == 'single' and self.current_path == path:
                self.text.delete('1.0', tk.END)
                self.text.insert('1.0', action['old_content'])
            self.status_var.set(f"Undid: {action['description']}")
        elif action['mode'] == 'batch':
            failed = []
            for path, old_content in action['old_buffers'].items():
                self.buffers[path] = old_content
                try:
                    with open(self._cp_path(path), 'w', encoding='utf-8') as f:
                        f.write(old_content)
                except Exception as e:
                    failed.append(f"{os.path.basename(path)}: {e}")
            if self.mode == 'single' and self.current_path in action['old_buffers']:
                self.text.delete('1.0', tk.END)
                self.text.insert('1.0', self.buffers[self.current_path])
            n = len(action['old_buffers'])
            self.status_var.set(f"Undid: {action['description']} ({n} file(s) reverted).")
            if failed:
                messagebox.showerror("Some files failed to revert on disk", "\n".join(failed))
        self.last_action = None

    def do_wrap(self):
        try:
            width = int(self.width_var.get())
        except ValueError:
            messagebox.showerror("Invalid width", "Wrap width must be a number.")
            return
        self._apply_transform(f"Wrapped at {width} characters.", wrap_script, width=width)

    def do_rename_speaker(self):
        old_name = self.find_var.get()
        new_name = self.replace_var.get()
        if not old_name.strip() or not new_name.strip():
            messagebox.showinfo("Rename speaker", "Enter both the speaker to rename and the new name.")
            return
        self._apply_transform(f"Renamed '{old_name}' to '{new_name}'.", rename_speaker, old_name, new_name)

    def do_remove_speaker_label(self):
        speaker = self.exclude_var.get().strip()
        if not speaker:
            messagebox.showinfo("Remove speaker label", "Enter a speaker name to remove the label for.")
            return
        self._apply_transform(
            f"Removed the '{speaker}' label (dialogue kept).", remove_speaker_label, speaker
        )

    def do_set_title(self):
        title = self.title_var.get()
        if not title.strip():
            messagebox.showinfo("Title", "Enter a title first.")
            return
        self._apply_transform("Title updated.", set_title, title)


def main():
    root = tk.Tk()
    ScriptEditorApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
