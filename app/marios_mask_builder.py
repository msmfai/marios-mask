#!/usr/bin/env python3
"""Small native GUI for building Mario's Mask from two user-owned ROMs."""

from __future__ import annotations

import os
import platform
import queue
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


APP_NAME = "Mario's Mask Builder"
DEFAULT_OUTPUT = "Mario's Mask.z64"


class BuilderError(RuntimeError):
    pass


def installed_root(executable: Path | None = None) -> Path:
    """Find payload/runtime beside a frozen executable or in the source tree."""
    executable = executable or Path(sys.executable)
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.extend(
            [
                executable.resolve().parent,
                executable.resolve().parent / "_internal",
                executable.resolve().parent.parent / "Resources",
            ]
        )
    candidates.append(Path(__file__).resolve().parents[1])
    for candidate in candidates:
        if (candidate / "payload" / "project" / "VERSION").is_file():
            return candidate
        if (candidate / "VERSION").is_file() and (candidate / "tools").is_dir():
            return candidate
    raise BuilderError("This app is incomplete. Download and extract the whole release again.")


def cache_root(system: str | None = None) -> Path:
    system = system or platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "MariosMask"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "MariosMask"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "marios-mask"


def materialize_project(root: Path) -> Path:
    packaged = root / "payload" / "project"
    if not packaged.is_dir():
        return root
    version = (packaged / "VERSION").read_text(encoding="utf-8").strip()
    target = cache_root() / version / "project"
    marker = target / ".marios-mask-payload"
    installed_version = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    if installed_version == version:
        return target
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(packaged, target)
    marker.write_text(version + "\n", encoding="utf-8")
    return target


def materialize_runtime(root: Path) -> Path:
    packaged = root / "runtime"
    if not packaged.is_dir() or platform.system() == "Windows":
        return packaged
    project = root / "payload" / "project"
    version = (project / "VERSION").read_text(encoding="utf-8").strip()
    target = cache_root() / version / "runtime"
    marker = target / ".marios-mask-runtime-ready"
    if marker.is_file():
        ensure_compiler_aliases(target)
        return target
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(packaged, target, symlinks=True)
    unpack = target / "bin" / "conda-unpack"
    python = target / "bin" / "python3"
    if unpack.is_file() and python.is_file():
        subprocess.run([str(python), str(unpack)], check=True, cwd=target)
    ensure_compiler_aliases(target)
    marker.write_text("ready\n", encoding="utf-8")
    return target


def ensure_compiler_aliases(runtime: Path, system: str | None = None) -> None:
    """Expose compiler names hard-coded by the pinned decomp host-tool builds."""
    runtime_bin = runtime / "bin"
    make = runtime_bin / "make"
    gmake = runtime_bin / "gmake"
    if not make.is_file():
        raise BuilderError("The packaged GNU Make runtime is incomplete.")
    if not gmake.exists():
        gmake.symlink_to(make.name)
    system = system or platform.system()
    if system == "Darwin":
        compiler_pairs = (("clang", ("cc", "gcc")), ("clang++", ("c++", "g++")))
    else:
        c_candidates = sorted(runtime_bin.glob("*-gcc"))
        cxx_candidates = sorted(runtime_bin.glob("*-g++"))
        if not c_candidates or not cxx_candidates:
            raise BuilderError("The packaged compiler runtime is incomplete.")
        compiler_pairs = (
            (c_candidates[0].name, ("cc", "gcc")),
            (cxx_candidates[0].name, ("c++", "g++")),
        )
    for compiler, aliases in compiler_pairs:
        target = runtime_bin / compiler
        if not target.is_file():
            raise BuilderError("The packaged compiler runtime is incomplete.")
        for alias in aliases:
            link = runtime_bin / alias
            if not link.exists():
                link.symlink_to(target.name)


def materialize_windows_python(root: Path) -> Path:
    packaged = root / "runtime" / "conda"
    project = root / "payload" / "project"
    version = (project / "VERSION").read_text(encoding="utf-8").strip()
    target = cache_root("Windows") / version / "python"
    marker = target / ".marios-mask-python-ready"
    if marker.is_file():
        return target
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(packaged, target)
    python = target / "python.exe"
    unpack = target / "Scripts" / "conda-unpack.exe"
    if not unpack.exists():
        unpack = target / "Scripts" / "conda-unpack-script.py"
    if unpack.exists():
        subprocess.run([str(python), str(unpack)], check=True, cwd=target)
    marker.write_text("ready\n", encoding="utf-8")
    return target


