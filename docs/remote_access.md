Image login defaults
====================
SSH user: root
SSH password: root
VNC password: root

The image boots LXDE/startx and VNC automatically.

# SSH, desktop and VNC startup

The boot-tested v3 SD image uses SSH user/password **root/root** and VNC
password **root**. See [current image instructions](sd_image.md). Generic
installations without preset credentials generate a VNC password as described
below; that generation does not replace v3’s preset password.

Receiver images enable three systemd services at boot:

- `sz-hf-rx-firstboot`: installs the bundled, checksum-verified Ubuntu Xenial
  VNC packages without needing a network connection, and creates a per-card
  VNC password on first boot.
- `sz-hf-rx-desktop`: runs `startx` and LXDE on HDMI display `:0`, tty7.
- `sz-hf-rx-vnc`: shares that same desktop on TCP 5900 with VNC authentication.

SSH is enabled separately through the standard `ssh.service`. An image is not
a copy of your old root directory: previous authorized SSH keys must be supplied
explicitly to the image builder with `--ssh-public-key`. Password login follows
the base Xillinux account configuration; no universal password is added.

## Connect

Find the board's DHCP address on its console with `hostname -I`, then:

```bash
ssh root@BOARD_IP
cat /root/.vnc/initial-password.txt
```

The second command prints the generated VNC password. Enter it in your VNC
client when connecting to `BOARD_IP:5900` (display `:0`). The password is
stored in a root-only file and is not printed to system logs. Eight characters
are used because classic VNC authentication only uses the first eight.
LAN VNC authentication does not encrypt desktop traffic; for an encrypted
connection, build/install with `--vnc-access tunnel` and connect through SSH:

```bash
ssh -N -L 5900:127.0.0.1:5900 root@BOARD_IP
```

Then point the VNC client to `127.0.0.1:5900`, using the same VNC password.
The receiver demo itself does not run automatically; launch **SmartZynq FT8
Demo** on the desktop, or run `sz-hf-rx` through SSH.

## Diagnose or restart

```bash
systemctl status ssh sz-hf-rx-firstboot sz-hf-rx-desktop sz-hf-rx-vnc
journalctl -b -u sz-hf-rx-firstboot -u sz-hf-rx-desktop -u sz-hf-rx-vnc
systemctl restart sz-hf-rx-desktop sz-hf-rx-vnc
```

The VNC service retries if X is not ready yet. Do not run a second `startx`
when the desktop service is active. Before live FPGA JTAG programming, stop
these services from UART so the lifecycle helper sees no active X session:

```bash
systemctl stop sz-hf-rx-vnc sz-hf-rx-desktop
```

Run the documented JTAG prepare/program/finish procedure, then restart both
services. Reboot is not required just to restart the desktop.

## Repair an existing card

The startup repair archive contains the new scripts, service units, verified
VNC packages and the requested public SSH keys. It contains no private key or
preset VNC password. Transfer it using a USB drive, or download it from the
build PC from the board's local console, then extract and run `apply.sh` as
root. It preserves existing authorized keys and starts services immediately.
No SD-card reflash is required.

VNC packages come from the [Ubuntu archive](https://old-releases.ubuntu.com/ubuntu/pool/universe/x/x11vnc/).
`packages/packages.json` records exact versions and hashes checked against the
original Xillinux image's package index. Runtime loading was checked using
the base image libraries under ARM emulation; a hardware boot confirms the
actual display session and network listeners.
