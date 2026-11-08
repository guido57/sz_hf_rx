#!/usr/bin/env python3
"""Build and install the live-capture launcher on the running Xillinux SD card."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Run as root on the Xillinux board')
    if not os.uname().machine.startswith('armv7'):
        raise RuntimeError('Install on the 32-bit ARM Xillinux board')
    root = Path(__file__).resolve().parents[1]
    subprocess.run(['make', 'stream'], cwd=str(root / 'ft8_decoder'), check=True)
    launcher = Path('/usr/local/bin/sz-hf-rx')
    target = root / 'scripts/live_capture.py'
    target.chmod(target.stat().st_mode | 0o111)
    launcher.parent.mkdir(parents=True, exist_ok=True)
    if launcher.is_symlink():
        if launcher.resolve() != target:
            raise RuntimeError('Existing launcher points elsewhere: ' + str(launcher))
    elif launcher.exists():
        raise RuntimeError('Refusing to replace existing file: ' + str(launcher))
    else:
        launcher.symlink_to(target)
    desktop = '''[Desktop Entry]
Type=Application
Name=SmartZynq FT8 Demo
Comment=Run one internal FT8 capture and decode
Exec=/bin/bash -c "sz-hf-rx; read -r -p 'Press Enter to close...' answer"
Terminal=true
Icon=utilities-terminal
Categories=HamRadio;Education;
'''
    for path in (Path('/usr/share/applications/sz-hf-rx.desktop'),
                 Path('/root/Desktop/sz-hf-rx.desktop')):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and 'Name=SmartZynq FT8 Demo' not in path.read_text():
            raise RuntimeError('Refusing to replace ' + str(path))
        path.write_text(desktop)
        path.chmod(0o755)
    print('Installed. Run sz-hf-rx or open SmartZynq FT8 Demo on the desktop.')
    print('The compatible PL bitstream must already be installed on the SD boot partition.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit('Installation failed: %s' % error)
