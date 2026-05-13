#!/usr/bin/env python3
"""
AWS Environment Assessment — Interactive Wizard

Full guided experience: dependency check, authentication, region and scan
option selection, pre-scan summary, live scan output, and workbook launch.

DISCLAIMER: Community sample script provided without support guarantees.
Not an official product. Use at your own risk.

Requires Python 3.8+ to start.
"""

import sys
import os
import subprocess
import platform
import shutil
import getpass
import json
import datetime

# ── Minimum Python to run this wizard ────────────────────────────────────────
if sys.version_info < (3, 8):
    print("Python 3.8 or later is required to run this wizard.")
    print("Download: https://www.python.org/downloads/")
    sys.exit(1)

# ── ANSI colours (Windows VT100 fallback) ─────────────────────────────────────
def _enable_win_ansi():
    if platform.system() == "Windows":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass

_enable_win_ansi()
USE_COLOUR = sys.stdout.isatty()

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if USE_COLOUR else text

def cyan(t):     return _c("0;36",  t)
def green(t):    return _c("0;32",  t)
def yellow(t):   return _c("1;33",  t)
def red(t):      return _c("0;31",  t)
def gray(t):     return _c("0;90",  t)
def bold(t):     return _c("1",     t)
def dim_cyan(t): return _c("2;36",  t)

def good(msg):   print(green(f"  ✓ {msg}"))
def warn(msg):   print(yellow(f"  ⚠ {msg}"))
def fail(msg):   print(red(f"  ✗ {msg}"))
def info(msg):   print(gray(f"    {msg}"))

def divider():
    print(f"  {gray('─' * 54)}")

def step_header(n, total, title):
    print(f"\n{bold(cyan(f'  ─── Step {n} of {total}'))}  {bold(title)}")
    divider()

