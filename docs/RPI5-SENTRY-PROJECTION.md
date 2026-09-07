# RPi5 SENTRY projection

## Current state

The Linux PC remains the processing and household-authority host. The RPi5 at
`192.168.254.4` runs only the SENTRY visual projection and I/O bridge:

```text
RPi5 webcam/microphone → authenticated PCM stream → Linux PC SENTRY
Linux PC SENTRY Kokoro WAV → authenticated playback endpoint → RPi5 speaker/TV
Linux PC voice metadata → authenticated status tunnel → RPi5 orb projection
```

No ANIMA database, Home Assistant, OPA, provider, or model credentials are
installed on the Pi. Audio remains ephemeral and is not written to disk by the
projection transport.

## Installed services

The Pi user `sketch` has these enabled services:

- `sentry-projection-io.service` — bounded PipeWire microphone/WAV endpoint;
- `sentry-projection-sync.service` — status-only sync into the Pi runtime dir;
- `sentry-projection-ui.service` — `sentry_ui.py --projection` under labwc.

The PC has `sentry-projection-status.service` and a reconnecting
`sentry-projection-tunnel.service`. The reverse tunnel is used for the status
leg because the current network allows ICMP and PC→Pi traffic but refused the
new Pi→PC TCP listener directly.

## Audio output

The projection is voice-only: it does not display the current audio target or
provide a clickable selector. SENTRY's typed `set_projection_audio_output`
tool routes speech to `usb` or `hdmi` through the authenticated Pi control
endpoint. USB playback uses the Pi's PipeWire default sink. The connected TV's
HDMI ALSA plugin is used directly because this Pi image does not publish that
device as a PipeWire sink; HDMI selection performs a silent fixed-device probe
before persisting the choice. Because the voice synthesizer emits 24 kHz mono
speech while the HDMI ALSA endpoint accepts 48 kHz stereo PCM, the projection
bridge converts each bounded WAV in memory with the Pi's existing `ffmpeg`
binary before playback. HDMI audio remains bounded and ephemeral.

## Evidence and limits

- PC-generated silent WAV playback through the Pi endpoint: observed success.
- PC-generated Kokoro phrase delivered to the Pi endpoint: observed success.
- Pi microphone stream: observed live PCM bytes at 16 kHz mono.
- PC voice listener: active with `LISTENING`, `wake_enabled=true`, and remote
  microphone transport configured.
- Pi labwc/GTK projection: active with HDMI-A-2 enabled at 3840×2160 and zero
  UI restarts after the final projection fix.

This is live local deployment evidence, not a claim of full SENTRY/ANIMA
household qualification or native Pi5 performance qualification. The current
PC SENTRY UI and resident processing services remain intact.

## Hailo face-matching path

The Pi has a detected Hailo8 device and SENTRY now includes a bounded
`HailoFaceRuntime` contract for the official Hailo Apps face pipeline: SCRFD
detection followed by a face-recognition model. The Pi may emit only a typed,
ephemeral identity candidate; ANIMA/SENTRY on the processing host remains
responsible for profile matching authority and household decisions.

The live Pi is currently gated by the externally provisioned Hailo Apps package
and detector/recognizer HEF assets. `hailortcli` and the Python platform
runtime are present, but no qualified face HEFs were found on the Pi. The
runtime reports `HAILO_FACE_MODELS_OR_RUNTIME_UNAVAILABLE` rather than falling
back while claiming Hailo matching. Once the official assets are provisioned,
the fixed command contract is ready for the Pi worker without copying ANIMA,
Home Assistant, OPA, or model credentials to the projection.
