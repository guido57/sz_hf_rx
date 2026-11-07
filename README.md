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

## Documentation and repository boundary

This repository owns Xillinux software, receiver utilities, decoder builds,
board-validation procedures, integration tests and final receiver operation.
The [PL repository](https://github.com/guido57/SmartZynq_SP2_HF_receiver) owns
RTL, Vivado projects, constraints, bitstream preparation and programming.

- [Preliminary PL–PS hardware validation](docs/hardware_validation.md)
- [Complete internal FT8 integration test](docs/integration_tests.md)
- [Receiver operation and external FT8 reception](docs/receiver.md)
- [PS–PL interface contract](https://github.com/guido57/SmartZynq_SP2_HF_receiver/blob/master/docs/ps_pl_interface.md)
- [PL build and deployment](https://github.com/guido57/SmartZynq_SP2_HF_receiver/blob/master/docs/deployment.md)

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
decode currently makes the program return status `1`, use its printed decoded count rather than treating status 1 as an automatic
failure when testing.

On this Xillinux board, the 12 kHz reference recording above decodes 27
messages in about 3.1 seconds: 20 on the first pass and seven after residual
subtraction.

You'll see something like this:

```
./ft8_decoder tests/20m_busy/test_01.wav -1
[INF] [ft8] monitor sample_rate=12000 samples=180000 time_osr=2 freq_osr=2
[INF] [ft8] monitor block=1920 (160.000ms) subblock=960 (80.000ms) fft=3840 (320.000ms)
[INF] [ft8] stage=full pass=0 waterfall blocks=93 elapsed=149.9ms max=-19.1dB
[INF] [ft8] stage=full pass=0 candidates=146 threshold=10 search=21.2ms
[INF] [ft8] stage=full pass=0 candidates=146 new=20 total=20 decode=1597.8ms
[INF] [ft8] stage=full pass=1 waterfall blocks=93 elapsed=148.8ms max=-19.1dB
[INF] [ft8] stage=full pass=1 candidates=100 threshold=10 search=21.3ms
[INF] [ft8] stage=full pass=1 candidates=100 new=7 total=27 decode=889.8ms
[INF] [ft8] stage=full pass=2 waterfall blocks=93 elapsed=148.9ms max=-19.1dB
[INF] [ft8] stage=full pass=2 candidates=73 threshold=10 search=21.2ms
[INF] [ft8] stage=full pass=2 candidates=73 new=0 total=27 decode=458.7ms
[INF] [ft8] results stage=full slot=20:07:00.000 decoded=27
[INF] [ft8] 200701 snr=-9 dt=+1.30s freq=337.5Hz text=JO1COV PE1OYB JO21
[INF] [ft8] 200702 snr=-7 dt=+1.38s freq=559.4Hz text=OE3MLC G3ZQQ 73
[INF] [ft8] 200702 snr=+16 dt=+1.38s freq=709.4Hz text=CQ IK4LZH JN54
[INF] [ft8] 200703 snr=-10 dt=+2.42s freq=718.8Hz text=<...> SQ9JJR JO90
[INF] [ft8] 200702 snr=-6 dt=+1.46s freq=771.9Hz text=JA1FWS HA7CH JN97
[INF] [ft8] 200703 snr=+5 dt=+2.42s freq=771.9Hz text=JA1FWS OK2BV JN89
[INF] [ft8] 200702 snr=+5 dt=+1.38s freq=821.9Hz text=LY2EW DL1KDA RR73
[INF] [ft8] 200701 snr=+14 dt=+1.30s freq=890.6Hz text=SA5QED IQ5PJ 73
[INF] [ft8] 200702 snr=-15 dt=+1.38s freq=946.9Hz text=<...> E77VM R-11
[INF] [ft8] 200701 snr=+1 dt=+1.14s freq=956.2Hz text=CQ IU8DMZ JN70
[INF] [ft8] 200702 snr=+17 dt=+1.38s freq=1125.0Hz text=CQ HB9CUZ JN47
[INF] [ft8] 200702 snr=-3 dt=+1.38s freq=1156.2Hz text=CQ HA1BF JN86
[INF] [ft8] 200702 snr=+4 dt=+1.54s freq=1290.6Hz text=EA9ACD HA5LGO -13
[INF] [ft8] 200701 snr=-16 dt=+0.66s freq=1343.8Hz text=CQ 4U1A JN88
[INF] [ft8] 200701 snr=+5 dt=+1.30s freq=1368.8Hz text=CQ OK6LZ JN99
[INF] [ft8] 200702 snr=-14 dt=+2.26s freq=1450.0Hz text=CQ RX3ASQ KO95
[INF] [ft8] 200702 snr=+5 dt=+1.38s freq=1512.5Hz text=JO1COV DL4SBF 73
[INF] [ft8] 200702 snr=-4 dt=+1.54s freq=1565.6Hz text=JI1TYA DH1NAS 73
[INF] [ft8] 200701 snr=-13 dt=+1.22s freq=1615.6Hz text=JO1COV PA0CAH JO21
[INF] [ft8] 200702 snr=-13 dt=+1.38s freq=2046.9Hz text=9A9A OK1AWC JO70
[INF] [ft8] 200701 snr=-4 dt=+1.22s freq=2050.0Hz text=PD0CIF/PHOTO
[INF] [ft8] 200702 snr=-16 dt=+1.38s freq=2103.1Hz text=F1BHB SP4TXI 73
[INF] [ft8] 200702 snr=+4 dt=+1.38s freq=2137.5Hz text=LZ365BM <...> 73
[INF] [ft8] 200702 snr=+10 dt=+1.70s freq=2278.1Hz text=PY2DPM ON6UF RR73
[INF] [ft8] 200701 snr=+3 dt=+1.30s freq=2328.1Hz text=CQ R8AU MO05
[INF] [ft8] 200702 snr=+10 dt=+2.18s freq=2387.5Hz text=CQ E75C JN93
[INF] [ft8] 200701 snr=-7 dt=+1.30s freq=2693.8Hz text=CQ OE8GMQ JN66
decode time: 3463 ms
```


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
this resampled recording decodes all 27 messages in about 2.45 seconds.


## Internal FT8 integration test

The test has three steps: upload FT8 tones (automatically aligned to UTC slot
+0.5 seconds), set the simulated source/mode/frequencies, and run the decoder.
The complete commands, expected result and troubleshooting live in
[Integration tests](docs/integration_tests.md). Validate a newly programmed
board first using [hardware validation](docs/hardware_validation.md).
For final external reception see [receiver operation](docs/receiver.md).

## Automated software tests

See [tests/README.md](tests/README.md) for dependencies and the separate Tk
GUI check. Run the hardware-mocked unit tests from this repository root:

```bash
MPLBACKEND=Agg python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Real-board checks remain in [hardware validation](docs/hardware_validation.md)
and [integration tests](docs/integration_tests.md).

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
| `ft8_control.py` | Upload 79 FT8 tones to the FPGA simulator through the control window; commit automatically at the next UTC slot boundary + 0.5 seconds. Requires the FT8-upload-capable bitstream and `receiver_control.py`. This does not decode FT8. | Optional; keep for simulator tests. |
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
README.md                         Software overview and build instructions
docs/hardware_validation.md       Preliminary PL–PS transport checks
docs/integration_tests.md         Full internal FT8 test and expected results
docs/receiver.md                  Final receiver operation
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
