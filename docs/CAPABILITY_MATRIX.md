# Resident Capability Matrix

Codex tool annotations describe intent; `ExecutionAuthority` performs the host
enforcement. The current resident MCP exposes exactly 33 tools:

| Exact MCP tool | Tier | Resident behavior | Authorization |
|---|---:|---|---|
| `get_current_office_state` | 0 | automatic truthful read | none |
| `get_office_history` | 0 | automatic bounded read | none |
| `get_office_reminders` | 0 | automatic bounded read | none |
| `get_acknowledgement_preference` | 0 | automatic bounded read | none |
| `get_recent_proactive_action` | 0 | automatic bounded read | none |
| `get_routines` | 0 | automatic bounded read | none |
| `get_home_weather` | 0 | automatic bounded read | none |
| `get_local_time` | 0 | automatic bounded read | none |
| `get_alarms` | 0 | automatic bounded read | none |
| `get_system_volume` | 0 | automatic local read | none |
| `get_active_window` | 0 | automatic local read | none |
| `find_applications` | 0 | automatic local read | none |
| `get_execution_authority_status` | 0 | sanitized security read | none |
| `get_recent_execution_audit` | 0 | sanitized bounded read | none |
| `get_pending_authorization` | 0 | sanitized pending-state read | none |
| `capture_desktop` | 1 | current-turn explicit request only | direct request |
| `inspect_office_camera` | 1 | current-turn explicit request; ephemeral frames | direct request |
| `create_next_office_reminder` | 1 | bounded existing mutation | direct request |
| `cancel_pending_office_reminder` | 1 | bounded existing mutation | direct request |
| `set_acknowledgement_preference` | 1 | bounded existing mutation | direct request |
| `create_one_shot_alarm` | 1 | bounded existing mutation | direct request |
| `cancel_alarm` | 1 | bounded existing mutation | direct request |
| `launch_application` | 1 | allow-listed desktop launch | direct request |
| `open_web_page` | 1 | exact public HTTP(S) URL only | direct request |
| `open_local_artifact` | 1 | validated local artifact display | direct request |
| `set_system_volume` | 1 | bounded local volume mutation | direct request |
| `adjust_system_volume` | 1 | bounded local volume mutation | direct request |
| `set_system_muted` | 1 | bounded local mute mutation | direct request |
| `control_media` | 1 | bounded MPRIS control | direct request |
| `propose_file_move` | 2 | non-overwriting workspace-to-approved-home move | direct request or explicit deferred dialogue |
| `press_keys` | 2 | active-window identity revalidated at execution | direct request or explicit deferred dialogue |
| `type_into_active_window` | 2 | active-window identity revalidated; credential-like text blocked | direct request or explicit deferred dialogue |
| `click_desktop` | 2 | active-window identity revalidated at execution | direct request or explicit deferred dialogue |

Native public research and ordinary reasoning are Tier 0. Workspace-local file,
code, shell, test, and image operations are Tier 1, constrained by the resident
sandbox and gated by a content-free pre-turn audit record.

Tier 3 actions—authenticated form submission, reservations, sends, purchases,
uploads, Git push, deployment, destructive overwrite, package/system changes,
and other external commitments—currently have no resident executor and remain
blocked. Risk tiers describe enforcement and audit routing; they do not by
themselves require a second conversational approval.
Tier 4 credential access, authority/profile mutation, self-authorization,
arbitrary sudo, broad deletion, hidden persistence, unrestricted remote access,
automatic transcript mining, Codex memory generation, and direct future
Obsidian-vault writes are prohibited and not confirmable.

Apps, plugins, browser/CDP, generic computer use, unmanaged MCP servers, login
shells, shell networking, and broad-home writes are disabled in the resident
profile. The separate manual development profile is not reachable from voice.
