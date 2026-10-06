#!/usr/bin/env bash

set -e
set -x

# pytest-xdist workers. Set PYTEST_XDIST_WORKERS to a number to change it, to "auto" for one per
# CPU, or to 0 (or empty) to run the tests serially (e.g. to debug an ordering problem). 1 starts
# a single worker, which still exercises the per-worker setup (PYTEST_XDIST_WORKER).
# Only an unset variable means "auto"; `:-` would treat an empty one the same way.
workers="${PYTEST_XDIST_WORKERS-auto}"
parallel=()
case "$workers" in
  ""|0|false|off) ;;
  *) parallel=(-n "$workers") ;;
esac

pytest "${parallel[@]}" --cov=app --cov-report=term-missing app/tests "${@}"
