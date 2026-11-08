#!/usr/bin/env python3
"""Prepare offline VNC packages and a per-card VNC password (Python 3.5+)."""
import json
import os
from pathlib import Path
import random
import string
import subprocess


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Run as root')
    root = Path(__file__).resolve().parents[1]
    if not Path('/usr/bin/x11vnc').exists():
        records = json.loads((root / 'packages/packages.json').read_text())
        import hashlib
        packages = []
        for record in records:
            path = root / 'packages' / record['Filename'].split('/')[-1]
            if hashlib.sha256(path.read_bytes()).hexdigest() != record['SHA256']:
                raise RuntimeError('Package checksum mismatch: ' + path.name)
            packages.append(str(path))
        subprocess.run(['dpkg', '-i'] + packages, check=True)
    directory = Path('/root/.vnc')
    directory.mkdir(mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    password_file = directory / 'initial-password.txt'
    auth_file = directory / 'passwd'
    if not auth_file.exists():
        if password_file.exists():
            password = password_file.read_text().strip()
        else:
            rng = random.SystemRandom()
            password = ''.join(rng.choice(string.ascii_letters + string.digits) for _ in range(8))
            fd = os.open(str(password_file), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as out:
                out.write(password + '\n')
        try:
            subprocess.run(['/usr/bin/x11vnc', '-storepasswd', password, str(auth_file)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except subprocess.CalledProcessError:
            # Do not let CalledProcessError put the password-bearing argv in the journal.
            raise RuntimeError('Failed to initialize VNC authentication') from None
        auth_file.chmod(0o600)
    subprocess.run(['ssh-keygen', '-A'], check=True)
    print('Remote access prepared. Read the VNC password with: cat /root/.vnc/initial-password.txt')


if __name__ == '__main__':
    main()
