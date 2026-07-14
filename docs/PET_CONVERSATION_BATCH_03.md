# PET Conversation Batch 03 Evidence

## Scope

This batch implements browser-side evidence for five exact Local Conversation feature contracts on every mini dashboard while leaving catalog execution states `planned` until physical-device, independent, and Brain release gates are satisfied.

| Feature | Implemented evidence | Safe fallback |
|---|---|---|
| `PET-03-01` Text chat | Accessible transcript, typed composer, audited `/models/query` request, visible failure reply | Typed text remains available when Brain is unreachable; no task is auto-created |
| `PET-03-03` Speech-to-text | User-initiated Web Speech dictation, interim preview, review-before-send | Unsupported/denied microphone path announces typed-input fallback |
| `PET-03-04` Text-to-speech | Latest-reply and per-message playback through browser speech synthesis | Controls disable and announce when browser playback is unavailable |
| `PET-03-08` Detect interruptions | Explicit Stop Voice, Cancel Response, Escape shortcut, playback cancellation when dictation starts | Preserves typed transcript and session context after interruption |
| `PET-03-10` Remember context | Last ten session messages supplied to the model; last thirty retained in session storage | Context is device/session scoped, bounded, user-clearable, and never promoted to durable memory |

## UI and accessibility evidence

- Existing cyan/violet mini-dashboard identity, PET surfaces, and responsive grid are preserved.
- Listening has a visible and screen-reader status, `aria-pressed`, and a reduced-motion override.
- Speech features only start from explicit user actions; there is no always-on microphone.
- Stop/cancel controls expose interruption as an intentional operation rather than hiding it as an error.
- `Ctrl/Cmd+Enter` submits; `Escape` stops voice and cancels an in-flight model response.
- Protected actions remain approval-gated in the model prompt. Chat requests set `auto_create_tasks: false`.

## Verification commands

```powershell
node --check laptop_packages/shared/mini-dashboard.js
python -m pytest tests/test_pet_conversation_ui.py -q
```

## Release status

Implementation and local automated checks are development evidence only. All five catalog entries remain `planned`. Advancement requires the repository's independent review, physical laptop browser/microphone/speaker proof, Brain feedback, and release approval gates.
