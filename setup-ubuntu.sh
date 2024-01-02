#!/bin/sh
sudo apt-get install -y python3-virtualenv
python -m venv .venv
. .venv/bin/activate
pip install holidays
