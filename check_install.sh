#!/bin/bash
cd "$(dirname "$0")"
# Install sharp with proper PATH
export PATH="$PWD/node_bin:$PATH"
./node_bin/npm rebuild sharp 2>&1 || echo "Sharp rebuild may have issues but continuing..."
# Verify @graphmemory/server
./node_bin/node -e "console.log(require('@graphmemory/server').version || 'loaded')" 2>&1 || echo "Direct require may need more setup"
