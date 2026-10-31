# Demo run (about 3 minutes)

Owner: M4. Rehearse from a fresh start at least 3 times after H20.

## Reset (Laptop B)

```bash
docker compose -f deployment/docker-compose.yml --env-file deployment/lab.env down
rm -rf deployment/state/cowrie-log/* deployment/state/web-log/* backend/data/*.db
echo '{"version":0,"entries":[]}' > deployment/state/blocklist.json
# bump LAB_RUN_ID in deployment/lab.env
docker compose -f deployment/docker-compose.yml --env-file deployment/lab.env up -d
# start backend, adapter, frontend
bash deployment/preflight.sh     # must say ALL PASS
```

## Run

| Step | Laptop A does | Dashboard shows | Score |
|---|---|---|---|
| 1 | hydra, 6 wrong passwords then right | R01 repeated SSH guessing, kill-chain: credential attack | 25 medium |
| 2 | ssh in, `whoami`, `ls -la` | R02 + R03, transcript replay fills in | 50 high |
| 3 | `cat notes.txt`, then web login with svc_portal | Strong-candidate dashed edge, "token tok_portal_01" | 50 |
| 4 | SQLi on /search | R07 web attack attempt (sqli), kill-chain: exploit attempt | 65 high |
| 5 | Analyst confirms the link with a reason | Edge turns solid, R05 + R09 count | 95 critical |
| 6 | Download customer_data.csv | R04 synthetic file served, kill-chain: data access | 100 critical |
| 7 | Analyst previews and applies a block, reason "demo containment" | Action applied | 100 |
| 8 | Any request from A | 403, `blocked_request` arrives, action shows verified | unchanged |
| 9 | Undo | Next request gets 200 again | unchanged |

Script for A: `STEP_DELAY=6 bash scenarios/attack_p3.sh 192.168.77.20`

## What to say about limits

- Commands were submitted to an emulated shell. Nothing ran on a real host.
- The file was synthetic. No real data exists in the lab.
- The confirmed link means the same source followed our planted trail. It does not identify a person.
- The block covers the web decoy only.

## Backup

Record a screen capture of a clean run by H22 in case anything fails live.
