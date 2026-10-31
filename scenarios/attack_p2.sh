#!/usr/bin/env bash
# M4. Small fixed SSH guessing scenario, Laptop A only. No arbitrary wordlists.
set -euo pipefail
if [ "$#" -ne 1 ] || [ "$1" != "192.168.77.20" ]; then
  echo 'Refusing: only the lab decoy 192.168.77.20 is allowed' >&2
  exit 1
fi
command -v hydra >/dev/null
words=$(mktemp /tmp/dg_p2_words.XXXXXX)
trap 'rm -f "$words"' EXIT
printf '%s\n' DGLAB-Wrong-01 DGLAB-Wrong-02 DGLAB-Wrong-03 DGLAB-Wrong-04 DGLAB-Wrong-05 DGLAB-Wrong-06 > "$words"
# Hydra reports no successful password with a nonzero status on some versions.
# Print its actual outcome; the analyst verifies six failures in the SOC.
status=0
hydra -l dg_demo -P "$words" -s 2222 -t 1 -W 1 ssh://192.168.77.20 || status=$?
echo "Hydra exit status: $status. Verify six auth_failure events and R01 in the SOC."
exit "$status"
