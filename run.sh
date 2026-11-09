#!/usr/bin/env bash
cd "$(dirname "$(readlink -f "$0")")"
exec python3 silverwolf.py "$@"
