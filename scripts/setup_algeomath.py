#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Beginner-friendly dependency installer for the AlgeoMath skill."""

import importlib.util
import subprocess
import sys
from pathlib import Path


def run(command):
    print("+ " + " ".join(command), flush=True)
    subprocess.check_call(command)


def ensure_pip_package(package_name):
    if importlib.util.find_spec(package_name) is not None:
        print(f"{package_name}: already installed")
        return
    run([sys.executable, "-m", "pip", "install", package_name])


def ensure_playwright_chromium():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        executable = Path(playwright.chromium.executable_path)
    if executable.exists():
        print("playwright chromium: already installed")
        return
    run([sys.executable, "-m", "playwright", "install", "chromium"])


def main():
    print("This installs the libraries needed for AlgeoMath automatic placement.")
    print("It is safe to run again; installed items are skipped.")
    ensure_pip_package("playwright")
    ensure_playwright_chromium()
    print("Ready. AlgeoMath automatic placement can now open the browser and place blocks.")


if __name__ == "__main__":
    main()
