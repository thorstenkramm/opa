#!/usr/bin/env bash
set -e

BACKUP=/tmp/opa/last/backup.xbstream
TEMP=$(mktemp -d)
xbstream -x < "$BACKUP" -C "$TEMP"
echo "✅ Unpacking completed"
ls -l "$TEMP"
xtrabackup --decompress --remove-original --target-dir="$TEMP"
echo "✅ Decompressing completed"
ls -l "$TEMP"
xtrabackup --prepare --target-dir="$TEMP"
echo "✅ Prepare completed"
systemctl stop mysql
rm -rf /var/lib/mysql/*
xtrabackup --copy-back --target-dir="$TEMP"
rm -rf "${TEMP}"
chown -R mysql:mysql /var/lib/mysql
systemctl start mysql
echo "✅ MySQL started"
mysql -e "SHOW DATABASES"
