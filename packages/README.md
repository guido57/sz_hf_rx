# Offline VNC packages

These four Ubuntu Xenial ARM/all packages support first-boot VNC installation
without network access. `packages.json` contains exact versions, archive
paths and SHA-256 values from the original Xillinux image package index.
`firstboot.py` verifies every archive before invoking dpkg.

Archives were downloaded from https://old-releases.ubuntu.com/ubuntu/ .
The corresponding source packages are x11vnc and libvncserver in that archive.
Each .deb contains its upstream copyright and licensing information.
No password or SSH key is stored in this directory.
