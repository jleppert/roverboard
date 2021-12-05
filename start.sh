#!/bin/bash

source ./env/bin/activate
./LibreVNA-GUI --no-gui --port=19542 &
python3 ./webserver.py
