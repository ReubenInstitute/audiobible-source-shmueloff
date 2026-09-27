#!/usr/bin/env python3
import glob
import hashlib
import os
import shutil
import subprocess
import sys

import jinja2

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DEBIAN = os.path.join(REPO, "debian")
TEMPLATES = os.path.join(DEBIAN, "templates")
SOURCE = os.path.normpath(os.path.join(REPO, "..", "audiobible-data", "source"))
BUILD_ROOT = os.path.join(REPO, "build")
OUTDIR = os.path.join(BUILD_ROOT, "dist")
STAGING = os.path.join(BUILD_ROOT, "staging")
VERSION = "1.0"
MAINTAINER = "Reuben Institute <reubeninstitute@gmail.com>"

JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES),
    keep_trailing_newline=True,
)


def discover_chapter_packages():
    pkgs = []
    for book_dir in sorted(glob.glob(os.path.join(SOURCE, "[0-9][0-9]"))):
        book = os.path.basename(book_dir)
        for mp3 in sorted(glob.glob(os.path.join(book_dir, "*.mp3"))):
            chapter = os.path.splitext(os.path.basename(mp3))[0]
            pkgs.append(f"audiobible-shmueloff-source-{book}-{chapter}")
    return pkgs


def discover_book_mp3s():
    return sorted(glob.glob(os.path.join(SOURCE, "[0-9][0-9].mp3")))


def write_control(pkg_root, pkg, depends, description):
    debian_dir = os.path.join(pkg_root, "DEBIAN")
    os.makedirs(debian_dir, exist_ok=True)
    os.chmod(debian_dir, 0o755)

    size_kb = sum(
        os.path.getsize(os.path.join(dirpath, f))
        for dirpath, _, files in os.walk(pkg_root)
        if "DEBIAN" not in dirpath.split(os.sep)
        for f in files
    ) // 1024

    depends_list = [f"{d} (= {VERSION})" for d in depends]
    rendered = JINJA_ENV.get_template("control-meta.j2").render(
        pkg=pkg,
        version=VERSION,
        maintainer=MAINTAINER,
        size_kb=size_kb,
        depends=depends_list,
        description=description,
    )
    control = os.path.join(debian_dir, "control")
    with open(control, "w") as fh:
        fh.write(rendered)
    os.chmod(control, 0o644)
    return debian_dir


def embed_scripts(debian_dir):
    for name in ("bump-version.sh", "fast-build.sh"):
        src = os.path.join(DEBIAN, name)
        dst = os.path.join(debian_dir, name)
        shutil.copy(src, dst)
        os.chmod(dst, 0o755)


def write_md5sums(pkg_root):
    debian_dir = os.path.join(pkg_root, "DEBIAN")
    lines = []
    for dirpath, _, files in os.walk(pkg_root):
        if "DEBIAN" in dirpath.split(os.sep):
            continue
        for f in sorted(files):
            path = os.path.join(dirpath, f)
            rel = os.path.relpath(path, pkg_root)
            with open(path, "rb") as fh:
                digest = hashlib.md5(fh.read()).hexdigest()
            lines.append(f"{digest}  {rel}\n")
    md5sums = os.path.join(debian_dir, "md5sums")
    with open(md5sums, "w") as fh:
        fh.writelines(sorted(lines))
    os.chmod(md5sums, 0o644)


def build_deb(pkg_root, pkg):
    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, f"{pkg}_{VERSION}_all.deb")
    env = dict(os.environ, TMPDIR=OUTDIR)
    subprocess.run(
        ["dpkg-deb", "-b", "-Zgzip", "-z1", pkg_root, out], check=True, env=env
    )
    shutil.rmtree(pkg_root)
    return out


def main():
    pkg = "audiobible-shmueloff-source"
    chapter_pkgs = discover_chapter_packages()
    book_mp3s = discover_book_mp3s()
    if not chapter_pkgs:
        sys.exit("No chapter packages discovered -- run debian/bootstrap.py first.")

    pkg_root = os.path.join(STAGING, pkg)
    if os.path.exists(pkg_root):
        shutil.rmtree(pkg_root)
    payload_dir = os.path.join(pkg_root, "usr", "share", "audiobible", "source")
    os.makedirs(payload_dir, exist_ok=True)
    for d in ("usr", "usr/share", "usr/share/audiobible", "usr/share/audiobible/source"):
        os.chmod(os.path.join(pkg_root, d), 0o755)
    for mp3 in book_mp3s:
        dst = os.path.join(payload_dir, os.path.basename(mp3))
        shutil.copy(mp3, dst)
        os.chmod(dst, 0o644)

    description = (
        "Original 1970s recordings (Abraham Shmueloff), fixed source audio\n"
        " Original ~1970 recordings of Abraham Shmueloff reading the entire Hebrew\n"
        " Bible, the fixed source audio everything else in AudioBible is derived\n"
        " from."
    )
    debian_dir = write_control(pkg_root, pkg, chapter_pkgs, description)
    embed_scripts(debian_dir)
    write_md5sums(pkg_root)
    out = build_deb(pkg_root, pkg)
    print(f"built {out}")


if __name__ == "__main__":
    main()
