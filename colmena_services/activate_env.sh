#!/bin/bash
cd "$1" || { echo "Failed to cd into $1"; exit 1; }  # Prevents continuing if cd fails
source /home/pablo/myenv/bin/activate

if [ -n "$2" ]; then
    eval "$2"  # Ensures proper execution with arguments
fi

exec bash  # Keeps terminal open