# Ready-to-run Xillinux SD image

The current image is **v3, 2026-11-08**, for the HelloFPGA SmartZynq SP2
V1.3B (XC7Z020). The owner confirmed a successful physical boot with the
requested desktop, SSH and VNC behavior on 2026-11-08.

[Download the v3 image and SHA-256 checksum](https://github.com/guido57/SmartZynq_SP2_HF_receiver/releases/tag/sd-image-v3-2026-11-08).
The compressed image is about 1.3 GB. It includes the tested PL boot files,
Xillinux, software sources and a prebuilt Cortex-A9 decoder; the default
internal FT8 demo needs no compiler, package download or antenna.

## Flash and boot

1. Download `smartzynq-hf-rx-xillinux-2026-11-08-v3.img.gz` and its
   `.img.gz.sha256` file into the same directory.
2. Verify the download:

```bash
sha256sum -c smartzynq-hf-rx-xillinux-2026-11-08-v3.img.gz.sha256
```

3. Write the complete compressed image with your disk-image writer to a
   spare SD card, 8 GB or larger. Flashing erases that card. Writers that do
   not accept gzip require you to decompress it first.
4. Boot the SmartZynq from the card. HDMI/LXDE starts automatically, and SSH
   and password-protected VNC are enabled. Wait for first-boot preparation
   to finish; bundled VNC packages install offline.

## Login and remote desktop

| Access | Setting |
| --- | --- |
| SSH username | `root` |
| SSH/root password | `root` |
| VNC password | `root` |
| VNC TCP port | `5900` |

Find the DHCP address on the board with `hostname -I`, or in your router.
From another computer:

```bash
ssh root@BOARD_IP
```

Connect a VNC viewer to `BOARD_IP:5900` (display `:0`) and enter `root`.
VNC shares the same LXDE session as HDMI. You do not need to run `startx`
manually. The VNC and root passwords are separate even though both defaults
are `root`. The v3 image also retains the maintainer public SSH keys used
while testing; no private SSH keys are included.

To change your card's credentials later:

```bash
passwd
x11vnc -storepasswd /root/.vnc/passwd
chmod 600 /root/.vnc/passwd
systemctl restart sz-hf-rx-vnc
```

Classic VNC uses at most eight password characters. The initial-password
text file is a record of the initial value and is not updated by a manual
password change. If you want only your own SSH keys, replace
`/root/.ssh/authorized_keys` with your own public keys.

## Run the live receiver demo

Open **SmartZynq FT8 Demo** on the desktop, or run in a board terminal/SSH:

```bash
sz-hf-rx
```

The launcher selects the internal source and USB mode, tunes to 14.074 MHz,
sets the simulated carrier to 14.0755 MHz, uploads the default FT8 sequence
at the next UTC slot +0.5 seconds, and captures/decodes one slot. Allow up
to 15.5 seconds for upload alignment, then up to 30 seconds for slot wait
and capture, followed by decoding. Expected message:

```text
... dt=+0.50s freq=1500.0Hz text=G0XYZ K1ABC FN43
```

Only desktop and remote-access services start at boot; the FT8 demo starts
when requested. Close competing Xillybus readers first. Ctrl+C stops capture.
For external reception with the ADC board and suitable RF input:

```bash
sz-hf-rx --source external --tune 14074000 --slots 2
```

This enables USB audio without uploading simulator tones. Synchronize the
board UTC clock for off-air FT8. See [receiver operation](receiver.md),
[hardware validation](hardware_validation.md) and [integration tests](integration_tests.md).

## Existing card and troubleshooting

With this repository at `/root/sz_hf_rx`, install the launcher on Xillinux:

```bash
cd /root/sz_hf_rx
python3 scripts/install_sd.py
```

To enable remote/desktop startup using the included offline packages:

```bash
python3 scripts/install_remote_access.py --ssh-public-key /path/to/your-key.pub --vnc-access lan --start
```

This preserves existing credentials. On a fresh installation without preset
VNC credentials, first boot generates a password in
`/root/.vnc/initial-password.txt`. **The released v3 image instead presets
both passwords to `root`.** Details are in [remote access](remote_access.md).

```bash
systemctl status ssh sz-hf-rx-firstboot sz-hf-rx-desktop sz-hf-rx-vnc --no-pager
journalctl -b -u sz-hf-rx-firstboot -u sz-hf-rx-desktop -u sz-hf-rx-vnc
```

Do not run another `startx` while the desktop service is active. Before live
JTAG programming, stop desktop and VNC from UART as described in the remote
access guide, then restart them after the JTAG lifecycle completes.

## Contents and validation

Software and documentation are under `/root/sz_hf_rx`; the ARM executable is
under `ft8_decoder/build/a9-stream/`. The image is a source snapshot without
`.git`, so it does not support `git pull` in place. For a development checkout,
clone this repository separately. `/root/START-HERE.txt` documents the initial
login. Internal and external manifests identify the base, boot files, source
snapshot and executable hashes. The source documentation on GitHub is updated
after testing; the released image checksum continues to identify the exact
boot-tested artifact.

Recorded checks include filesystem integrity, source/boot checksums, password
hash and VNC file verification, ARM runtime/reference decoding, software tests,
and the owner's physical boot confirmation for v3. The internal signal-path
test and 27-message reference WAV test were validated earlier; the v3 boot
report does not claim a new weak-signal off-air performance measurement.

The image starts from the clean vendor base and copies only the four tested
boot files and the receiver software. It does not copy a running personal
root filesystem, browser profiles, shell history or private SSH keys. Build
and password-customization tools live with the
[PL image-composition guide](https://github.com/guido57/SmartZynq_SP2_HF_receiver/blob/master/docs/sd-image.md).