def _windows_unix_path(runtime: Path, path: Path) -> str:
    cygpath = runtime / "msys64" / "usr" / "bin" / "cygpath.exe"
    if not cygpath.is_file():
        raise BuilderError("The Windows build runtime is incomplete (cygpath is missing).")
    result = subprocess.run(
        [str(cygpath), "-u", str(path.resolve())],
        check=True,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return result.stdout.strip()


@dataclass(frozen=True)
class BuildInvocation:
    command: list[str]
    environment: dict[str, str]
    cwd: Path


def build_invocation(root: Path, sm64: Path, mm: Path, output: Path) -> BuildInvocation:
    project = materialize_project(root)
    runtime = materialize_runtime(root)
    script = project / "tools" / "build_from_roms.sh"
    if not script.is_file():
        raise BuilderError("The builder payload is incomplete.")

    environment = os.environ.copy()
    if (root / "payload" / "project").is_dir() and (root / "runtime").is_dir():
        # The packaged app carries its own compiler and host tools.  Tell the
        # shell builder not to prefer optional tools installed on the host.
        environment["DSCE_PACKAGED_RUNTIME"] = "1"
    work = cache_root() / "work"
    system = platform.system()
    if runtime.is_dir() and system == "Windows":
        msys = runtime / "msys64"
        python_root = materialize_windows_python(root)
        bash = msys / "usr" / "bin" / "bash.exe"
        if not bash.is_file():
            raise BuilderError("The Windows build runtime is incomplete (bash is missing).")
        unix_script = _windows_unix_path(runtime, script)
        unix_sm64 = _windows_unix_path(runtime, sm64)
        unix_mm = _windows_unix_path(runtime, mm)
        unix_output = _windows_unix_path(runtime, output)
        unix_work = _windows_unix_path(runtime, work)
        unix_python = _windows_unix_path(runtime, python_root / "python.exe")
        environment["PATH"] = os.pathsep.join(
            [
                str(python_root),
                str(msys / "usr" / "bin"),
                str(msys / "ucrt64" / "bin"),
                environment.get("PATH", ""),
            ]
        )
        environment["DSCE_WORK_DIR"] = unix_work
        environment["DSCE_PYTHON"] = unix_python
        environment["DSCE_MAKE"] = "make"
        command = [str(bash), "--noprofile", "--norc", unix_script, unix_sm64, unix_mm, unix_output]
    else:
        bash = Path("/bin/bash")
        if runtime.is_dir():
            runtime_bin = runtime / "bin"
            environment["PATH"] = os.pathsep.join([str(runtime_bin), environment.get("PATH", "")])
            if environment.get("DSCE_PACKAGED_RUNTIME") == "1":
                git_exec = runtime / "libexec" / "git-core"
                git_templates = runtime / "share" / "git-core" / "templates"
                certificates = runtime / "ssl" / "cacert.pem"
                if (
                    not (git_exec / "git-remote-https").is_file()
                    or not git_templates.is_dir()
                    or not certificates.is_file()
                ):
                    raise BuilderError("The packaged Git runtime is incomplete.")
                # Conda's Git binary retains its original CI prefix after
                # conda-unpack. Override its two compiled-in search paths.
                environment["GIT_EXEC_PATH"] = str(git_exec)
                environment["GIT_TEMPLATE_DIR"] = str(git_templates)
                environment["GIT_SSL_CAINFO"] = str(certificates)
                environment["SSL_CERT_FILE"] = str(certificates)
            python = runtime_bin / "python3"
            make = runtime_bin / "make"
            if python.exists():
                environment["DSCE_PYTHON"] = str(python)
            if make.exists():
                environment["DSCE_MAKE"] = str(make)
        environment["DSCE_WORK_DIR"] = str(work)
        builder_command = [str(bash), str(script), str(sm64), str(mm), str(output)]
        micromamba = runtime / "bin" / "micromamba"
        if micromamba.is_file():
            command = [str(micromamba), "run", "-p", str(runtime), *builder_command]
        else:
            command = builder_command
    return BuildInvocation(command, environment, project)


def validate_choices(sm64: str, mm: str, output: str) -> tuple[Path, Path, Path]:
    values = [value.strip() for value in (sm64, mm, output)]
    if not all(values):
        raise BuilderError("Choose both ROMs and where to save the new ROM.")
    sm64_path, mm_path, output_path = map(Path, values)
    if not sm64_path.is_file():
        raise BuilderError("The Super Mario 64 ROM could not be found.")
    if not mm_path.is_file():
        raise BuilderError("The Majora's Mask ROM could not be found.")
    if sm64_path.resolve() == mm_path.resolve():
        raise BuilderError("Choose two different ROM files.")
    if output_path.resolve() in {sm64_path.resolve(), mm_path.resolve()}:
        raise BuilderError("The new ROM cannot overwrite either original ROM.")
    return sm64_path, mm_path, output_path


def run_build(invocation: BuildInvocation, emit: Callable[[str], None]) -> int:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        invocation.command,
        cwd=invocation.cwd,
        env=invocation.environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=creationflags,
    )
    assert process.stdout is not None
    for line in process.stdout:
        emit(line.rstrip())
    return process.wait()


