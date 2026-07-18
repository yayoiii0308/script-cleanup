# script-cleanup

Tkinter GUI (`script_editor.py`) for editing speaker-transcript `.txt`
files. See `README.md` for user-facing usage/features. This file is
project context for Claude Code sessions working on the code itself.

## Non-negotiable rule

**Never delete or alter script content (timestamps, dialogue text).**
This has been stated explicitly, twice, by the user. Every transform in
this file must be provably content-preserving except for the one thing
it's explicitly meant to change:

- `wrap_script` — only re-flows dialogue text to a width; the words
  themselves never change.
- `rename_speaker` — only rewrites the exact speaker-label line of a
  matching block. Timestamps and dialogue are untouched, byte-for-byte,
  in matching *and* non-matching blocks.
- `remove_speaker_label` — only deletes the label line itself. The
  timestamp and dialogue text always survive (the block becomes a bare
  `[timestamp]` + text cue, same shape as an unlabeled `(Music)` cue).
  There is deliberately **no** feature that drops an entire block/turn
  — an earlier version did this and was rejected as content loss.

When adding any new transform, write a test that asserts block count
and dialogue text are unchanged (see "Testing approach" below) unless
the whole point of the feature is to remove blocks (none currently is).

## Transcript block format

Blocks are separated by a blank line. Two shapes exist in real files:

```
[16:32:55:00 - 16:32:55:13]      <- 3-line: timestamp / speaker / text
PRODUCER:
 Cool.

[00:02:10:48 - 00:02:20:31]      <- 2-line: timestamp / text, no speaker
 (Music)
```

The timestamp line may be **bracketed or not** — DaVinci Resolve brackets
it (`[..]`), Adobe Premiere does not (`08:39:16:04 - 08:39:38:03`). Detect
it with `_is_timestamp_line()` (a bracket-optional timecode regex), never
`startswith('[')`. Every transform routes through that helper so all NLE
exports parse identically. See [[transcript-source-formats]].

- Speaker label may or may not have a trailing colon (`EJ:` vs
  `Speaker 3`) — always normalize with `.rstrip(':').strip()` before
  comparing, both when parsing and when matching user input.
- Speaker matching must be **exact**, never substring/prefix. A real
  file had `Speaker 3` and `Speaker 30` coexisting — a naive
  `text.replace("Speaker 3", ...)` corrupts `Speaker 30` into
  `...0`. This is why `rename_speaker`/`remove_speaker_label` parse
  blocks and compare the normalized label exactly, rather than doing
  whole-document string replacement.
- A block only has a speaker if it has >= 3 non-blank lines and the
  first is a timestamp line (`_is_timestamp_line`). `block_speaker()`
  returns `None` for 2-line cue blocks — don't assume line[1] is always
  a speaker.
- `wrap_script` also handles blocks with **no timecode**: per an explicit
  user decision, no timecode ⇒ no speaker label either, so the whole
  block is treated as dialogue and wrapped (this is what lets plain prose
  `.txt` files wrap). The one exception is a dashed title banner, which is
  left untouched. Wrapping only ever breaks at existing spaces
  (`break_on_hyphens=False, break_long_words=False`) so words are never
  altered and re-wrapping is lossless.

## Environment gotcha: Tkinter on macOS

Plain `python3` on this machine (pyenv-built 3.9.21) links against
Apple's deprecated system Tk 8.5, which aborts with
`macOS 14 (1407) or later required...` on this OS build — a real,
reproducible crash, not sandbox-specific. Fixed locally via
`brew install python-tk@3.13`. **Run/test with**
`/usr/local/opt/python@3.13/bin/python3.13`, not bare `python3`.

Full troubleshooting matrix (python.org / Homebrew / pyenv) is in
`README.md` — a second machine hit the same class of issue with a
different Python install.

## Testing approach

There's no test suite file yet — verification so far has been ad hoc
`python3.13 -c "..."` snippets against a real sample transcript
(`AXBTB10154_BOWTV_...Main_M.txt`, kept locally, gitignored — 1507
blocks, mixes colon/no-colon speakers and 2-line cue blocks, good
regression fixture). Pattern used repeatedly and worth reusing:

1. Parse before/after with `split_blocks`.
2. Assert block count unchanged (unless intentionally removing blocks).
3. Assert every block's timestamp and dialogue text unchanged except
   the one line the transform is meant to touch.
4. Build `ScriptEditorApp` headlessly (`tk.Tk()` + `root.update()`,
   then `root.destroy()`) to confirm the GUI still constructs without
   errors — this catches wiring bugs (stale function/method names)
   without needing an actual display.

If a formal `tests/` suite gets added, base it on these fixtures rather
than starting over.

## Repo layout

- `script_editor.py` — the app. Pure functions at the top
  (`split_blocks`, `wrap_script`, `rename_speaker`,
  `remove_speaker_label`, `set_title`) are the logic to test; `
  ScriptEditorApp` is thin GUI wiring on top.
- The six original single-purpose scripts this replaced once lived in
  `legacy/`; that folder was removed from the repo before the v1.0.0
  release (still recoverable from git history before commit that
  removed it, if ever needed).
- `.gitignore` excludes all `*.txt` — transcripts are the user's real
  content and must never be pushed to GitHub.

## Release / versioning workflow

The user ships versions as **emailed zips**, not GitHub Releases, and
does not use feature branches — work lands directly on `main`. Each
shareable version is a frozen git **tag** (`vMAJOR.MINOR.PATCH`); a zip
is built from that tag with `git archive`.

- **Tags are frozen once shipped.** `v1.0.0` was emailed to a friend on
  2026-07-17 — never move or re-tag a released version again. (It was
  moved a few times *before* first send, which was fine then; that
  window is closed.) New work always gets a new number.
- **Cutting a new version**, once changes are committed to `main`:
  ```
  git tag -a vX.Y.Z -m "vX.Y.Z — <summary>"
  git push origin vX.Y.Z
  git archive --format=zip --prefix=script-cleanup-vX.Y.Z/ \
      -o ~/Desktop/script-cleanup-vX.Y.Z.zip vX.Y.Z
  ```
  `git archive` from the tag automatically excludes gitignored
  transcripts and anything not tracked — the zip is clean by
  construction. Verify with `unzip -l` before handing it over.
- **Version bump convention:** bug fix → PATCH (v1.0.1); new feature,
  nothing breaks → MINOR (v1.1.0); behaves differently than before →
  MAJOR (v2.0.0).
- The zip must extract into a single `script-cleanup-vX.Y.Z/` folder
  (that's the `--prefix`) and include the executable
  `Launch Script Editor.command` (mode 100755 — preserved by git, so
  don't lose the exec bit when editing it).
