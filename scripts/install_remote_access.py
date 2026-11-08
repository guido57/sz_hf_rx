#!/usr/bin/env python3
"""Install SSH, automatic X/LXDE and authenticated VNC startup services."""
import argparse
import os
from pathlib import Path
import subprocess


def install(root, software, key_paths, access):
    # root is / on a board, or a staging directory when composing an image.
    ssh = root / 'root/.ssh'
    ssh.mkdir(parents=True, mode=0o700, exist_ok=True)
    ssh.chmod(0o700)
    authorized = ssh / 'authorized_keys'
    lines = authorized.read_text().splitlines() if authorized.exists() else []
    for path in key_paths:
        for line in path.read_text().splitlines():
            if line.strip() and line not in lines:
                if not line.startswith(('ssh-ed25519 ', 'ssh-rsa ', 'ecdsa-sha2-')):
                    raise ValueError('Expected an SSH public key, not a private key: ' + str(path))
                lines.append(line)
    if lines:
        authorized.write_text('\n'.join(lines) + '\n')
        authorized.chmod(0o600)
    systemd = root / 'etc/systemd/system'
    systemd.mkdir(parents=True, exist_ok=True)
    for name in ('sz-hf-rx-firstboot.service', 'sz-hf-rx-desktop.service', 'sz-hf-rx-vnc.service'):
        content = (software / 'systemd' / name).read_text()
        if access == 'tunnel' and name == 'sz-hf-rx-vnc.service':
            content = content.replace('-listen 0.0.0.0', '-localhost')
        (systemd / name).write_text(content)
        wants = systemd / 'multi-user.target.wants'
        wants.mkdir(exist_ok=True)
        link = wants / name
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to('../' + name)
    wants = systemd / 'multi-user.target.wants'
    link = wants / 'ssh.service'
    if not link.exists() and not link.is_symlink():
        link.symlink_to('/lib/systemd/system/ssh.service')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/'), help='offline root directory or /')
    parser.add_argument('--ssh-public-key', type=Path, action='append', default=[])
    parser.add_argument('--vnc-access', choices=('lan', 'tunnel'), default='lan')
    parser.add_argument('--start', action='store_true', help='start services on the running board now')
    args = parser.parse_args()
    software = Path(__file__).resolve().parents[1]
    if args.root == Path('/') and os.geteuid() != 0:
        parser.error('Run as root on Xillinux, or specify an offline --root')
    install(args.root, software, args.ssh_public_key, args.vnc_access)
    if args.start:
        if args.root != Path('/'):
            parser.error('--start requires the running system')
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', 'start', 'ssh.service', 'sz-hf-rx-desktop.service',
                        'sz-hf-rx-vnc.service'], check=True)
    print('SSH, desktop and VNC services enabled. Read VNC password after first boot:')
    print('cat /root/.vnc/initial-password.txt')


if __name__ == '__main__':
    main()
