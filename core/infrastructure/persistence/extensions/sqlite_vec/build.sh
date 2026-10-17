#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

gcc -O3 -fPIC -shared \
    -include sys/types.h \
    "$SCRIPT_DIR/sqlite-vec.c" \
    -o "$SCRIPT_DIR/vec0.so" \
    -lm

echo "Собрано: $SCRIPT_DIR/vec0.so"
