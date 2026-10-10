#!/bin/sh
set -eu
cd "$(dirname "$0")"
python -m src.analyze
python -m src.report
python -m unittest discover -s tests -v
if [ "${1:-}" = "--rebuild-workbook" ]; then
  node src/build_workbook.mjs
fi
