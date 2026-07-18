#!/bin/bash
# Double-click launcher for Script Editor (macOS).
#
# Finds a Python on this Mac whose Tkinter actually works (the app needs
# it), then launches the app. Works no matter where this folder lives,
# because it cd's to its own location first.

cd "$(dirname "$0")" || exit 1

# Candidate Python interpreters, in preference order: the machine's
# default first, then the usual python.org and Homebrew locations.
candidates=(
    "python3"
    "/usr/local/bin/python3"
    "/opt/homebrew/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/Current/bin/python3"
    "/usr/local/opt/python@3.13/bin/python3.13"
    "/opt/homebrew/opt/python@3.13/bin/python3.13"
)

# True only if this interpreter can actually build a Tk window (catches
# the "macOS 14 (1407) or later required" Tcl/Tk crash, which happens on
# Tk() creation, not on import).
tk_works() {
    "$1" - >/dev/null 2>&1 <<'PY'
import tkinter
r = tkinter.Tk()
r.withdraw()
r.destroy()
PY
}

PYBIN=""
for c in "${candidates[@]}"; do
    if command -v "$c" >/dev/null 2>&1 || [ -x "$c" ]; then
        if tk_works "$c"; then
            PYBIN="$c"
            break
        fi
    fi
done

if [ -z "$PYBIN" ]; then
    echo
    echo "Couldn't find a Python with a working Tkinter on this Mac."
    echo
    echo "Script Editor needs Python 3 with a working Tkinter. See the"
    echo "Troubleshooting section in README.md (in this folder) for how to"
    echo "fix it for your Python install."
    echo
    echo "Press any key to close this window."
    read -r -n 1 -s
    exit 1
fi

exec "$PYBIN" "script_editor.py"
