#!/bin/sh

echo "[INIT] Clearing old log files..."

rm -f /var/www/logs/~log.log
rm -f /var/www/logs/~log.log

rm -f /var/www/logs/~error.log
rm -f /var/www/logs/~error.log

rm -f /var/www/logs/~complete.log
rm -f /var/www/logs/~complete.log

rm -f ~log.log
rm -f ~log.log

rm -f ~error.log
rm -f ~error.log

rm -f ~complete.log
rm -f ~complete.log

touch /var/www/logs/~log.log /var/www/logs/~error.log /var/www/logs/~complete.log
chmod 666 /var/www/logs/~log.log
chmod 666 /var/www/logs/~error.log
chmod 666 /var/www/logs/~complete.log

chmod 666 ~log.log
chmod 666 ~error.log
chmod 666 ~complete.log

exec nginx -g "daemon off;"