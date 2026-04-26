#!/bin/sh -e
set -x

ruff check src tests docs_src --fix
ruff format src tests docs_src
