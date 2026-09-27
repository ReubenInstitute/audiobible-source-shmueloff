#!/bin/sh
set -eu

dir="$1"
out="$2"

dpkg-deb -b -Zgzip -z1 "$dir" "$out"
