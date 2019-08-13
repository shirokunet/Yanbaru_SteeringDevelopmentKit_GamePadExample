#!/bin/bash

while true
do
    echo 'Type Ctrl+Z to end this script.'
    killall -9 python3
    python3 main.py
    printf '\n'
    sleep 3
done
