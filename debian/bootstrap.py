#!/usr/bin/env python3
import argparse
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
BUILD_ROOT = os.path.join(REPO, "build")
SDIST = os.path.join(BUILD_ROOT, "sdist")
OUTDIR = os.path.join(BUILD_ROOT, "dist")
STAGING = os.path.join(BUILD_ROOT, "staging")
VERSION = "1.0"
MAINTAINER = "Reuben Institute <reubeninstitute@gmail.com>"

JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES),
    keep_trailing_newline=True,
)


def extract_package(book, chapter, pkg_root):
    pattern = os.path.join(SDIST, f"audiobible-shmueloff-source-{book}-{chapter}_*.deb")
    matches = glob.glob(pattern)
    if not matches:
        return False
    deb_path = matches[0]
    os.makedirs(os.path.dirname(pkg_root), exist_ok=True)
    subprocess.run(["dpkg-deb", "-R", deb_path, pkg_root], check=True)
    return True


def discover_chapters():
    chapters = {}
    for deb in glob.glob(os.path.join(SDIST, "audiobible-shmueloff-source-*-*_*.deb")):
        name = os.path.basename(deb)
        pkg = name.split("_", 1)[0]
        parts = pkg.split("-")
        if len(parts) != 5:
            continue
        book, chapter = parts[3], parts[4]
        chapters[(book, chapter)] = None
    return chapters


def write_control(pkg_root, pkg, description):
    debian_dir = os.path.join(pkg_root, "DEBIAN")
    os.makedirs(debian_dir, exist_ok=True)
    os.chmod(debian_dir, 0o755)

    size_kb = sum(
        os.path.getsize(os.path.join(dirpath, f))
        for dirpath, _, files in os.walk(pkg_root)
        if "DEBIAN" not in dirpath.split(os.sep)
        for f in files
    ) // 1024

    rendered = JINJA_ENV.get_template("control.j2").render(
        pkg=pkg,
        version=VERSION,
        maintainer=MAINTAINER,
        size_kb=size_kb,
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


def build_chapter_package(book, chapter):
    pkg = f"audiobible-shmueloff-source-{book}-{chapter}"
    pkg_root = os.path.join(STAGING, pkg)
    if os.path.exists(pkg_root):
        shutil.rmtree(pkg_root)

    if not extract_package(book, chapter, pkg_root):
        return None, None

    description = (
        f"Original 1970s recordings (Abraham Shmueloff), book {book} chapter {chapter}\n"
        f" Original ~1970 recording of Abraham Shmueloff reading book {book} chapter\n"
        f" {chapter}, the fixed source audio everything else in AudioBible is derived\n"
        f" from."
    )
    debian_dir = write_control(pkg_root, pkg, description)
    embed_scripts(debian_dir)
    write_md5sums(pkg_root)
    return build_deb(pkg_root, pkg), pkg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("book", nargs="?", help="e.g. 01 -- build only this book")
    parser.add_argument("chapter", nargs="?", help="e.g. 001 -- build only this chapter (requires book)")
    args = parser.parse_args()

    if args.chapter and not args.book:
        sys.exit("chapter requires a book argument too")

    if not os.path.isdir(SDIST):
        sys.exit(f"{SDIST} not found -- nothing to source mp3s from")

    chapters = discover_chapters()
    if not chapters:
        sys.exit("No chapter packages found in sdist/ -- nothing to build.")

    if args.book:
        chapters = {
            (book, chapter): v
            for (book, chapter), v in chapters.items()
            if book == args.book and (args.chapter is None or chapter == args.chapter)
        }
        if not chapters:
            sys.exit(f"No chapters found matching book={args.book} chapter={args.chapter}")

    all_chapter_pkgs = []
    for book, chapter in sorted(chapters):
        out, pkg = build_chapter_package(book, chapter)
        if out is None:
            continue
        all_chapter_pkgs.append(pkg)
        print(f"built {out}")

    print(f"\n{len(all_chapter_pkgs)} chapter packages built")


if __name__ == "__main__":
    main()