def ask(prompt, default=""):
    dflt = f" {dim_cyan(f'[{default}]')}" if default else ""
    try:
        val = input(f"  {prompt}{dflt}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print(); sys.exit(0)
    return val if val else default

def ask_yes_no(prompt, default=True):
    hint = dim_cyan("[Y/n]") if default else dim_cyan("[y/N]")
    try:
        val = input(f"  {prompt} {hint}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(); sys.exit(0)
    if val in ("y", "yes"):  return True
    if val in ("n", "no"):   return False
    return default

def menu(title, options, default="1"):
    """Display a numbered menu and return the chosen key."""
    print(f"\n  {bold(title)}\n")
    for key, label, hint in options:
        h = f"  {gray(hint)}" if hint else ""
        print(f"    {bold(key)}  {label}{h}")
    print()
    return ask("Choice", default)

def run_live(cmd, **kwargs):
    proc = subprocess.Popen(cmd, **kwargs)
    proc.communicate()
    return proc.returncode

# ── Saved config (last-used settings) ────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, ".last_run.json")

def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

cfg = load_config()

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
OS = platform.system()   # "Windows" | "Darwin" | "Linux"
TOTAL_STEPS = 6


def _install_deps(req_file):
    """Install requirements.txt — handles PEP 668 externally-managed environments."""
    venv_dir    = os.path.join(SCRIPT_DIR, ".venv")
    in_venv     = sys.prefix != sys.base_prefix or bool(os.environ.get("VIRTUAL_ENV"))

    # ── Case 1: already inside a venv — plain pip always works ───────────────
    if in_venv:
        info("Running: pip install -r requirements.txt")
        print()
        rc = run_live([sys.executable, "-m", "pip", "install", "-r", req_file])
        print()
        if rc != 0:
            fail("pip install failed. Check errors above.")
            sys.exit(1)
        good("Dependencies installed")
        return

    # ── Case 2: try plain pip (works on non-managed Python installs) ─────────
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", req_file],
        capture_output=True
    )
    if result.returncode == 0:
        good("Dependencies installed")
        return

    # ── Case 2b: .venv already exists with packages — just re-exec into it ──
    venv_python = os.path.join(
        venv_dir,
        "Scripts" if OS == "Windows" else "bin",
        "python.exe" if OS == "Windows" else "python"
    )
    if os.path.isfile(venv_python):
        check = subprocess.run(
            [venv_python, "-c", "import boto3, openpyxl, tqdm"],
            capture_output=True
        )
        if check.returncode == 0:
            info("Packages found in .venv/ — switching to virtual environment...")
            os.environ["_AWS_WIZARD_VENV"] = "1"
            if OS != "Windows":
                os.execv(venv_python, [venv_python] + sys.argv)
            else:
                sys.exit(subprocess.run([venv_python] + sys.argv).returncode)

    # ── Case 3: PEP 668 / externally-managed Python (Homebrew, system) ───────
    #   Fall back to a project-local virtual environment
    warn("pip install blocked (PEP 668 — externally managed Python).")
    info("Creating a project-local virtual environment in .venv/ ...")
    print()

    if not os.path.isdir(venv_dir):
        rc = subprocess.run([sys.executable, "-m", "venv", venv_dir],
                            capture_output=True, text=True)
        if rc.returncode != 0:
            fail("Could not create virtual environment.")
            # Detect missing python3-venv (common on minimal Linux installs)
            if "No module named venv" in rc.stderr or "No module named ensurepip" in rc.stderr:
                warn("The 'venv' module is not installed. Install it with:")
                if shutil.which("apt-get"):
                    info("  sudo apt-get install python3-venv python3-pip")
                elif shutil.which("dnf"):
                    info("  sudo dnf install python3-venv")
                elif shutil.which("yum"):
                    info("  sudo yum install python3-venv")
                elif shutil.which("zypper"):
                    info("  sudo zypper install python3-venv")
                elif shutil.which("pacman"):
                    info("  sudo pacman -S python-virtualenv")
                else:
                    info("  Install python3-venv via your system package manager")
            else:
                print(rc.stderr.strip())
            sys.exit(1)
    good("Virtual environment ready")
    info("Installing packages into .venv/ ...")
    print()
    rc = subprocess.run(
        [venv_python, "-m", "pip", "install", "-r", req_file]
    ).returncode
    print()
    if rc != 0:
        fail("pip install into virtual environment failed.")
        sys.exit(1)

    good("Dependencies installed in .venv/")
    info("Re-launching wizard with virtual environment Python...")
    print()
    # Replace this process with the venv Python — step 1 will skip dep install
    os.environ["_AWS_WIZARD_VENV"] = "1"
    if OS != "Windows":
        os.execv(venv_python, [venv_python] + sys.argv)
    else:
        sys.exit(subprocess.run([venv_python] + sys.argv).returncode)


def run_wizard():
    """Run one full assessment wizard cycle. Returns True to run again."""

    # ── Banner ────────────────────────────────────────────────────────────────
    print()
    print(cyan("  ┌──────────────────────────────────────────────────────┐"))
    print(cyan("  │          AWS Environment Assessment Tool             │"))
    print(cyan("  └──────────────────────────────────────────────────────┘"))
    print()

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1 — Environment check (Python + CLI + dependencies)
    # ─────────────────────────────────────────────────────────────────────────
    step_header(1, TOTAL_STEPS, "Environment check")

    # Python version
    major, minor, patch = sys.version_info[:3]
    if (major, minor) >= (3, 10):
        good(f"Python {major}.{minor}.{patch} — compatible")
    else:
        warn(f"Python {major}.{minor}.{patch} — 3.10+ recommended")
        if OS == "Darwin":    info("Upgrade: brew install python@3.12")
        elif OS == "Windows": info("Upgrade: winget install --id Python.Python.3.12 -e")
        else:                 info("Upgrade: sudo apt-get install python3.12")
        if not ask_yes_no("Continue anyway?", default=False):
            sys.exit(0)

    # AWS CLI
    aws_cmd = shutil.which("aws")
    if aws_cmd:
        try:
            ver = subprocess.check_output([aws_cmd, "--version"],
                                          stderr=subprocess.STDOUT).decode().strip()
            good(f"AWS CLI — {ver.split()[0]}")
        except Exception:
            good("AWS CLI found")
    else:
        warn("AWS CLI not found — some auth options will be unavailable")
        if OS == "Darwin":    info("Install: brew install awscli")
        elif OS == "Windows": info("Install: winget install --id Amazon.AWSCLI -e")
        else:                 info("Install: pip install awscli")

    # Dependencies — check first, only install if missing
    req_file = os.path.join(SCRIPT_DIR, "requirements.txt")

    # If we were re-launched from a venv, skip the check noise
    _venv_ready = os.environ.get("_AWS_WIZARD_VENV") == "1"
    if _venv_ready:
        good("Running inside virtual environment — dependencies ready")
    else:
        missing = []
        for pkg in ("boto3", "openpyxl", "tqdm"):
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)

        if not missing:
            good("All dependencies already installed")
        else:
            warn(f"Missing packages: {', '.join(missing)}")
            _install_deps(req_file)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2 — Authentication
    # ─────────────────────────────────────────────────────────────────────────
    step_header(2, TOTAL_STEPS, "Authentication")

    last_auth    = cfg.get("auth_choice", "5")
    last_profile = cfg.get("profile", "")

    choice = menu(
        "How would you like to authenticate?",
        [
            ("1", "IAM Identity Center / SSO",   "run: aws login"),
            ("2", "Named AWS CLI profile",        "~/.aws/credentials or ~/.aws/config"),
            ("3", "Environment variables",        "AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY"),
            ("4", "Enter access key / secret",    "set in this session only — never written to disk"),
            ("5", "Use existing credentials",     "boto3 auto-detects what's already active"),
        ],
        default=last_auth,
    )

    profile_name = None

    if choice == "1":
        if not aws_cmd:
            fail("AWS CLI is required for 'aws login'.")
            sys.exit(1)
        info("Running: aws login")
        print()
        if run_live([aws_cmd, "login"]) != 0:
            fail("Login failed.")
            sys.exit(1)

    elif choice == "2":
        profiles, seen = [], set()
        for path in (os.path.expanduser("~/.aws/config"),
                     os.path.expanduser("~/.aws/credentials")):
            if os.path.exists(path):
                with open(path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("[profile "):
                            p = line[9:].rstrip("]").strip()
                        elif line.startswith("[") and not line.startswith("[profile "):
                            p = line[1:].rstrip("]").strip()
                        else:
                            continue
                        if p and p not in seen:
                            profiles.append(p); seen.add(p)

        print()
        if profiles:
            info("Available profiles:")
            for i, p in enumerate(profiles, 1):
                marker = green(" ◀ last used") if p == last_profile else ""
                print(f"    {bold(str(i))}  {p}{marker}")
            print()
            raw = ask("Profile name or number", last_profile or profiles[0])
            profile_name = (profiles[int(raw) - 1]
                            if raw.isdigit() and 1 <= int(raw) <= len(profiles)
                            else raw)
        else:
            profile_name = ask("Profile name", last_profile or "default")

    elif choice == "3":
        key_id = os.environ.get("AWS_ACCESS_KEY_ID", "")
        secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        if not (key_id and secret):
            fail("AWS_ACCESS_KEY_ID and/or AWS_SECRET_ACCESS_KEY not set.")
            info("Set them in your shell first:  export AWS_ACCESS_KEY_ID=AKIA...")
            sys.exit(1)
        good(f"AWS_ACCESS_KEY_ID is set  ({key_id[:8]}...)")

    elif choice == "4":
        print()
        info("Credentials are set for this session only — never written to disk.")
        print()
        key_id = ask("AWS Access Key ID (AKIA...)")
        secret = getpass.getpass("  AWS Secret Access Key: ").strip()
        region = ask("Default region", "us-east-1")
        token  = ""
        if ask_yes_no("Session token? (for temporary / assumed-role credentials)", default=False):
            token = getpass.getpass("  AWS Session Token: ").strip()
        if not key_id or not secret:
            fail("Key ID and Secret are required.")
            sys.exit(1)
        os.environ["AWS_ACCESS_KEY_ID"]     = key_id
        os.environ["AWS_SECRET_ACCESS_KEY"] = secret
        os.environ["AWS_DEFAULT_REGION"]    = region
        if token:
            os.environ["AWS_SESSION_TOKEN"] = token

    # Verify identity
    print()
    account_id = "unknown"
    identity_arn = ""
    account_alias = ""
    iam_user = ""

    # Try AWS CLI first; fall back to boto3 directly
    verified = False
    verify_cmd = [aws_cmd] if aws_cmd else None
    if verify_cmd:
        extra = ["--profile", profile_name] if profile_name else []
        try:
            raw = subprocess.check_output(
                verify_cmd + ["sts", "get-caller-identity", "--output", "json"] + extra,
                stderr=subprocess.STDOUT
            ).decode().strip()
            parsed = json.loads(raw)
            account_id   = parsed.get("Account", "unknown")
            identity_arn = parsed.get("Arn", "")
            iam_user     = identity_arn.split("/")[-1] if identity_arn else ""
            good(f"Authenticated  ·  Account: {bold(account_id)}")
            info(f"Identity: {identity_arn}")
            verified = True
            # Try account alias
            try:
                alias_raw = subprocess.check_output(
                    verify_cmd + ["iam", "list-account-aliases",
                                  "--query", "AccountAliases[0]",
                                  "--output", "text"] + extra,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                if alias_raw and alias_raw != "None":
                    account_alias = alias_raw
                    good(f"Account alias: {bold(account_alias)}")
            except Exception:
                pass
        except subprocess.CalledProcessError as e:
            warn("Could not verify: " + e.output.decode().strip().splitlines()[-1])
            if not ask_yes_no("Continue anyway?", default=True):
                sys.exit(0)

    if not verified:
        # boto3 fallback — works even without AWS CLI installed
        try:
            import boto3
            kwargs = {}
            if profile_name:
                kwargs["profile_name"] = profile_name
            session = boto3.Session(**kwargs)
            sts = session.client("sts")
            resp = sts.get_caller_identity()
            account_id   = resp.get("Account", "unknown")
            identity_arn = resp.get("Arn", "")
            iam_user     = identity_arn.split("/")[-1] if identity_arn else ""
            good(f"Authenticated  ·  Account: {bold(account_id)}")
            info(f"Identity: {identity_arn}")
            # Try account alias via boto3
            try:
                iam = session.client("iam")
                aliases = iam.list_account_aliases().get("AccountAliases", [])
                if aliases:
                    account_alias = aliases[0]
                    good(f"Account alias: {bold(account_alias)}")
            except Exception:
                pass
        except Exception as e:
            warn(f"Could not verify credentials: {e}")
            if not ask_yes_no("Continue anyway?", default=True):
                sys.exit(0)

    cfg["auth_choice"] = choice
    if profile_name:
        cfg["profile"] = profile_name

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3 — Region selection
    # ─────────────────────────────────────────────────────────────────────────
    step_header(3, TOTAL_STEPS, "Region selection")

    # Detect available regions
    available_regions = []
    if aws_cmd:
        try:
            extra = ["--profile", profile_name] if profile_name else []
            out = subprocess.check_output(
                [aws_cmd, "ec2", "describe-regions",
                 "--query", "Regions[*].RegionName",
                 "--output", "text"] + extra,
                stderr=subprocess.DEVNULL
            ).decode().strip()
            available_regions = sorted(out.split())
        except Exception:
            pass

    region_count_str = (f"{len(available_regions)} enabled regions"
                        if available_regions else "all enabled regions")

    last_region_choice = cfg.get("region_choice", "1")

    rchoice = menu(
        "Which regions should be scanned?",
        [
            ("1", "All enabled regions",          region_count_str),
            ("2", "Specific regions",             "enter as space-separated list"),
            ("3", "Current / default only",       "fastest — single region"),
        ],
        default=last_region_choice,
    )

    region_args = []

    if rchoice == "1":
        region_args = ["--all-regions"]
        region_display = f"All enabled  ({region_count_str})"

    elif rchoice == "2":
        if available_regions:
            info("Available regions:")
            cols = 4
            for i, r in enumerate(available_regions):
                end = "\n" if (i + 1) % cols == 0 else "  "
                print(f"    {r:<22}", end=end)
            if len(available_regions) % cols != 0:
                print()
            print()
        last_regions = cfg.get("regions", "us-east-1 us-west-2")
        raw = ask("Space-separated region(s)", last_regions)
        regions = raw.split()
        region_args = ["--regions"] + regions
        region_display = ", ".join(regions)
        cfg["regions"] = raw

    else:
        default_region = (os.environ.get("AWS_DEFAULT_REGION") or
                          os.environ.get("AWS_REGION") or "us-east-1")
        if aws_cmd:
            try:
                extra = ["--profile", profile_name] if profile_name else []
                detected = subprocess.check_output(
                    [aws_cmd, "configure", "get", "region"] + extra,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                if detected:
                    default_region = detected
            except Exception:
                pass
        region_args = ["--regions", default_region]
        region_display = default_region

    cfg["region_choice"] = rchoice

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4 — Scan mode & options
    # ─────────────────────────────────────────────────────────────────────────
    step_header(4, TOTAL_STEPS, "Scan options")

    last_mode = cfg.get("scan_mode", "2")

    mode = menu(
        "Select a scan mode:",
        [
            ("1", bold("Quick scan"),    "current region · skip snapshots · 4 workers"),
            ("2", bold("Standard scan"), "selected regions · all data · 4 workers  ← recommended"),
            ("3", bold("Full scan"),     "selected regions · all data · 8 workers · verbose"),
            ("4", bold("Custom"),        "configure every option individually"),
        ],
        default=last_mode,
    )

    date_str    = datetime.datetime.now().strftime("%Y%m%d")
    default_out = f"AWS_Assessment_{date_str}.xlsx"
    last_out    = cfg.get("output", default_out)

    # Apply preset defaults
    if mode == "1":
        # Quick — override region to current only
        default_region = (os.environ.get("AWS_DEFAULT_REGION") or "us-east-1")
        if aws_cmd:
            try:
                extra = ["--profile", profile_name] if profile_name else []
                detected = subprocess.check_output(
                    [aws_cmd, "configure", "get", "region"] + extra,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                if detected:
                    default_region = detected
            except Exception:
                pass
        region_args    = ["--regions", default_region]
        region_display = default_region
        skip_snaps     = True
        workers        = "4"
        verbose        = False
        output         = ask("Output filename", last_out)

    elif mode == "2":
        skip_snaps = False
        workers    = "4"
        verbose    = False
        output     = ask("Output filename", last_out)

    elif mode == "3":
        skip_snaps = False
        workers    = "8"
        verbose    = True
        output     = ask("Output filename", last_out)

    else:
        # Custom
        print()
        skip_snaps = ask_yes_no(
            "Skip EBS snapshot enumeration?  (faster on accounts with many snapshots)",
            default=cfg.get("skip_snaps", False)
        )
        workers = ask("Parallel workers", cfg.get("workers", "4"))
        verbose = ask_yes_no("Enable verbose logging?", default=cfg.get("verbose", False))
        output  = ask("Output filename", last_out)

    if not output.endswith(".xlsx"):
        output += ".xlsx"

    cfg["scan_mode"] = mode
    cfg["output"]    = output
    cfg["workers"]   = workers
    cfg["verbose"]   = verbose
    cfg["skip_snaps"] = skip_snaps

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5 — Pre-scan summary & confirmation
    # ─────────────────────────────────────────────────────────────────────────
    step_header(5, TOTAL_STEPS, "Scan summary")

    mode_labels = {"1": "Quick", "2": "Standard", "3": "Full", "4": "Custom"}
    acct_display = account_id
    if account_alias:
        acct_display += f"  ({account_alias})"

    W = 56
    def box_row(label, value):
        label_str = f"  {cyan(label):<22}"
        print(f"  │  {label_str}  {bold(value):<{W - 28}}│")

    print()
    print(f"  ┌{'─' * (W - 2)}┐")
    print(f"  │{'  Scan Configuration':^{W - 2}}│")
    print(f"  ├{'─' * (W - 2)}┤")
    box_row("Account",    acct_display or "—")
    if iam_user:
        box_row("Identity",   iam_user)
    if profile_name:
        box_row("Profile",    profile_name)
    box_row("Regions",    region_display)
    box_row("Scan mode",  mode_labels.get(mode, "Custom"))
    box_row("Snapshots",  "Skipped" if skip_snaps else "Included")
    box_row("Workers",    workers)
    box_row("Output",     output)
    box_row("Verbose",    "Yes" if verbose else "No")
    print(f"  └{'─' * (W - 2)}┘")
    print()

    if not ask_yes_no("Start the scan?", default=True):
        sys.exit(0)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6 — Run
    # ─────────────────────────────────────────────────────────────────────────
    step_header(6, TOTAL_STEPS, "Running assessment")

    assessment_script = os.path.join(SCRIPT_DIR, "aws_assessment.py")
    if not os.path.exists(assessment_script):
        fail(f"aws_assessment.py not found in: {SCRIPT_DIR}")
        sys.exit(1)

    cmd = [sys.executable, assessment_script]
    cmd += region_args
    if profile_name:
        cmd += ["--profile", profile_name]
    cmd += ["--workers", workers, "--output", output]
    if skip_snaps:
        cmd.append("--skip-snapshots")
    if verbose:
        cmd.append("--verbose")

    info("Command: " + " ".join(cmd))
    print()
    print(cyan("  " + "─" * 54))
    start_time = datetime.datetime.now()
    rc = run_live(cmd)
    elapsed = datetime.datetime.now() - start_time
    print(cyan("  " + "─" * 54))
    print()

    if rc != 0:
        fail(f"Assessment exited with code {rc}.")
        sys.exit(rc)

    mins, secs = divmod(int(elapsed.total_seconds()), 60)
    good(f"Scan complete  ·  {mins}m {secs}s")

    output_path = os.path.join(os.getcwd(), output)
    info(f"Saved to: {output_path}")

    # Save last-run config
    save_config(cfg)

    # Open workbook
    print()
    if os.path.exists(output_path) and ask_yes_no("Open the workbook now?", default=True):
        try:
            if OS == "Darwin":
                subprocess.Popen(["open", output_path])
            elif OS == "Windows":
                os.startfile(output_path)
            else:
                subprocess.Popen(["xdg-open", output_path])
            good(f"Opened: {os.path.basename(output_path)}")
        except Exception as e:
            warn(f"Could not open automatically: {e}")

    # Run again?
    print()
    return ask_yes_no("Run another scan?", default=False)


# ── Main loop ─────────────────────────────────────────────────────────────────
while True:
    try:
        again = run_wizard()
    except KeyboardInterrupt:
        print()
        sys.exit(0)
    if not again:
        print()
        good("Done. Goodbye.")
        print()
        break
