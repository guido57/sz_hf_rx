# SmartZynq HF receiver

This repository contains receiver control and diagnostic scripts in `scripts/`
and an FT8 residual-subtraction decoder in `ft8_decoder/` for the SmartZynq
Xillinux target. The decoder is derived from the `subtract-test` branch of
[`guido57/ESP32_ft8_lib`](https://github.com/guido57/ESP32_ft8_lib). It decodes
FT8 and FT4 WAV recordings and provides a live FT8 capture program for the
receiver's 8 kHz PCM stream.

The decoder performs three passes by default: it decodes the original
waterfall, synthesizes and subtracts every successful FT8 signal, then rebuilds
the waterfall to recover signals that were masked by stronger transmissions.

## Xillinux quick start

The examples assume the repository is checked out at `/root/sz_hf_rx` on
the Xillinux board. Adjust that prefix if your checkout is elsewhere. Build
and decoder commands run from the `ft8_decoder/` subdirectory.

```bash
cd /root/sz_hf_rx/ft8_decoder
make a9
./ft8_decoder tests/20m_busy/test_01.wav -1
```

`make a9` builds a hard-float, NEON-optimized Cortex-A9 executable. `-1`
selects automatic cancellation for every decoded candidate. A successful
decode currently makes the program return status `1`, because the application
uses its positive decoded-message count as the return value; use its printed
result rather than the shell status when testing.

On this Xillinux board, the 12 kHz reference recording above decodes 27
messages in about 3.1 seconds: 20 on the first pass and seven after residual
subtraction.

## Test at the receiver's 8 kHz rate

The receiver supplies mono signed PCM at 8 kHz. Create an equivalent WAV once:

```bash
apt-get update
apt-get install -y sox
cd /root/sz_hf_rx/ft8_decoder
sox tests/20m_busy/test_01.wav -r 8000 -c 1 -b 16 test_01_8k.wav
soxi test_01_8k.wav
./ft8_decoder test_01_8k.wav -1
```

`soxi` must report an 8000 Hz, one-channel, 16-bit PCM WAV. On the Cortex-A9,
this resampled recording decodes all 27 messages in about 2.45 seconds. The Cortex-A9 build raises FT8_MAX_CANDIDATES to 80, avoiding an 8 kHz search-list cap that previously excluded the two signals near 2.05 kHz.

## Live SmartZynq receiver capture

Build the capture program:

```bash
cd /root/sz_hf_rx/ft8_decoder
make stream
```

Run one UTC-aligned 15-second slot:

```bash
build/a9-stream/ft8-subtract-stream-a9 --slots 1 --base-mhz 14.074
```

The program opens `/dev/xillybus_read_8`, waits for the next FT8 UTC boundary,
captures exactly 120,000 PCM16 samples, and decodes the completed slot while
the next one is captured. The FPGA must be configured to send an 8 kHz FT8
audio passband to that device. `--base-mhz` controls the RF frequency printed
with each decode.

The runner uses a two-slot buffer and enables automatic subtraction with three
passes. It currently implements one stream. A four-receiver system must
deinterleave the four channels and create one runner/decoder instance per
channel.

## Build commands

Run these commands from `ft8_decoder/`, which contains the Makefile.

| Command | Result |
| --- | --- |
| `make` | Native host `ft8_decoder` build using the local compiler defaults. |
| `make a9` | Clean and build `ft8_decoder` for Cortex-A9 with NEON and hard-float. |
| `make stream` | Build `build/a9-stream/ft8-subtract-stream-a9`. |
| `make clean` | Remove the native decoder build and executable. |
| `make stream-clean` | Remove the live-stream build. |

## Python receiver tools

Run these scripts with `python3` on Xillinux. Hardware tools require the
matching FPGA bitstream and Xillybus endpoints. Keep `receiver_control.py`
beside the scripts that import it. The board currently has Python 3.5,
NumPy 1.11, Matplotlib 1.5 and Tkinter.

| Script in `scripts/` | Purpose and requirements | Recommendation |
| --- | --- | --- |
| `receiver_control.py` | Read/set DDC source, mode, tuning and simulator frequency through `/dev/xillybus_mem_8`. USB/LSB needs the SSB bitstream. Shared helper imported by the monitor, audio recorder and FT8 uploader. | Keep. |
| `adc_monitor.py` | Plot raw ADC, IQ or audio snapshots, or CSV input. Requires NumPy and Matplotlib, plus Tkinter for interactive frequency dialogs. `--save` produces headless output. Imports `receiver_control.py`. | Keep for signal inspection. |
| `capture_ssb_audio.py` | Record continuous 8 kHz mono PCM16 from `/dev/xillybus_read_8` to WAV; configure USB/LSB and check overflow. Requires the SSB bitstream and `receiver_control.py`. | Keep for recordings and decoder tests. |
| `ft8_control.py` | Upload 79 FT8 tones to the FPGA simulator through the control window. Requires the FT8-upload-capable bitstream and `receiver_control.py`. This does not decode FT8. | Optional; keep for simulator tests. |
| `jtag_lifecycle.py` | Inspect drivers, detach before live JTAG programming, then rebind and rearm HDMI. Uses root privileges and board-specific registers. Run prepare/finish from an interactive UART console, not SSH; Ethernet is interrupted. | Keep for live JTAG programming. |

Examples (the monitor and recording commands change receiver settings):

```bash
cd /root/sz_hf_rx
# Read current receiver settings.
python3 scripts/receiver_control.py
# Save a simulated raw ADC snapshot without a GUI.
python3 scripts/adc_monitor.py --receiver --source simulated --mode raw --save /root/adc-raw.png
# Record five seconds of USB audio from the external ADC.
python3 scripts/capture_ssb_audio.py /root/usb.wav --source external --mode usb --tune 1000000 --seconds 5
# Status is read-only; prepare/finish require an interactive UART console.
python3 scripts/jtag_lifecycle.py status
```

For normal receiver inspection and recording, the core Python tools are
`receiver_control.py`, `adc_monitor.py` and `capture_ssb_audio.py`.
The live FT8 capture executable runs independently of these Python scripts
once the FPGA receiver has been configured. `ft8_control.py` supports FPGA
simulator tests, and `jtag_lifecycle.py` supports live JTAG programming.

## Layout

Paths below are relative to the repository root:

```text
README.md                         Project documentation
scripts/                          Receiver control, capture and diagnostics
  receiver_control.py             DDC/SSB controls and shared Python helpers
  adc_monitor.py                  ADC/IQ/audio snapshot plots
  capture_ssb_audio.py            Continuous PCM16 WAV recording
  ft8_control.py                  FPGA simulator FT8 tone upload
  jtag_lifecycle.py               Current live-JTAG driver and HDMI lifecycle
ft8_decoder/
  Makefile                        Native and Cortex-A9 build targets
  LICENSE                         Decoder license
  src/ft8/                        FT8 protocol, LDPC, packing and message code
  src/fft/                        KissFFT implementation
  src/decode_ft8.cpp              Waterfall search, decode passes and subtraction
  src/subtract.cpp                FT8 waveform synthesis and residual cancellation
  src/decoder_api.cpp             Slot and streaming decoder API
  src/main.cpp                    Native WAV-file command-line application
  src/ft8_subtract_stream.cpp      SmartZynq live PCM capture application
  tests/                          Reference WAV recordings
  build/                          Generated build output
```

## ESP32 and PlatformIO

The decoder originates from an ESP32/PlatformIO project. This repository does
not currently include a `platformio.ini`; the build instructions above use
`ft8_decoder/Makefile`.

## Credits

The decoder originates from Karlis Goba (YL3JG)'s `ft8_lib`; this version adds
the FT8 residual-subtraction pipeline. KissFFT is by Mark Borgerding. FT8 is
part of the WSJT-X protocol ecosystem.
