#!/usr/bin/env bash

set -e
set -x

mypy src
ty check src
ruff check src tests docs_src
ruff format src tests docs_src --check
