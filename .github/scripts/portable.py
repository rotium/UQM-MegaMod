#!/usr/bin/env python3
"""Package UQM and test the exact archives. Only Python's standard library is used."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
NAME = "UQM-MegaMod"

def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, errors="replace", **kwargs)

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def write(path, text, executable=False):
    path.write_text(text, encoding="utf-8", newline="\n")
    if executable:
        path.chmod(0o755)

def stage(platform, binary, content):
    dest = ROOT / "stage" / NAME
    dest.mkdir(parents=True, exist_ok=False)
    exe = dest / ("UrQuanMasters.exe" if platform == "windows" else "UrQuanMasters")
    shutil.copy2(binary, exe)
    shutil.copytree(content, dest / "content",
                    ignore=shutil.ignore_patterns(".git", ".github", ".gitignore", "desktop.ini"))
    for required in ("version", "uqm.rmp", "uqm.key", "menu.key", "base/gamestrings.txt",
                     "addons/mm-hd", "addons/mm-3dovoice"):
        if not (dest / "content" / required).exists():
            raise RuntimeError("Missing required content: " + required)
    licenses = dest / "licenses"
    shutil.copytree(ROOT / "licenses", licenses)
    shutil.copytree(ROOT / "dev-lib" / "licenses", licenses / "upstream-libraries")
    shutil.copytree(ROOT / "doc" / "release", dest / "docs")
    for name in ("NOTICE", "README.md", "INSTALL"):
        if (ROOT / name).exists():
            shutil.copy2(ROOT / name, dest / "docs" / name)
    dependencies = []
    if platform == "windows":
        bindir = Path(sys.executable).parent
        available = {p.name.lower(): p for p in bindir.glob("*.dll")}
        system = Path(os.environ["SystemRoot"]) / "System32"
        queue = [exe]
        visited = set()
        while queue:
            current = queue.pop()
            for name in re.findall(r"DLL Name:\s*(\S+)", run("objdump", "-p", str(current))):
                key = name.lower()
                if key in visited:
                    continue
                visited.add(key)
                if key.startswith(("api-ms-win-", "ext-ms-win-")):
                    continue
                if key in available:
                    origin = available[key]
                    target = dest / origin.name
                    shutil.copy2(origin, target)
                    queue.append(target)
                    dependencies.append(origin.name)
                elif not (system / name).exists():
                    raise RuntimeError("Unresolved Windows import: " + name)
        source_licenses = bindir.parent / "share" / "licenses"
        if source_licenses.exists():
            shutil.copytree(source_licenses, licenses / "msys2")
        write(dest / "DEPENDENCY-VERSIONS.txt", run("pacman", "-Q"))
        write(dest / "Play.cmd",
              '@echo off\ncd /d "%~dp0"\n"UrQuanMasters.exe" --contentdir="%~dp0content" %*\n')
        instructions = "Windows 10/11 x86-64: extract the entire ZIP, then double-click Play.cmd."
    else:
        libdir = dest / "lib"
        libdir.mkdir()
        output = run("ldd", str(exe))
        if "not found" in output:
            raise RuntimeError(output)
        host = re.compile(r"^(?:ld-linux|lib(?:c|m|dl|pthread|rt|resolv|util)\.so|"
                          r"lib(?:GL|EGL|GLX|GLdispatch|drm)[.-])")
        for soname, source in re.findall(r"^\s*(\S+) => (/\S+) \(", output, re.M):
            if host.match(soname):
                continue
            shutil.copy2(source, libdir / soname)
            dependencies.append(soname)
        subprocess.check_call(["patchelf", "--set-rpath", "$ORIGIN/lib", str(exe)])
        for lib in libdir.iterdir():
            subprocess.check_call(["patchelf", "--set-rpath", "$ORIGIN", str(lib)])
        for copyright_file in Path("/usr/share/doc").glob("*/copyright"):
            target = licenses / "ubuntu-packages" / copyright_file.parent.name
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(copyright_file, target / "copyright")
        write(dest / "DEPENDENCY-VERSIONS.txt", run("dpkg-query", "-W")
              + "\nBundled SDL2: 2.32.10, built from the included SDL2-SOURCE.tar.gz\n")
        shutil.copy2("/tmp/uqm-sdl/SDL2-2.32.10.tar.gz", dest / "SDL2-SOURCE.tar.gz")
        sdl_license = licenses / "built-sdl2"
        sdl_license.mkdir()
        shutil.copy2("/tmp/uqm-sdl/SDL2-2.32.10/LICENSE.txt", sdl_license / "LICENSE.txt")
        exe.chmod(0o755)
        write(dest / "Play.sh", '#!/bin/sh\nset -eu\n'
              'GAME_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
              'export LD_LIBRARY_PATH="$GAME_DIR/lib"\n'
              'exec "$GAME_DIR/UrQuanMasters" --contentdir="$GAME_DIR/content" "$@"\n', True)
        instructions = ("Linux x86-64, glibc 2.35+ (Ubuntu 22.04+): extract the entire ZIP,\n"
                        "then run ./Play.sh. If your extractor drops permissions, run\n"
                        "chmod +x Play.sh UrQuanMasters first. Requires a desktop session\n"
                        "and the host graphics/audio drivers. No game-library installation is needed.")
    subprocess.check_call(["git", "-c", "safe.directory=" + str(ROOT), "archive", "--format=zip",
                           "--output=" + str(dest / "GAME-SOURCE.zip"), "HEAD"], cwd=ROOT)
    write(dest / "PLAY-README.txt", instructions + "\n\n"
          "All base content, HD content, voices, and DOS/3DO mode assets are included.\n"
          "Choose graphics, sound, and mode preferences in the game's setup menu.\n"
          "No network download is required to play. Saves use the game's user-profile directory.\n"
          "Code, content, and third-party libraries retain their respective licenses;\n"
          "see licenses/, docs/, and content/README.md. Content is generally CC BY-NC-SA 2.5.\n"
          "GAME-SOURCE.zip contains the exact game source and this cloud build workflow.\n"
          "Dependency package versions are in DEPENDENCY-VERSIONS.txt.\n")
    manifest = {
        "platform": platform, "architecture": "x86_64",
        "game_commit": os.environ["GITHUB_SHA"],
        "content_commit": os.environ["CONTENT_SHA"],
        "source_repository": os.environ["GITHUB_REPOSITORY"],
        "run_url": "https://github.com/" + os.environ["GITHUB_REPOSITORY"]
                   + "/actions/runs/" + os.environ["GITHUB_RUN_ID"],
        "bundled_libraries": sorted(dependencies),
        "files": {str(p.relative_to(dest)).replace("\\", "/"): digest(p)
                  for p in sorted(dest.rglob("*")) if p.is_file()},
    }
    write(dest / "BUILD-MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    archive = dist / (NAME + "-" + platform + "-x86_64.zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(dest.rglob("*")):
            if p.is_file():
                z.write(p, str(p.relative_to(dest.parent)).replace("\\", "/"))
    if archive.stat().st_size >= 2 * 1024 ** 3:
        raise RuntimeError("ZIP exceeds GitHub's 2 GiB release asset limit")
    print(str(archive), archive.stat().st_size, digest(archive), flush=True)

def smoke(archive):
    with tempfile.TemporaryDirectory(prefix="UQM package test ") as temp:
        base = Path(temp)
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None:
                raise RuntimeError("Corrupt ZIP")
            z.extractall(base)
            if os.name != "nt":
                for info in z.infolist():
                    mode = (info.external_attr >> 16) & 0o777
                    if mode:
                        (base / info.filename).chmod(mode)
        game = base / NAME
        manifest = json.loads((game / "BUILD-MANIFEST.json").read_text(encoding="utf-8"))
        for name, expected in manifest["files"].items():
            if digest(game / name) != expected:
                raise RuntimeError("Checksum mismatch: " + name)
        windows = manifest["platform"] == "windows"
        executable = game / ("UrQuanMasters.exe" if windows else "Play.sh")
        env = dict(os.environ)
        if windows:
            env = {key.upper(): value for key, value in env.items()}
            env["PATH"] = str(Path(env["SYSTEMROOT"]) / "System32")
        env["SDL_AUDIODRIVER"] = "dummy"
        version = subprocess.run([str(executable), "--version"], cwd=base, env=env,
                                 capture_output=True, timeout=30)
        print(version.stdout.decode(errors="replace") + version.stderr.decode(errors="replace"))
        if version.returncode != 0:
            raise RuntimeError("Version check failed: " + str(version.returncode))
        logfile = base / "startup.log"
        command = [str(executable), "--contentdir=" + str(game / "content"),
                   "--configdir=" + str(base / "profile"), "--logfile=" + str(logfile),
                   "--windowed", "--res=640x480", "--nogl", "--renderer=software",
                   "--sound=none", "--skipintro"]
        with (base / "process.log").open("wb") as output:
            process = subprocess.Popen(command, cwd=base, env=env, stdout=output, stderr=output)
            try:
                time.sleep(25)
                if process.poll() is not None:
                    raise RuntimeError("Game exited during startup: " + str(process.returncode))
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                log = logfile.read_text(errors="replace") if logfile.exists() else ""
                print(log, flush=True)
                print((base / "process.log").read_text(errors="replace"), flush=True)
        if not logfile.exists():
            raise RuntimeError("Game did not create its startup log")
        if re.search(r"fatal error|could not find content|error loading kernel", log, re.I):
            raise RuntimeError("Fatal startup/content error")
        print("PASS: ZIP integrity, version, and 25-second graphical startup.", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    package = sub.add_parser("package")
    package.add_argument("platform", choices=("linux", "windows"))
    package.add_argument("binary", type=Path)
    package.add_argument("content", type=Path)
    test = sub.add_parser("smoke")
    test.add_argument("archive", type=Path)
    args = parser.parse_args()
    if args.command == "package":
        stage(args.platform, args.binary, args.content)
    else:
        smoke(args.archive)
