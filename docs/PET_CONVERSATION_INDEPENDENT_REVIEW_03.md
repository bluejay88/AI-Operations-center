# PET Conversation Independent Review 03

## Decision

**Development evidence accepted; release certification withheld.** All five reviewed catalog features must remain `planned` (`P`). The implementation provides a useful, accessible browser conversation surface, but physical speech evidence and stronger interruption/privacy boundaries are still required.

## Rubric

Each feature is scored out of 100: functional behavior 30, safety/privacy 25, accessibility 20, fallback/resilience 15, release evidence 10. A release candidate requires at least 85 overall, no critical boundary ambiguity, physical-device proof, and Brain/independent approval.

| Feature | Score | Review result |
|---|---:|---|
| `PET-03-01` Text chat | 84 | Escaped transcript rendering, accessible composer/log, bounded request, and no automatic task creation. Needs authenticated live-model and physical mini-dashboard proof. |
| `PET-03-03` Speech-to-text | 68 | User-initiated, non-continuous dictation with typed fallback and permission-error messaging. Missing secure-context check, browser speech-provider privacy disclosure, and physical microphone proof. |
| `PET-03-04` Text-to-speech | 78 | Explicit playback, per-message controls, stop behavior, unavailable-browser state, and reduced-motion support. Needs physical speaker/headphone, voice availability, and assistive-technology coexistence proof. |
| `PET-03-08` Detect interruptions | 55 | Explicit Stop Voice, Cancel Response, Escape, and dictation-over-playback cancellation are useful. This is not automatic spoken interruption detection; fetch abort does not prove server-side model cancellation. |
| `PET-03-10` Remember context | 76 | Ten-message outbound context, thirty-message session bound, visible count, and clear control. Context is still readable by same-origin scripts and is transmitted to the Brain/model workflow; no sensitive-data warning or per-message deletion exists. |

## Verified boundaries

- Model output and speech-button attributes are HTML escaped before insertion.
- Chat sets `auto_create_tasks: false`; conversation cannot directly create tasks or execute protected actions.
- Microphone recognition begins only from the Dictate button and uses `continuous = false`; there is no always-on microphone.
- Playback begins only from explicit user controls; replies do not auto-speak.
- Unsupported recognition/playback disables the relevant control while typed chat remains available.
- Context uses `sessionStorage`, not persistent `localStorage`, is truncated to thirty messages, and sends only the latest ten messages.
- Clear Transcript removes the stored conversation context for the current machine/tab.
- Cancel Response uses `AbortController`, catches `AbortError`, and retains the conversation context.
- Screen-reader status, transcript labeling, keyboard cancellation/submission, 40-pixel controls, and reduced-motion behavior are present.

## Boundary findings

### High: cancellation wording exceeds provable scope

`AbortController` cancels the browser's wait for `/models/query`. Once the server accepts the request, upstream provider work may continue. The UI must not be interpreted as proof that Brain/model computation stopped. Server cancellation correlation and receipt evidence are required for that claim.

### High: PET-03-08 is explicit interruption control, not interruption detection

The implementation detects button/Escape intent and cancels playback when dictation starts. It does not listen for user speech while the PET is speaking or automatically detect barge-in. Full feature certification requires a consented, device-tested barge-in design or a narrower feature claim.

### Medium: browser speech privacy boundary is not disclosed

Depending on browser/OS, speech recognition may be processed by a browser-vendor service. The UI says voice is ready but does not explain that boundary before microphone use. No raw audio is intentionally stored by this application, but that does not describe browser-provider processing.

### Medium: session context is bounded, not confidential storage

`sessionStorage` limits persistence to the tab/session but is not encrypted application storage and remains accessible to same-origin scripts. The latest ten messages are sent to the model workflow. Users should avoid credentials, secrets, regulated data, and unrelated private content.

### Medium: secure-context and permission behavior needs physical proof

Speech APIs vary by browser, operating system, policy, locale, installed voices, and whether the dashboard is delivered in a secure context. Constructor detection alone does not prove microphone permission or service availability.

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

Expected result: eight passing review controls and four strict expected failures representing unresolved release gates. Expected failures must not be converted to passing assertions without corresponding implementation and physical evidence.
