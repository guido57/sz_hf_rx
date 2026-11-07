# PL–PS FT8 integration tests

This guide owns the complete internal signal-path test: Python tone upload,
PL RF simulation, DDC/SSB demodulation, Xillybus PCM transport and PS decoding.
For preliminary transport checks see [hardware validation](hardware_validation.md).
For final off-air use see [receiver operation](receiver.md).

## Required hardware and software

Use the single-channel `hf_ssb_receiver` PL project with SSB marker `0xd3`
and FT8 upload marker `0xf8`; build/program it using the hardware repository
[deployment guide](https://github.com/guido57/SmartZynq_SP2_HF_receiver/blob/master/docs/deployment.md).
Its [interface contract](https://github.com/guido57/SmartZynq_SP2_HF_receiver/blob/master/docs/ps_pl_interface.md)
is authoritative for endpoints, rates and registers. This software checkout
must include the +0.5-second FT8 commit scheduler and decoder search including
the start of the slot. A valid reference-WAV decode does not by itself verify
this hardware interface.

Record both repository revisions and dirty status, the programmed bitstream
path and SHA-256, board revision, test commands and output. Use `git rev-parse
HEAD`, `git status --short` and `sha256sum IMAGE.bit` on the corresponding
machines. Preserve logs with each test run. Historical observations below
do not identify an exact bitstream hash and must not be treated as a complete
versioned compatibility record.

## Internal FT8 integration test

The test has three steps:

1. **Upload FT8 tones.** `ft8_control.py` stages and verifies the 79 tones,
   then automatically commits them at the next UTC 15-second boundary plus
   0.5 seconds. It prints the target time while waiting. The commit restarts
   the simulator at symbol 0; the sequence repeats every 15 seconds.
2. **Set mode and frequencies.** Select the internal simulated source, USB
   mode, 14.074 MHz tuning and 14.0755 MHz simulated carrier. The signal is
   at 1500 Hz audio.
3. **Run the decoder.** It automatically captures at the next UTC boundary;
   the already aligned simulator begins its next frame 0.5 seconds later.

Run on Xillinux:

```bash
python3 /root/sz_hf_rx/scripts/ft8_control.py
python3 /root/sz_hf_rx/scripts/receiver_control.py \
  --source simulated --mode usb \
  --tune 14074000 --sim-frequency 14075500
cd /root/sz_hf_rx/ft8_decoder
make stream
build/a9-stream/ft8-subtract-stream-a9 --slots 1 --base-mhz 14.074
```

The decoder timing search includes the beginning of the captured slot, so
transmissions starting at +0.5 seconds can be found. Rebuild with `make stream`
after updating decoder sources.

No separate Python scheduling block is needed. The upload can wait up to
15.5 seconds; its hardware I/O timeouts exclude that intentional wait.
Close other audio readers before running the decoder. After it starts,
allow up to 15 seconds to reach the boundary, 15 seconds to capture, and
additional decoding time. The board clock must remain stable during the test.
Linux scheduling and device latency can shift the actual start slightly.

The default uploaded message is `G0XYZ K1ABC FN43`; expect `decoded=1`
and a decode near `freq=1500.0Hz`. Exact SNR and timing can vary. Uploading
replaces any custom tone sequence. After reboot or FPGA reconfiguration,
upload again to restore alignment. `decoded=0` means no valid message was
recovered. `--base-mhz` only labels results; it does not tune the receiver.

The capture program reads 120,000 mono PCM16 samples at 8 kHz from
`/dev/xillybus_read_8` per slot and runs three decoding/subtraction passes.
It uses a two-slot buffer and supports one audio stream. Multiple receiver
channels require deinterleaving and separate decoder instances.

The first progress message appears only after capture completes. There is
no built-in capture timeout: use `timeout 40s` before the decoder command
for a bounded diagnostic run (exit status 124 indicates timeout). Raw mode
does not supply audio to this endpoint, so USB/LSB configuration is required.

For external reception, skip the tone upload and select
`--source external --mode usb --tune 14074000` with `receiver_control.py`
(adjust tuning for the desired band), then run the same decoder command.

## Observed result and limits

The aligned +0.5-second test recovered:

```text
results stage=full ... decoded=1
snr=+20 dt=+0.50s freq=1500.0Hz text=G0XYZ K1ABC FN43
```

The reference 8 kHz WAV also recovered all 27 known messages after extending
the decoder timing search. These are recorded observations, not newly rerun
tests for this documentation change. PL emits continuous-phase 8-FSK without
Gaussian shaping; this validates the integration path rather than complete
FT8 waveform fidelity or external weak-signal performance.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No output for the first 15–30 seconds | Normal boundary wait plus complete-slot capture; the first progress line follows capture. |
| Wait continues indefinitely | Select USB/LSB, verify SSB image and close other audio readers; raw mode supplies no audio here. Use `timeout 40s` for a bounded test. |
| Upload marker error | Loaded image lacks the FT8 upload interface. |
| Strong signal but `decoded=0` | Re-upload using the aligned uploader; verify source/tuning and rebuild the decoder so its timing search includes +0.5 s. |
| Audio overflow | Lost samples; stop competing consumers and repeat. |

