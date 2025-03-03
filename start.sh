#!/bin/env bash
git pull

if [ ! -d "venv" ]; then
  python -m venv venv
fi

./venv/bin/pip install -r requirements.txt
./venv/bin/python app.py

