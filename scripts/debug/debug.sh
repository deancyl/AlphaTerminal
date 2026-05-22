#!/bin/bash
# AlphaTerminal Debug Script
# Usage: ./scripts/debug/debug.sh <command> [--json]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

command="${1:-help}"
json_output="${2:-}"

case "$command" in
    quick)
        echo "Running quick health check..."
        python3 "$SCRIPT_DIR/quick_check.py" $json_output
        ;;
    security)
        echo "Running security audit..."
        python3 "$SCRIPT_DIR/security_check.py" $json_output
        ;;
    help|--help|-h)
        echo "AlphaTerminal Debug Script"
        echo "Usage: $0 <command> [--json]"
        echo ""
        echo "Commands:"
        echo "  quick     Run quick health check"
        echo "  security  Run security audit"
        echo "  help      Show this help message"
        echo ""
        echo "Options:"
        echo "  --json    Output in JSON format"
        ;;
    *)
        echo "Unknown command: $command"
        exit 1
        ;;
esac