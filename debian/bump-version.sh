#!/bin/sh
set -eu

dir="$1"
control="$dir/DEBIAN/control"

old="$(grep '^Version:' "$control" | awk '{print $2}')"
major="${old%.*}"
minor="${old#*.}"
new="$major.$((minor + 1))"

sed -i "s/^Version:.*/Version: $new/" "$control"

echo "Bumped $dir from $old to $new"
