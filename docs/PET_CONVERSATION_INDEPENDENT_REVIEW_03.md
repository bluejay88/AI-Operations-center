# PET Conversation Independent Review 03

## Decision

**Code-level remediation accepted; physical release certification withheld.** All five reviewed catalog features must remain `planned` (`P`). The implementation provides an accessible browser conversation surface with explicit speech privacy and request-scoped cancellation boundaries, but physical speech evidence and automatic barge-in remain outstanding.

## Rubric

Each feature is scored out of 100: functional behavior 30, safety/privacy 25, accessibility 20, fallback/resilience 15, release evidence 10. A release candidate requires at least 85 overall, no critical boundary ambiguity, physical-device proof, and Brain/independent approval.

| Feature | Score | Review result |
|---|---:|---|
| `PET-03-01` Text chat | 84 | Escaped transcript rendering, accessible composer/log, bounded request, and no automatic task creation. Needs authenticated live-model and physical mini-dashboard proof. |
| `PET-03-03` Speech-to-text | 80 | User-initiated, non-continuous dictation with typed fallback, secure-context/permission readiness, privacy disclosure, and permission-error messaging. Physical microphone/browser proof remains required. |
| `PET-03-04` Text-to-speech | 78 | Explicit playback, per-message controls, stop behavior, unavailable-browser state, and reduced-motion support. Needs physical speaker/headphone, voice availability, and assistive-technology coexistence proof. |
| `PET-03-08` Detect interruptions | 70 | Explicit Stop Voice, Escape, dictation-over-playback cancellation, and request-ID-scoped API cancellation are useful and honestly labeled. This is still not automatic spoken interruption detection, and upstream provider cancellation is not guaranteed. |
| `PET-03-10` Remember context | 76 | Ten-message outbound context, thirty-message session bound, visible count, and clear control. Context is still readable by same-origin scripts and is transmitted to the Brain/model workflow; no sensitive-data warning or per-message deletion exists. |

## Verified boundaries

- Model output and speech-button attributes are HTML escaped before insertion.
- Chat sets `auto_create_tasks: false`; conversation cannot directly create tasks or execute protected actions.
- Microphone recognition begins only from the Dictate button and uses `continuous = false`; there is no always-on microphone.
- Playback begins only from explicit user controls; replies do not auto-speak.
- Unsupported recognition/playback disables the relevant control while typed chat remains available.
- Dictation is disabled outside a secure context and when current microphone permission is denied; permission changes refresh the readiness label.
- The interface discloses possible browser/OS speech-provider processing and states that the app does not intentionally store raw audio.
- Context uses `sessionStorage`, not persistent `localStorage`, is truncated to thirty messages, and sends only the latest ten messages.
- Clear Transcript removes the stored conversation context for the current machine/tab.
- Cancel Response immediately aborts the browser wait and sends a stop request for only the unpredictable active request ID. API receipts explicitly set `scope=request_only` and `upstream_cancellation_guaranteed=false`.
- Screen-reader status, transcript labeling, keyboard cancellation/submission, 40-pixel controls, and reduced-motion behavior are present.

## Boundary findings

### Remediated boundary: request-scoped cancellation is honest

The UI now aborts its own wait and sends a cancellation request keyed to the active unpredictable request ID only. The API cancels the matching in-process task and explicitly reports that upstream cancellation is not guaranteed. Provider-specific cancellation and physical log correlation remain release evidence, not a code-level claim.

### High: PET-03-08 is explicit interruption control, not interruption detection

The implementation detects button/Escape intent and cancels playback when dictation starts. It does not listen for user speech while the PET is speaking or automatically detect barge-in. Full feature certification requires a consented, device-tested barge-in design or a narrower feature claim.

### Remediated boundary: browser speech privacy is disclosed

The UI now explains before use that a browser/OS speech provider may process audio and that this application does not intentionally store raw audio. Provider-specific policy verification and user consent behavior still require physical-browser review.

### Medium: session context is bounded, not confidential storage

`sessionStorage` limits persistence to the tab/session but is not encrypted application storage and remains accessible to same-origin scripts. The latest ten messages are sent to the model workflow. Users should avoid credentials, secrets, regulated data, and unrelated private content.

### Remediated code gate; physical secure-context and permission behavior still needs proof

The client now checks `window.isSecureContext`, inspects microphone permission where the Permissions API supports it, reacts to permission changes, and preserves typed fallback. The server permission policy allows microphone access only to the same origin. These checks still do not prove device/service availability.

### Low: visual labels contain encoding artifacts in the reviewed checkout

Several middle-dot/ellipsis strings render in source output as mojibake (`Â·`, `â€¦`). Browser/encoding verification should confirm whether users see those artifacts before release.

## Required physical and integration evidence

1. Business, Research, and Dev laptops: current Chrome/Edge versions, HTTPS or verified secure context, and exact dashboard URL.
2. Microphone: permission allow/deny/revoke flows, interim and final transcript accuracy, locale, silence timeout, stop behavior, and confirmation that no capture continues after stop/page hide.
3. Speaker/headphones: default voice availability, playback start/end/error, repeated Speak, Stop Voice latency, volume/mute state, and screen-reader coexistence.
4. Browser fallback: Firefox/Safari or an intentionally unsupported profile must show disabled voice controls while typed chat remains fully operable.
5. Cancellation: correlate client request ID with Brain/provider logs; prove whether upstream work stops or relabel the control as client-side dismissal.
6. Context: reload/tab-close behavior, machine-key isolation, clear persistence, long-message truncation, malicious markup, prompt-injection handling, and sensitive-data warning review.
7. Accessibility: keyboard-only flow, 200% zoom, 360-pixel viewport, Windows High Contrast, NVDA/Narrator announcements, focus order, and no announcement duplication.
8. Authenticated `/models/query` canary: one safe question per laptop with request, response, risk label, and no task/approval side effect.

## Automated review evidence

Run:

```powershell
python -m pytest tests/review_test_pet_conversation_batch_03.py -q -rxX
```

Expected result: eleven passing review controls and one strict expected failure for unresolved automatic voice interruption detection. The expected failure must not be converted to a passing assertion without corresponding implementation, consent design, and physical evidence.
