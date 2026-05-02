#!/usr/bin/env bash
#===============================================================================
# Database Debug Script v2.1
#===============================================================================

set -uo pipefail

DB_PATH="backend/app/db/alphaterminal.db"
BACKEND_DIR="$(dirname "$0")/../.."

# 尝试多个路径
for try_path in "$DB_PATH" "$BACKEND_DIR/$DB_PATH" "backend/tests/database.db" "$(dirname "$0")/../../backend/tests/database.db"; do
    if [ -f "$try_path" ]; then
        DB_PATH="$try_path"
        break
    fi
done

if [ ! -f "$DB_PATH" ]; then
    echo "Database file not found"
    echo "Searched paths:"
    echo "  - backend/app/db/alphaterminal.db"
    echo "  - backend/tests/database.db"
    exit 1
fi

echo "Database: $DB_PATH"
echo "Size: $(du -h "$DB_PATH" | cut -f1)"

# Integrity check
integrity=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>/dev/null)
if [ "$integrity" = "ok" ]; then
    echo "Integrity: OK"
else
    echo "Integrity: FAILED"
    exit 1
fi

# Table counts
echo ""
echo "Tables:"
for table in $(sqlite3 "$DB_PATH" ".tables" 2>/dev/null | tr ' ' '\n' | sort -u); do
    if [ -n "$table" ]; then
        count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM ${table};" 2>/dev/null)
        echo "  ${table}: ${count} rows"
    fi
done
