#!/usr/bin/env bash
# DDL: uninstall at the user level. Options and what it does: python3 bin/ddl_setup.py --help
set -euo pipefail
exec python3 -I "$(dirname "$0")/ddl_setup.py" uninstall "$@"
