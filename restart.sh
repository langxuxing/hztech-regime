#!/usr/bin/env bash
DIR="$(dirname "$0")"
"$DIR/scripts/stop-all.sh" "$@"
sleep 2
exec "$DIR/scripts/start-all.sh" "$@"
