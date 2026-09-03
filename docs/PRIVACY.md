# Privacy

SENTRY keeps microphone audio and camera inspection frames ephemeral unless the operator explicitly requests an artifact. It does not persist ambient transcripts, raw audio, screenshots, biometric vectors, or conversation archives.

The persistent Codex thread is owned by Codex and the SENTRY session pointer stores only thread and usage metadata. Codex-generated memories are disabled. The execution audit stores action metadata only and excludes prompts, transcripts, contents, credentials, biometrics, authentication state, and exact private coordinates.

Private weather coordinates and SENTRY configuration remain local and are not exposed through Luna-visible facts. The future Obsidian personal-memory vault is a planned, separate governed capability and is not created by V0.3.3.
