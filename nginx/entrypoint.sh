#!/bin/sh

echo "[INIT] Clearing old log files..."

# Remove any duplicated or rotated logs
rm -f /var/www/logs/*.log*

# Re-create empty logs
touch /var/www/logs/access.log /var/www/logs/error.log
chmod 666 /var/www/logs/*.log

# Start Nginx
exec nginx -g "daemon off;"