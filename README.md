# script-cleanup

A small Tkinter GUI for editing speaker-transcript `.txt` files.

## Expected transcript format

Blocks separated by a blank line. The timestamp may be bracketed or not,
so exports from different editors work the same way:

```
[16:32:55:00 - 16:32:55:13]     <- DaVinci Resolve (bracketed)
SPEAKER:
 Dialogue text for this turn.

08:39:16:04 - 08:39:38:03       <- Adobe Premiere (no brackets)
SPEAKER
 Dialogue text for this turn.
```

Files with **no timecodes at all** (plain prose `.txt`) are also handled:
Wrap treats each blank-line-separated paragraph as text and re-wraps it.
(Avid exports aren't tested yet — no sample on hand — but timecoded ones
should parse the same way.)

## Running

### Easiest (macOS): double-click the launcher

Double-click **`Launch Script Editor.command`** in this folder. It finds
a Python with a working Tkinter on your Mac and starts the app.

The first time, macOS may block it with a warning that it's from an
"unidentified developer." To allow it: **Control-click (or right-click)
the file → Open → Open** in the dialog. After that first time, a normal
double-click works. (Alternatively: System Settings → Privacy &
Security → "Open Anyway.")

### From the terminal

```
python3 script_editor.py
```

Requires Python 3 with Tkinter (bundled with python.org installers; on
Homebrew Python, `brew install python-tk@3.13` or match whichever
Python you're using). If your default `python3` isn't set up with a
working Tkinter, see Troubleshooting below.

## Troubleshooting: "macOS 14 (1407) or later required... Abort trap: 6"

This means the Tcl/Tk library your Python is linked against has a
broken macOS-version check (a known Tk bug on macOS 14.x, unrelated to
this app — `import tkinter; tkinter.Tk()` alone will crash the same
way). First check which Python you're running and how Tkinter is
wired up:

```
python3 -c "import sys; print(sys.executable)"
python3 -c "import _tkinter; print(_tkinter.TK_VERSION)"
find "$(python3 -c 'import sys; print(sys.exec_prefix)')" -name "_tkinter*.so" -exec otool -L {} \;
```

Then fix based on how that Python was installed:

- **python.org installer** — reinstall the latest patch release from
  python.org; current installers bundle a patched Tcl/Tk that doesn't
  have this bug.
- **Homebrew Python** (`python@3.x` from `brew`) — run
  `brew install python-tk@3.x` (match your Python's minor version).
  This pulls in a compatible `tcl-tk@8` and links it correctly. Avoid
  relying on the plain `tcl-tk` formula by itself — it now installs
  Tcl/Tk 9.0, which older `tkinter` builds don't support.
- **pyenv-built Python** — pyenv often links against Apple's own
  deprecated system Tk 8.5 framework, which has this same bug. Fix by
  installing a compatible Tcl/Tk and rebuilding:
  ```
  brew install tcl-tk@8
  env PYTHON_CONFIGURE_OPTS="--with-tcltk-includes='-I$(brew --prefix tcl-tk@8)/include' --with-tcltk-libs='-L$(brew --prefix tcl-tk@8)/lib -ltcl8.6 -ltk8.6'" \
    pyenv install --force <your-version>
  ```

## Features

- **Open File / Open Folder** — edit one script at a time, or browse a
  folder of scripts in the left-hand list.
- **Wrap Script** — re-wraps each block's dialogue text to a given
  character width. Works whether or not the timestamp is bracketed, and
  on plain `.txt` files with no timecodes at all. Only ever breaks at
  existing spaces (hyphenated words are never split, a word longer than
  the width overflows instead of breaking), leaves exactly one blank
  line between blocks, never inserts blank lines inside a block, leaves
  a dashed title banner untouched, and is safe to run repeatedly.
- **Rename speaker** — renames a speaker by rewriting only the exact
  label line of blocks that match, e.g. `Speaker 3` → `Announcer`.
  Never touches timestamps or dialogue text, and never matches on a
  numeric prefix (renaming `Speaker 3` cannot affect `Speaker 30`).
- **Remove speaker label** — strips the label line from blocks
  matching a given speaker, leaving the timestamp and dialogue text in
  place (the block becomes a bare `[timestamp]` + text cue, like an
  unlabeled `(Music)` cue). This never deletes script content, only
  the label itself.
- **Insert/Update Title** — adds a custom title as a dashed banner at
  the top of the file; running it again replaces the existing title
  instead of stacking a new one on top.
- **Batch editing** — select multiple files in the folder list
  (Cmd/Shift-click) and any of the actions above apply to all of them
  at once, auto-saving each as `<name>_CP.txt` next to its original.
- **Export Combined** — select multiple files and stitch them into one
  output file, in an order you choose via a reorder dialog.
- **Undo** — reverts the single most recent Wrap/Rename/Remove
  Label/Title action (one level, no stack). In batch mode this also
  re-writes the affected `<name>_CP.txt` files back to their
  pre-action content. Manual typing in the text box has its own
  separate native undo (Cmd+Z) while a single file is loaded.
- **Save As** — never overwrites your original file; defaults to
  `<original>_CP.txt` next to the source file.

## History

This tool consolidates six earlier single-purpose scripts (cleanup,
folder-batch cleanup, and wrap variants) into one app, and fixes a bug
where the old wrap scripts inserted a blank line after every line
instead of only between speaker turns.

## Author

Created by Corinne Pickett (cspickett@gmail.com).
