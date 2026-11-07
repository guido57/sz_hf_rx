# Receiver operation

Run these commands on Xillinux with the software repository at `/root/sz_hf_rx`.
Program the required PL image using the hardware repository
[deployment guide](https://github.com/guido57/SmartZynq_SP2_HF_receiver/blob/master/docs/deployment.md).
The [PS–PL interface contract](https://github.com/guido57/SmartZynq_SP2_HF_receiver/blob/master/docs/ps_pl_interface.md)
defines the registers, endpoints and sample formats. Start with
[hardware validation](hardware_validation.md) for a newly programmed board.

## Select source, demodulator and tuning

```bash
cd /root/sz_hf_rx
python3 scripts/receiver_control.py
python3 scripts/receiver_control.py --source external --mode usb --tune 14074000
```

Readback without options preserves settings. Source is `simulated` or `external`
(AD9248 channel A); modes are `raw`, `iq`, `usb`, `lsb`. Tuning is in Hz.
Use USB for ordinary FT8 audio. Close active readers before reconfiguration.
Do not run multiple consumers on the same device endpoint.

## Internal simulator

Use the [three-step integration test](integration_tests.md): upload FT8 tones,
set mode/frequencies, run decoder. The uploader schedules commit at the next
UTC slot +0.5 seconds. The hardware repeats relative to commit; it has no UTC
clock. Set simulator frequency above tuning for positive USB audio. The
79-tone sequence has a base offset plus tones spaced 6.25 Hz apart.

## Final receiver: external FT8

After connecting a suitable RF input and programming the compatible PL image:

```bash
cd /root/sz_hf_rx
python3 scripts/receiver_control.py --source external --mode usb --tune 14074000
cd ft8_decoder
make stream
build/a9-stream/ft8-subtract-stream-a9 --slots 1 --base-mhz 14.074
```

No simulator upload is needed for external reception. Keep the board UTC clock
synchronized for real FT8 slots. `--base-mhz` labels results; it does not tune
the FPGA. Allow up to 15 seconds to reach the next boundary, another 15 seconds
to capture, then decoding time. This command captures one slot and exits;
use `--slots N` for N consecutive slots. It supports one receiver stream.
Off-air decode success depends on input signal, passband and clock accuracy;
the internal test alone does not establish weak-signal RF performance.

## Monitor and record

```bash
cd /root/sz_hf_rx
DISPLAY=:0 python3 scripts/adc_monitor.py --receiver --source external --mode iq --tune 14074000
# Close the monitor before recording.
python3 scripts/capture_ssb_audio.py /root/usb.wav \
  --source external --mode usb --tune 14074000 --seconds 15
```

The monitor needs NumPy/Matplotlib and an X display, or `--save PATH` for a
headless plot. Audio is mono PCM16 at 8 kHz. Raw/IQ mode does not provide audio
to `/dev/xillybus_read_8`. `capture_ssb_audio.py` checks for FIFO overflow before
closing the stream; discard overflowed recordings.

## Live JTAG reconfiguration

The [hardware JTAG guide](https://github.com/guido57/SmartZynq_SP2_HF_receiver/blob/master/docs/jtag-reconfiguration.md)
covers Vivado programming. Run `scripts/jtag_lifecycle.py prepare` and `finish`
from an interactive UART console, not SSH: Ethernet is interrupted. Use only
compatible full bitstreams. After restoration re-run hardware validation and
upload simulator tones again if needed.
