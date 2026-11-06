# FT8 residual-subtraction decoder

This checkout is the `subtract-test` branch of
[`guido57/ESP32_ft8_lib`](https://github.com/guido57/ESP32_ft8_lib), arranged
for the SmartZynq Xillinux target. It decodes FT8 and FT4 WAV recordings and
provides a live FT8 capture program for the receiver's 8 kHz PCM stream.

The decoder performs three passes by default: it decodes the original
waterfall, synthesizes and subtracts every successful FT8 signal, then rebuilds
the waterfall to recover signals that were masked by stronger transmissions.

## Xillinux quick start

The checkout lives at `/root/ft8_decoder`.

```bash
cd /root/ft8_decoder
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
sox tests/20m_busy/test_01.wav -r 8000 -c 1 -b 16 test_01_8k.wav
soxi test_01_8k.wav
./ft8_decoder test_01_8k.wav -1
```

`soxi` must report an 8000 Hz, one-channel, 16-bit PCM WAV. On the Cortex-A9,
this resampled recording decodes all 27 messages in about 2.45 seconds. The Cortex-A9 build raises FT8_MAX_CANDIDATES to 80, avoiding an 8 kHz search-list cap that previously excluded the two signals near 2.05 kHz.

## Live SmartZynq receiver capture

Build the capture program:

```bash
cd /root/ft8_decoder
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

| Command | Result |
| --- | --- |
| `make` | Native host `ft8_decoder` build using the local compiler defaults. |
| `make a9` | Clean and build `ft8_decoder` for Cortex-A9 with NEON and hard-float. |
| `make stream` | Build `build/a9-stream/ft8-subtract-stream-a9`. |
| `make clean` | Remove the native decoder build and executable. |
| `make stream-clean` | Remove the live-stream build. |

## Layout

```text
src/ft8/                 FT8 protocol, LDPC, packing and message code
src/fft/                 KissFFT implementation
src/decode_ft8.cpp       Waterfall search, decode passes and subtraction loop
src/subtract.cpp         FT8 waveform synthesis and residual cancellation
src/decoder_api.cpp      Slot and streaming decoder API
src/main.cpp             Native WAV-file command-line application
src/ft8_subtract_stream.cpp
                          SmartZynq live PCM capture application
tests/                   Reference WAV recordings
```

## ESP32 and PlatformIO

The same core also remains usable with PlatformIO. The project configuration
is in `platformio.ini`; the native and ESP32-S3 environments can be built with
`pio run --environment native` and `pio run --environment esp32s3` when
PlatformIO is installed.

## Credits

The decoder originates from Karlis Goba (YL3JG)'s `ft8_lib`; this version adds
the FT8 residual-subtraction pipeline. KissFFT is by Mark Borgerding. FT8 is
part of the WSJT-X protocol ecosystem.
