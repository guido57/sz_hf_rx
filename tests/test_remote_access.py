from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from install_remote_access import install


class RemoteTests(unittest.TestCase):
    def test_keys_units_permissions_and_repeat_install(self):
        software = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = root / 'test.pub'
            key.write_text('ssh-ed25519 AAAATEST test-key\n')
            install(root, software, [key], 'lan')
            install(root, software, [key], 'lan')
            auth = root / 'root/.ssh/authorized_keys'
            self.assertEqual(auth.read_text().splitlines(), ['ssh-ed25519 AAAATEST test-key'])
            self.assertEqual(auth.stat().st_mode & 0o777, 0o600)
            self.assertEqual(auth.parent.stat().st_mode & 0o777, 0o700)
            systemd = root / 'etc/systemd/system'
            for name in ('sz-hf-rx-firstboot', 'sz-hf-rx-desktop', 'sz-hf-rx-vnc'):
                self.assertTrue((systemd / 'multi-user.target.wants' / (name+'.service')).is_symlink())
            self.assertIn('-listen 0.0.0.0', (systemd / 'sz-hf-rx-vnc.service').read_text())
            self.assertIn('-rfbauth', (systemd / 'sz-hf-rx-vnc.service').read_text())

    def test_tunnel_is_loopback_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install(root, Path(__file__).resolve().parents[1], [], 'tunnel')
            unit = (root / 'etc/systemd/system/sz-hf-rx-vnc.service').read_text()
            self.assertIn('-localhost', unit)
            self.assertNotIn('-listen 0.0.0.0', unit)

    def test_private_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = root/'private'
            key.write_text('-----BEGIN OPENSSH PRIVATE KEY-----\n')
            with self.assertRaises(ValueError):
                install(root, Path(__file__).resolve().parents[1], [key], 'lan')
            self.assertFalse((root/'root/.ssh/authorized_keys').exists())

if __name__ == '__main__':
    unittest.main()
