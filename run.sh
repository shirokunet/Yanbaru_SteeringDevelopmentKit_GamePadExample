#!/bin/bash

while true
do
    echo 'Use X-switch on F310 gamepad'
    echo 'Step 1: Push "Logicool" button to calibrate ODrive.'
    echo 'Step 2: Push "START" button to start close loop.'
    echo 'Step 3: Use "Right X" Joystick to control steering.'
    echo 'Step 4: Use "LT" and "RT" button to control two pedals.'
    echo 'Step 5: Push "BACK" button to end close loop.'
    echo 'Type Ctrl+Z to end this script.'
    killall -9 python3
    python3 main.py
    printf '\n'
    sleep 3
done
