#!/usr/bin/env bash
# Owner: M2. Run on Laptop B before every demo run. Read-only checks, changes nothing.
set -u
source "$(dirname "$0")/lab.env"
fail=0
pass() { echo "PASS  $1"; }
bad()  { echo "FAIL  $1"; fail=1; }

ip -4 addr | grep -q "inet ${LAB_HOST_IP}/" && pass "lab IP ${LAB_HOST_IP} is configured" || bad "lab IP ${LAB_HOST_IP} missing"

ip route | grep -q '^default' && bad "default route present (internet reachable): $(ip route | grep '^default')" || pass "no default route"

if command -v nmcli >/dev/null; then
  [ "$(nmcli radio wifi)" = "disabled" ] && pass "Wi-Fi off" || bad "Wi-Fi is on"
fi

listening() { ss -ltnH | awk '{print $4}'; }
for p in 2222 8080; do
  listening | grep -qE "^${LAB_HOST_IP}:${p}$" && pass "decoy port ${p} bound to ${LAB_HOST_IP}" || bad "decoy port ${p} not bound to ${LAB_HOST_IP} (or bound wider)"
  listening | grep -qE "^(0\.0\.0\.0|\[::\]|\*):${p}$" && bad "port ${p} bound to all interfaces"
done
for p in 8000 5173; do
  if listening | grep -qE ":${p}$"; then
    listening | grep -qE "^127\.0\.0\.1:${p}$" && pass "SOC port ${p} on loopback only" || bad "SOC port ${p} bound beyond loopback"
  else
    bad "SOC port ${p} not listening"
  fi
done

docker ps --format '{{.Names}}' | grep -q dg-cowrie && pass "cowrie running" || bad "cowrie not running"
docker ps --format '{{.Names}}' | grep -q dg-web-decoy && pass "web decoy running" || bad "web decoy not running"
for c in dg-cowrie dg-web-decoy; do
  [ "$(docker inspect -f '{{.HostConfig.Privileged}}' $c 2>/dev/null)" = "false" ] && pass "$c not privileged" || bad "$c privileged or missing"
  docker inspect -f '{{range .Mounts}}{{.Source}} {{end}}' $c 2>/dev/null | grep -q docker.sock && bad "$c mounts the Docker socket"
done

grep -q 'backend *= *shell' "$(dirname "$0")/cowrie/cowrie.cfg" && pass "cowrie in emulated shell mode" || bad "cowrie backend is not shell"

curl -fsS "${BACKEND_URL}/api/health" >/dev/null 2>&1 && pass "backend health" || bad "backend health"

echo
[ $fail -eq 0 ] && echo "ALL PASS" || { echo "FIX FAILURES BEFORE ANY TRAFFIC"; exit 1; }
