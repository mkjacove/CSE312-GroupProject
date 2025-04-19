#!/bin/sh

echo "[INIT] Clearing access.log and error.log..."
: > /var/www/logs/access.log
: > /var/www/logs/error.log

exec nginx -g "daemon off;"