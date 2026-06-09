#!/bin/bash

echo "Setting up IHI UE5 Environment..."

export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$IHI_DIR:/usr/local/lib/:/usr/lib/x86_64-linux-gnu/"

echo "$LD_LIBRARY_PATH"