def main() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    try:
        root_path = installed_root()
    except BuilderError as error:
        messagebox.showerror(APP_NAME, str(error))
        return 1

    window = tk.Tk()
    window.title(APP_NAME)
    window.resizable(False, False)
    window.columnconfigure(1, weight=1)
    events: queue.Queue[tuple[str, object]] = queue.Queue()

    sm64_var = tk.StringVar()
    mm_var = tk.StringVar()
    output_var = tk.StringVar(value=str(Path.home() / "Desktop" / DEFAULT_OUTPUT))
    status_var = tk.StringVar(value="Choose your two US ROMs.")

    frame = ttk.Frame(window, padding=18)
    frame.grid(sticky="nsew")
    frame.columnconfigure(1, weight=1)

    filters = [
        ("Nintendo 64 ROM", "*.z64 *.v64 *.n64 *.rom *.zip *.gz"),
        ("All files", "*"),
    ]

    def choose_input(variable: tk.StringVar, title: str) -> None:
        selected = filedialog.askopenfilename(title=title, filetypes=filters)
        if selected:
            variable.set(selected)

    def choose_output() -> None:
        selected = filedialog.asksaveasfilename(
            title="Save Mario's Mask ROM",
            initialfile=DEFAULT_OUTPUT,
            defaultextension=".z64",
            filetypes=[("Z64 ROM", "*.z64")],
        )
        if selected:
            output_var.set(selected)

    rows = [
        ("Super Mario 64 ROM", sm64_var, lambda: choose_input(sm64_var, "Choose Super Mario 64 (US)")),
        ("Majora's Mask ROM", mm_var, lambda: choose_input(mm_var, "Choose Majora's Mask (US)")),
        ("New ROM", output_var, choose_output),
    ]
    for row, (label, variable, callback) in enumerate(rows):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=6)
        ttk.Entry(frame, textvariable=variable, width=54).grid(row=row, column=1, sticky="ew", pady=6)
        ttk.Button(frame, text="Browse…", command=callback).grid(row=row, column=2, padx=(10, 0), pady=6)

    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(14, 5))
    ttk.Label(frame, textvariable=status_var).grid(row=4, column=0, columnspan=3, sticky="w")

    details = tk.Text(frame, width=82, height=14, wrap="word", state="disabled")
    details_visible = False

    def append_detail(line: str) -> None:
        details.configure(state="normal")
        details.insert("end", line + "\n")
        details.see("end")
        details.configure(state="disabled")

    def toggle_details() -> None:
        nonlocal details_visible
        details_visible = not details_visible
        details_button.configure(text="Hide details" if details_visible else "Show details")
        if details_visible:
            details.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        else:
            details.grid_remove()

    def worker(sm64_path: Path, mm_path: Path, output: Path) -> None:
        try:
            events.put(("status", "Preparing the build tools…"))
            invocation = build_invocation(root_path, sm64_path, mm_path, output)
            code = run_build(invocation, lambda line: events.put(("line", line)))
            events.put(("done", (code, output)))
        except Exception as error:  # shown to the user and retained in details
            events.put(("error", str(error)))

    def start_build() -> None:
        try:
            sm64_path, mm_path, output_path = validate_choices(
                sm64_var.get(), mm_var.get(), output_var.get()
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except (BuilderError, OSError, subprocess.SubprocessError) as error:
            messagebox.showerror(APP_NAME, str(error))
            return
        details.configure(state="normal")
        details.delete("1.0", "end")
        details.configure(state="disabled")
        build_button.configure(state="disabled")
        progress.start(12)
        status_var.set("Building… The first build takes a while; later ones are faster.")
        threading.Thread(
            target=worker, args=(sm64_path, mm_path, output_path), daemon=True
        ).start()

    def poll() -> None:
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == "line":
                    line = str(value)
                    append_detail(line)
                    if line.startswith(("Cloning", "Extracting", "Building")):
                        status_var.set(line)
                elif kind == "status":
                    status_var.set(str(value))
                elif kind == "done":
                    code, output_path = value
                    progress.stop()
                    build_button.configure(state="normal")
                    if code == 0 and Path(output_path).is_file():
                        status_var.set("Done! Your Mario's Mask ROM is ready.")
                        messagebox.showinfo(APP_NAME, f"Done!\n\nSaved to:\n{output_path}")
                    else:
                        status_var.set("Build failed. Open details to see why.")
                        messagebox.showerror(APP_NAME, "The build failed. Click Show details for the error.")
                elif kind == "error":
                    progress.stop()
                    build_button.configure(state="normal")
                    append_detail(str(value))
                    status_var.set("Build failed. Open details to see why.")
                    messagebox.showerror(APP_NAME, str(value))
        except queue.Empty:
            pass
        window.after(100, poll)

    controls = ttk.Frame(frame)
    controls.grid(row=5, column=0, columnspan=3, pady=(14, 0))
    build_button = ttk.Button(controls, text="Build Mario's Mask", command=start_build)
    build_button.grid(row=0, column=0, padx=6)
    details_button = ttk.Button(controls, text="Show details", command=toggle_details)
    details_button.grid(row=0, column=1, padx=6)

    ttk.Label(
        frame,
        text="Works with N64 ROMs, including .zip and .gz. Your ROMs stay on this computer.",
    ).grid(row=6, column=0, columnspan=3, pady=(12, 0))

    window.after(100, poll)
    window.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
