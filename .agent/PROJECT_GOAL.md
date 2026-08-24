# Project Goal

## Goal
Build SENTRY into an embodied household intelligence that maintains a grounded, evolving understanding of the physical home and uses that context to provide useful, appropriately restrained assistance.

## Objective success criteria
- SENTRY maintains reliable local world state for the office and preserves physical-event history.
- The V0.1 office prototype can detect presence, conservatively identify an enrolled primary user, track sessions, and expose grounded state to an assistant.
- The assistant can answer office-state questions and may speak proactively when a deterministic policy finds a useful, non-duplicative reason.
- The system fails explicitly when perception or assistant services are unavailable and does not invent occupancy or identity.
- A documented, unattended acceptance run demonstrates reliable one-room behavior before expansion.

## Non-goals
- V0.1 is not a whole-home deployment, security alarm, medical system, emergency monitor, or life-safety system.
- V0.1 does not require ESP32s, Home Assistant, Frigate, mmWave, BLE room positioning, Wi-Fi CSI, multiple rooms/cameras, a TV avatar, autonomous smart-home control, or full routine learning.

## Hard constraints
- The first scope is one office using the existing Windows PC, one webcam, microphone, speakers, local storage, and available CPU/GPU resources.
- Raw webcam frames and biometric enrollment data remain local by default and out of source control.
- SENTRY owns grounded physical events and sessions locally; an LLM is not the continuous vision processor or physical-event database.
- DAWN is the preferred assistant foundation under evaluation. Xiaomi Miloco is an architectural reference only.
- New dependencies, upstream derivation/forking, cloud video, infrastructure expansion, and scope changes require documented evidence and Architect authorization.

## Goal-change rule
The project goal may change only through explicit user/authorized strategic decision. Roadmaps, milestones, and implementation plans may change when evidence changes without rewriting historical records.
