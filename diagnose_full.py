#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
diagnose_full.py
Comprehensive Windows/Python diagnostic without third-party packages or admin rights.
Compatible with Python 3.8+ / Windows 7+.

Creates: diagnose_report_<COMPUTERNAME>.txt
Does not collect passwords, cookies, browser history, Windows Product Key,
or personal file contents.
"""

import os
import sys
import platform
import socket
import shutil
import subprocess
import time
import json
import re
from datetime import datetime

REPORT = "diagnose_report_%s.txt" % (os.environ.get("COMPUTERNAME") or socket.gethostname())

def run(cmd, timeout=30):
    try:
        p = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            errors="replace", timeout=timeout
        )
        out = (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr else "")
        return out.strip()
    except Exception as e:
        return "[ERROR] %s" % e

def section(f, title, body):
    f.write("\n" + "=" * 80 + "\n")
    f.write(title + "\n")
    f.write("=" * 80 + "\n")
    f.write(body if body else "[no data]")
    f.write("\n")

def ps(cmd, timeout=30):
    return run('powershell -NoProfile -ExecutionPolicy Bypass -Command "%s"' % cmd.replace('"', '\"'), timeout)

def benchmark():
    n = 3000000
    t0 = time.perf_counter()
    x = 0
    for i in range(n):
        x = (x + i * i) & 0xFFFFFFFF
    return "Iterations: %d\nElapsed: %.3f sec\nChecksum: %d" % (n, time.perf_counter() - t0, x)

def main():
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("FULL DIAGNOSTIC REPORT\n")
        f.write("Generated: %s\n" % datetime.now().isoformat())
        f.write("Computer: %s\n" % (os.environ.get("COMPUTERNAME") or socket.gethostname()))

        section(f, "SYSTEM", "\n".join([
            "platform: " + platform.platform(),
            "system: " + platform.system(),
            "release: " + platform.release(),
            "version: " + platform.version(),
            "machine: " + platform.machine(),
            "processor: " + platform.processor(),
            "architecture: " + str(platform.architecture()),
            "hostname: " + socket.gethostname(),
            "username: " + os.environ.get("USERNAME", ""),
        ]))

        section(f, "PYTHON", "\n".join([
            "version: " + sys.version.replace("\n", " "),
            "executable: " + sys.executable,
            "prefix: " + sys.prefix,
            "implementation: " + platform.python_implementation(),
        ]))

        section(f, "CPU", run("wmic cpu get Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed /format:list"))
        if not run("wmic cpu get Name"):
            section(f, "CPU (PowerShell fallback)",
                    ps("Get-CimInstance Win32_Processor | Format-List Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed"))

        section(f, "RAM", run("wmic computersystem get TotalPhysicalMemory /value"))
        section(f, "GPU", run("wmic path win32_VideoController get Name,AdapterRAM,DriverVersion,VideoModeDescription /format:list"))
        if "No Instance" in run("wmic path win32_VideoController get Name") or not shutil.which("wmic"):
            section(f, "GPU (PowerShell fallback)",
                    ps("Get-CimInstance Win32_VideoController | Format-List Name,AdapterRAM,DriverVersion,VideoModeDescription"))

        section(f, "MOTHERBOARD / BIOS",
                run("wmic baseboard get Manufacturer,Product,Version /format:list") + "\n" +
                run("wmic bios get Manufacturer,SMBIOSBIOSVersion,ReleaseDate /format:list"))

        section(f, "DISKS", run("wmic logicaldisk get DeviceID,FileSystem,FreeSpace,Size,VolumeName /format:list"))
        section(f, "NETWORK CONFIG", run("ipconfig /all"))
        section(f, "ROUTES", run("route print"))
        section(f, "ARP", run("arp -a"))
        section(f, "NETWORK CONNECTIONS", run("netstat -ano"))
        section(f, "INTERNET TEST", "\n".join([
            "DNS google.com: " + run("nslookup google.com", 15),
            "Ping 1.1.1.1: " + run("ping -n 2 1.1.1.1", 15),
            "PowerShell HTTPS test: " + ps("[Net.WebRequest]::Create('https://www.google.com').GetResponse().StatusCode", 20),
        ]))

        section(f, "WINDOWS INFO", run("systeminfo", 45))
        section(f, "DEVICES", run("wmic path Win32_PnPEntity get Name,Status /format:list"))
        section(f, "VIRTUALIZATION", run("systeminfo | findstr /i "Hyper-V Virtualization""))
        section(f, "POWER", run("powercfg /GETACTIVESCHEME"))
        section(f, "PROCESSES", run("tasklist", 30))
        section(f, "SERVICES", run("sc query type= service state= all", 45))

        software = run(r'reg query "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall" /s /v DisplayName', 45)
        software += "\n" + run(r'reg query "HKLM\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall" /s /v DisplayName', 45)
        section(f, "INSTALLED SOFTWARE", software)

        env = {k: v for k, v in os.environ.items()
               if k.upper() not in ("PATH", "PATHEXT") and "TOKEN" not in k.upper() and "PASSWORD" not in k.upper() and "SECRET" not in k.upper()}
        section(f, "ENVIRONMENT (SAFE SUBSET)", json.dumps(env, indent=2, ensure_ascii=False))

        section(f, "AI / PYTHON PACKAGES",
                run('"%s" -m pip list' % sys.executable, 45))
        section(f, "AI TOOL PRESENCE", "\n".join([
            "git: " + (shutil.which("git") or "not found"),
            "ffmpeg: " + (shutil.which("ffmpeg") or "not found"),
            "nvidia-smi: " + (shutil.which("nvidia-smi") or "not found"),
            "python: " + (shutil.which("python") or "not found"),
            "py: " + (shutil.which("py") or "not found"),
        ]))
        section(f, "NVIDIA", run("nvidia-smi", 20))
        section(f, "CPU BENCHMARK", benchmark())

        section(f, "SYSTEM LIMITS",
                "CPU count: %s\nRAM available (bytes): %s\nDisk free (current drive): %s" %
                (os.cpu_count(), getattr(__import__("psutil") if False else os, "name", "n/a"),
                 shutil.disk_usage(os.getcwd()).free))

        section(f, "COMMON AI PATHS", "\n".join([
            os.path.expanduser("~"),
            os.path.join(os.path.expanduser("~"), ".cache"),
            os.path.join(os.path.expanduser("~"), ".cache", "huggingface"),
            os.path.join(os.path.expanduser("~"), ".cache", "torch"),
            r"C:\work",
            r"C:\AI",
            r"C:\Program Files",
        ]))

    print("Готово.")
    print("Отчёт: " + os.path.abspath(REPORT))

if __name__ == "__main__":
    main()
