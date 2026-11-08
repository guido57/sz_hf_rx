import sys
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import live_capture
import receiver_control
import ft8_control


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch.object(Path, 'is_file', return_value=True),
            patch.object(live_capture.os, 'access', return_value=True),
            patch.object(live_capture.os.path, 'exists', return_value=True),
            patch.object(live_capture.os, 'geteuid', return_value=0),
            patch.object(receiver_control, '_read_bytes', return_value=bytes([0, 0, 0, 0xd3])),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_demo_configures_then_uploads_then_captures(self):
        events = []
        with patch.object(receiver_control, 'ReceiverController', side_effect=lambda *a: events.append(('config', a))), \
             patch.object(ft8_control, 'upload', side_effect=lambda *a: events.append(('upload', a))), \
             patch.object(live_capture.subprocess, 'run', side_effect=lambda *a, **k: events.append(('capture', a, k))):
            self.assertEqual(live_capture.main([]), 0)
        self.assertEqual([item[0] for item in events], ['config', 'upload', 'capture'])
        self.assertEqual(events[0][1][2:], ('simulated', 'usb', 14074000.0, 14075500.0))
        self.assertEqual(events[2][1][0][-2:], ['--base-mhz', '14.074000000'])
        self.assertEqual(events[2][2]['timeout'], 50)

    def test_external_does_not_upload_simulator_tones(self):
        with patch.object(receiver_control, 'ReceiverController') as configure, \
             patch.object(ft8_control, 'upload') as upload, \
             patch.object(live_capture.subprocess, 'run') as capture:
            live_capture.main(['--source', 'external', '--tune', '7074000', '--slots', '2'])
        self.assertEqual(configure.call_args[0][2:], ('external', 'usb', 7074000.0, None))
        upload.assert_not_called()
        self.assertEqual(capture.call_args[1]['timeout'], 70)

    def test_wrong_image_does_not_change_configuration(self):
        with patch.object(receiver_control, '_read_bytes', return_value=bytes([0, 0, 0, 0xd2])), \
             patch.object(receiver_control, 'ReceiverController') as configure, \
             patch.object(ft8_control, 'upload') as upload:
            with self.assertRaises(SystemExit) as error:
                live_capture.main([])
        self.assertEqual(error.exception.code, 1)
        configure.assert_not_called()
        upload.assert_not_called()

    def test_stalled_capture_has_a_bounded_error(self):
        with patch.object(receiver_control, 'ReceiverController'), \
             patch.object(ft8_control, 'upload'), \
             patch.object(live_capture.subprocess, 'run', side_effect=subprocess.TimeoutExpired('decoder', 50)):
            with self.assertRaises(SystemExit) as error:
                live_capture.main([])
        self.assertEqual(error.exception.code, 1)


if __name__ == '__main__':
    unittest.main()
