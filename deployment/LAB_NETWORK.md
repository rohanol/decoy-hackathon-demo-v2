# Lab network setup (M2)

Do this before the event and again at H0. Takes about 20 minutes.

## Hardware

- One ethernet cable. USB-ethernet adapters if either laptop lacks a port.
- Extension board. Phone hotspot for package installs only, never during runs.

## Laptop B (defender, 192.168.77.20)

Find the wired interface name with `ip link` (e.g. `eth0`, `enp3s0`, `enx...`).

```bash
IF=enp3s0                       # change
sudo nmcli dev set $IF managed no  # stop NetworkManager fighting you (or configure via nmcli instead)
sudo ip addr flush dev $IF
sudo ip addr add 192.168.77.20/24 dev $IF
sudo ip link set $IF up
```

During runs: Wi-Fi off and no default route.

```bash
nmcli radio wifi off
ip route | grep default && sudo ip route del default   # should print nothing afterwards
```

### If Laptop B is Windows + WSL2 or a VM

This is the riskiest part of the whole build. Test it today:

1. Start the decoys, then from Laptop A run `nc -vz 192.168.77.20 2222` and `curl -s http://192.168.77.20:8080/`.
2. Log in over SSH from A and check `deployment/state/cowrie-log/cowrie.json`: `src_ip` must be `192.168.77.10`, not a NAT address like `172.x` or `10.0.2.2`.

If either fails: VM → bridged adapter on the wired NIC. WSL2 → mirrored networking mode, or run everything on a Linux live USB or a Linux teammate's laptop. Do not spend more than 1 hour fighting this at the venue.

## Laptop A (Kali, 192.168.77.10)

```bash
IF=eth0
sudo ip addr flush dev $IF
sudo ip addr add 192.168.77.10/24 dev $IF
sudo ip link set $IF up
ping -c 2 192.168.77.20
```

## Preflight

On Laptop B, before every demo run: `bash deployment/preflight.sh`. All lines must say PASS.
