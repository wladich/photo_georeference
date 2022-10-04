#!/bin/bash

set -e

BASE="$(dirname $0)"
cd "$BASE"

echo 'pylint...'
pylint ./*.py photo_georeference
echo 'Black...'
black --diff --check -q .
echo 'flake8...'
flake8

echo All checks passed.
