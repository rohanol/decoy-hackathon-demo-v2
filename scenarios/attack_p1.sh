#!/usr/bin/env bash
# M4. Run on Laptop A in the isolated cable lab only.
set -euo pipefail
if [ "$#" -ne 1 ] || [ "$1" != "192.168.77.20" ]; then
  echo 'Refusing: only the lab decoy 192.168.77.20 is allowed' >&2
  exit 1
fi
command -v curl >/dev/null
WEB='http://192.168.77.20:8080'
# Deterministic gobuster-style probe sequence: R08 hidden-path/404 thresholds.
for path in /admin /administrator /.env /.git/HEAD /.git/config /backup.zip /backup /phpmyadmin /wp-admin /wp-login.php /server-status /config.php /db.sql /api/debug; do
  curl --noproxy '*' --connect-timeout 3 --max-time 10 -sS -o /dev/null -w "${path} %{http_code}\n" "$WEB$path"
  sleep "${STEP_DELAY:-0.2}"
done
for user in admin root guest; do
  curl --noproxy '*' --connect-timeout 3 --max-time 10 -sS -o /dev/null -w "login ${user} %{http_code}\n" \
    --data-urlencode "username=$user" --data-urlencode 'password=DGLAB-Wrong-Login' "$WEB/login"
done
