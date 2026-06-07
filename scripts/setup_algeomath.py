#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Beginner-friendly dependency installer for the AlgeoMath skill."""

import importlib.util
import subprocess
import sys
import time
from pathlib import Path


def log(message):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}", flush=True)


def run(command):
    log("+ " + " ".join(command))
    subprocess.check_call(command)


def ensure_pip_package(package_name):
    log(f"checking dependency: {package_name}")
    if importlib.util.find_spec(package_name) is not None:
        log(f"{package_name}: already installed")
        return
    log(f"installing dependency: {package_name}")
    run([sys.executable, "-m", "pip", "install", package_name])


def ensure_playwright_chromium():
    from playwright.sync_api import sync_playwright

    log("checking browser: playwright chromium")
    with sync_playwright() as playwright:
        executable = Path(playwright.chromium.executable_path)
    if executable.exists():
        log("playwright chromium: already installed")
        return
    log("installing browser: playwright chromium")
    run([sys.executable, "-m", "playwright", "install", "chromium"])


def main():
    log("This installs the libraries needed for AlgeoMath automatic placement.")
    log("It is safe to run again; installed items are skipped.")
    ensure_pip_package("playwright")
    ensure_playwright_chromium()
    log("Ready. AlgeoMath automatic placement can now open the browser and place blocks.")


if __name__ == "__main__":
    main()
