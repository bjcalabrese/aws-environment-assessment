#!/usr/bin/env bash
# start-assessment.sh — macOS / Linux launcher for the AWS Environment Assessment Tool
#
# DISCLAIMER: Community sample script provided without support guarantees.
# Not an official product. Use at your own risk.
#
# Usage:
#   ./start-assessment.sh
#   ./start-assessment.sh --verbose
#   ./start-assessment.sh --all-regions --output MyAssessment.xlsx

set -euo pipefail

# ── Colour helpers ─────────────────────────────────────────────────────────────
if [ -t 1 ]; then
    C_CYAN='\033[0;36m'  C_GREEN='\033[0;32m'  C_YELLOW='\033[1;33m'
    C_RED='\033[0;31m'   C_GRAY='\033[0;90m'   C_RESET='\033[0m'
else
    C_CYAN='' C_GREEN='' C_YELLOW='' C_RED='' C_GRAY='' C_RESET=''
fi

header() { printf "\n${C_CYAN}  %s${C_RESET}\n" "$*"; }
good()   { printf "${C_GREEN}  ✓ %s${C_RESET}\n" "$*"; }
warn()   { printf "${C_YELLOW}  ⚠ %s${C_RESET}\n" "$*"; }
fail()   { printf "${C_RED}  ✗ %s${C_RESET}\n" "$*"; }
info()   { printf "${C_GRAY}    %s${C_RESET}\n" "$*"; }

# ── Script directory (reliable even when dot-sourced) ─────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Banner ────────────────────────────────────────────────────────────────────
printf "\n${C_CYAN}"
printf "  ┌─────────────────────────────────────────────────┐\n"
printf "  │       AWS Environment Assessment Tool           │\n"
printf "  │           macOS / Linux Launcher                │\n"
printf "  └─────────────────────────────────────────────────┘\n"
printf "${C_RESET}\n"

# ── Fast path: use project venv if it already exists ─────────────────────────
VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python"
if [ -f "$VENV_PYTHON" ]; then
    good "Using project virtual environment (.venv/)"
    WIZARD="${SCRIPT_DIR}/setup_wizard.py"
    if [ ! -f "$WIZARD" ]; then
        fail "setup_wizard.py not found in: ${SCRIPT_DIR}"
        exit 1
    fi
    export _AWS_WIZARD_VENV=1
    exec "$VENV_PYTHON" "$WIZARD" "$@"
fi

# ── Step 1: Find Python 3.10+ ─────────────────────────────────────────────────
header "Checking for Python 3.10+..."

PYTHON_CMD=""

check_python() {
    local cmd="$1"
    if command -v "$cmd" &>/dev/null; then
        local ver
        ver="$("$cmd" --version 2>&1)"
        local major minor
        major="$(echo "$ver" | grep -oE '[0-9]+\.[0-9]+' | head -1 | cut -d. -f1)"
        minor="$(echo "$ver" | grep -oE '[0-9]+\.[0-9]+' | head -1 | cut -d. -f2)"
        if [ -n "$major" ] && [ "$major" -gt 3 ] 2>/dev/null; then
            PYTHON_CMD="$cmd"; return 0
        fi
        if [ -n "$major" ] && [ "$major" -eq 3 ] && [ "${minor:-0}" -ge 10 ] 2>/dev/null; then
            PYTHON_CMD="$cmd"; return 0
        fi
    fi
    return 1
}

# Check versioned commands first (newest to oldest), then generics
for cmd in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if check_python "$cmd"; then
        VER="$("$PYTHON_CMD" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
        good "Found Python ${VER} via '${PYTHON_CMD}'"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    warn "Python 3.10+ not found. Attempting to install..."

    OS="$(uname -s)"
    if [ "$OS" = "Darwin" ]; then
        if command -v brew &>/dev/null; then
            info "Running: brew install python@3.12"
            brew install python@3.12
            check_python python3.12 || check_python python3
        else
            warn "Homebrew not found."
            info "Opening python.org/downloads/macos in your browser..."
            open "https://www.python.org/downloads/macos/" 2>/dev/null || true
            fail "Please install Python 3.10+ then re-run this script."
            exit 1
        fi
    else
        # Linux — detect package manager
        if command -v apt-get &>/dev/null; then
            info "Detected apt — running: sudo apt-get install -y python3.12"
            sudo apt-get update -qq && sudo apt-get install -y python3.12
            check_python python3.12 || check_python python3
        elif command -v dnf &>/dev/null; then
            info "Detected dnf — running: sudo dnf install -y python3.12"
            sudo dnf install -y python3.12
            check_python python3.12 || check_python python3
        elif command -v yum &>/dev/null; then
            info "Detected yum — running: sudo yum install -y python3"
            sudo yum install -y python3
            check_python python3
        elif command -v zypper &>/dev/null; then
            info "Detected zypper — running: sudo zypper install -y python312"
            sudo zypper install -y python312
            check_python python3.12 || check_python python3
        elif command -v pacman &>/dev/null; then
            info "Detected pacman — running: sudo pacman -S --noconfirm python"
            sudo pacman -S --noconfirm python
            check_python python3
        else
            fail "No supported package manager found."
            info "Please install Python 3.10+ manually: https://www.python.org/downloads/"
            exit 1
        fi
    fi

    if [ -z "$PYTHON_CMD" ]; then
        fail "Python 3.10+ installation failed or not found after install."
        info "Please install manually: https://www.python.org/downloads/"
        exit 1
    fi
    good "Python installed: $("$PYTHON_CMD" --version 2>&1)"
fi

# ── Step 2: Verify wizard exists ──────────────────────────────────────────────
WIZARD="${SCRIPT_DIR}/setup_wizard.py"
if [ ! -f "$WIZARD" ]; then
    fail "setup_wizard.py not found in: ${SCRIPT_DIR}"
    exit 1
fi

# ── Step 3: Prefer project venv if it already exists (e.g. after first run) ──
VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python"
if [ -f "$VENV_PYTHON" ]; then
    good "Using project virtual environment (.venv/)"
    PYTHON_CMD="$VENV_PYTHON"
    export _AWS_WIZARD_VENV=1
fi

# ── Step 4: Hand off to wizard (exec = clean process replacement) ─────────────
good "Launching setup wizard..."
printf "\n"
exec "$PYTHON_CMD" "$WIZARD" "$@"
