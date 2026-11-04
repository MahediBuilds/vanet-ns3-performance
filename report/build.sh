#!/bin/bash
# Builds report/VANET_NS3_AAT_Report.docx and .pdf from the committed results.
#
# Two passes: render once to find the page numbers, then rebuild with a correct
# table of contents and check that the numbers did not move.
#
# Needs: Python with the packages in report/requirements.txt, and LibreOffice
# (soffice) on PATH. Set PYTHON to choose the interpreter (default: the repo's
# .venv if it exists, else python3). Pass --figures to redraw report/figures/.
set -euo pipefail

REPORT="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(dirname "$REPORT")"
BUILD="$REPORT/build"
NAME=VANET_NS3_AAT_Report

if [ -z "${PYTHON:-}" ]; then
  if [ -x "$PROJ/.venv/bin/python" ]; then PYTHON="$PROJ/.venv/bin/python"; else PYTHON=python3; fi
fi
PY="$PYTHON -W ignore"
command -v soffice >/dev/null || { echo "soffice (LibreOffice) not found on PATH" >&2; exit 1; }

mkdir -p "$BUILD"
cd "$BUILD"
pdf() { soffice -env:UserInstallation="file://$BUILD/lo_profile" --headless --convert-to pdf --outdir . "$1" >/dev/null 2>&1; }

if [ "${1:-}" = "--figures" ]; then
  $PY "$REPORT/make_figures.py" "$PROJ" "$REPORT/figures"
fi

$PY "$REPORT/build_report.py" "$PROJ" "$REPORT/figures" "$REPORT/logo.jpeg" pass1.docx | tail -1
pdf pass1.docx
$PY "$REPORT/find_pages.py" pass1.pdf pass1.docx.keys.json pages.json | cut -c1-160
$PY "$REPORT/build_report.py" "$PROJ" "$REPORT/figures" "$REPORT/logo.jpeg" final.docx pages.json | tail -1
pdf final.docx
$PY "$REPORT/find_pages.py" final.pdf final.docx.keys.json pages_check.json >/dev/null
$PY -c "import json; a=json.load(open('pages.json')); b=json.load(open('pages_check.json')); print('TOC page numbers stable' if a==b else 'TOC MISMATCH: '+str({k:(a[k],b.get(k)) for k in a if a[k]!=b.get(k)}))"

cp final.docx "$REPORT/$NAME.docx"
cp final.pdf "$REPORT/$NAME.pdf"
echo "Wrote $REPORT/$NAME.docx and $REPORT/$NAME.pdf"
