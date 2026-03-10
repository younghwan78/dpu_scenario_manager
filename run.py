#!/usr/bin/env python3
"""
DPU Scenario Viewer — Unified Runner.

Usage:
    python run.py              # Generate HTML from scenarios
    python run.py --scenarios path/to/yamls --output path/to/docs
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = PROJECT_DIR / "scripts"
VENV_DIR = SCRIPTS_DIR / "venv"
REQUIREMENTS = SCRIPTS_DIR / "requirements.txt"

# Platform-specific venv paths
if sys.platform == "win32":
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
    VENV_PIP = VENV_DIR / "Scripts" / "pip.exe"
else:
    VENV_PYTHON = VENV_DIR / "bin" / "python"
    VENV_PIP = VENV_DIR / "bin" / "pip"


def ensure_venv() -> None:
    """Create virtual environment and install dependencies if needed."""
    if VENV_PYTHON.exists():
        print("✅ Virtual environment found.")
        return

    print("📦 Creating virtual environment...")
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])

    print("📦 Installing dependencies...")
    subprocess.check_call([
        str(VENV_PIP), "install", "-r", str(REQUIREMENTS),
        "--quiet", "--disable-pip-version-check"
    ])
    print("✅ Dependencies installed.\n")


def run_processor(extra_args: list[str] | None = None) -> None:
    """Run the processor script inside the venv."""
    cmd = [str(VENV_PYTHON), str(SCRIPTS_DIR / "processor.py")]
    if extra_args:
        cmd.extend(extra_args)
    subprocess.check_call(cmd, cwd=str(PROJECT_DIR))


def main() -> None:
    print("\n" + "=" * 56)
    print("  🖥️  DPU Scenario Viewer — Static HTML Generator")
    print("=" * 56 + "\n")

    # 1. Ensure venv
    ensure_venv()

    # 2. Forward all CLI args to processor
    extra_args = sys.argv[1:]
    run_processor(extra_args)

    docs_dir = PROJECT_DIR / "docs"
    print("=" * 56)
    print(f"  📂 Output: {docs_dir}")
    print(f"  🌐 Open docs/index.html in your browser")
    print("=" * 56 + "\n")


if __name__ == "__main__":
    main()
