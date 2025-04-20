#!/bin/sh

echo "[INIT] Clearing old log files..."

rm -f /var/www/logs/access.log
rm -f /var/www/logs/error.log
rm -f /var/www/logs/*.log


touch /var/www/logs/access.log /var/www/logs/error.log
chmod 666 /var/www/logs/access.log
chmod 666 /var/www/logs/error.log

exec nginx -g "daemon off;"