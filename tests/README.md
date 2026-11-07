# Xillinux software tests

These tests live with the Python utilities they exercise. The decoder WAV
fixtures remain separately under `ft8_decoder/tests/`.

Run from the repository root on Linux with Python 3, NumPy and Matplotlib:

```bash
MPLBACKEND=Agg python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The automated tests mock receiver/JTAG device operations and do not program
the FPGA. They cover receiver controls, snapshot formats, audio recording,
GUI state changes, worker responsiveness and HDMI lifecycle safeguards.
Multiprocessing tests use Linux fork and need a working shared-memory setup.
Python 3.5 on Xillinux is supported; newer Python checks 3.5 syntax explicitly.

`check_monitor_tk.py` is a separate interactive Tk regression check. It opens
a window with simulated capture and needs Tkinter, a working X display and
NumPy/Matplotlib. Run from a terminal in the board desktop session:

```bash
DISPLAY=:0 python3 tests/check_monitor_tk.py
```

This GUI check is not included in automated unittest discovery. It verifies
that controls respond while capture is running and changes apply to the next
frame. For tests on real hardware use
[hardware validation](../docs/hardware_validation.md) and
[integration tests](../docs/integration_tests.md).

Bitstream deployment tests remain in the PL repository, beside its deployment
utilities. The retired FT8MON wrapper test is archived in that repository and
is not part of this active suite.
