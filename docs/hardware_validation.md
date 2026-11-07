# Preliminary PL–PS validation

These tests establish transport and signal formats before running the complete
FT8 decoder. They use the current single-channel `hf_ssb_receiver` image,
not the older counter/virtual-ADC test images.

## Prerequisites and provenance

Build/program the image using the PL repository [deployment guide](https://github.com/guido57/SmartZynq_SP2_HF_receiver/blob/master/docs/deployment.md).
Check its [PS–PL interface contract](https://github.com/guido57/SmartZynq_SP2_HF_receiver/blob/master/docs/ps_pl_interface.md).
Install this repository at `/root/sz_hf_rx`; Python 3, NumPy and Matplotlib are
needed for plots. Close other device readers. Run commands below on Xillinux.
Use an ordinary working SD boot, or complete JTAG lifecycle restoration first.

For each test run, record both Git revisions and dirty status, board version,
programmed bitstream path/hash and commands/results. On each repository use
`git rev-parse HEAD` and `git status --short`; hash the exact programmed `.bit`
on the programming PC with `sha256sum IMAGE.bit`. Do not infer the loaded
image from the current contents of a build directory.

```bash
cd /root/sz_hf_rx
mkdir -p results
ls -l /dev/xillybus_mem_8 /dev/xillybus_read_32 /dev/xillybus_read_8
python3 scripts/receiver_control.py --timeout 3
```

Expected: all three endpoints exist and control readback succeeds. A protocol
marker error indicates an incompatible image; device names alone do not prove
compatibility. Also verify SSH and the HDMI desktop when those are required.

## 1. Raw ADC snapshot

```bash
python3 scripts/ft8_control.py
python3 scripts/adc_monitor.py --receiver --source simulated --mode raw \
  --sim-frequency 1001000 --save results/adc-raw.png
```

Expected: `Frame 1`, 4096 indexed signed 14-bit samples at 64 MS/s, no timeout
or format errors, and a saved PNG. The dominant raw FFT bin is near 1 MHz
(15.625 kHz bin spacing). The FT8 source changes tones and contains a silent
interval; repeat a snapshot if it reports `No signal`.

## 2. Tuned IQ snapshot

```bash
python3 scripts/adc_monitor.py --receiver --source simulated --mode iq \
  --tune 1000000 --sim-frequency 1001000 --save results/adc-iq.png
```

Expected: 4096 I/Q pairs at 8 ksample/s, a spectrum near +1 kHz with FT8 tone
offsets, no invalid signed-24-bit or capture errors, and the saved plot.
For a live HDMI monitor, omit `--save` and use `DISPLAY=:0` after starting X.
Close the monitor before the next test.

## 3. Continuous USB audio

```bash
python3 scripts/capture_ssb_audio.py results/simulated-usb.wav \
  --source simulated --mode usb --tune 1000000 \
  --sim-frequency 1001000 --seconds 5
python3 - <<'CHECKWAV'
import wave
with wave.open('results/simulated-usb.wav', 'rb') as w:
    actual = (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes())
    assert actual == (1, 2, 8000, 40000), actual
    print('PASS: mono PCM16, 8000 Hz, 40000 frames')
CHECKWAV
```

Expected: capture reports 40000 continuous samples without overflow, and the
WAV check passes. This proves transport/format, not a valid FT8 decode. A hung
reader in raw/IQ mode is not an audio test: select USB/LSB first. Overflow means
samples were lost; reduce competing work and repeat with a single reader.

After these checks, run the [complete FT8 test](integration_tests.md). These
procedures change receiver settings; use [receiver operation](receiver.md) to
restore the intended source and tuning. Counter and old repeating-tone ADC
checks are not prerequisites for this receiver; their utilities were retired.
