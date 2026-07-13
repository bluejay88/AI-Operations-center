# PET Motion System — UI Team Handoff

## Shipped behavior

- Connectivity maps to `strong`, `limited`, or `lost` signal orbits.
- Workload maps to `calm`, `ready`, `busy`, or `critical` packet flow.
- Running-task titles deterministically select meaningful motion (build, test, debug, research, design, report, connectivity, or release).
- Completion clusters trigger a finite two-cycle flare instead of a permanent celebration loop.
- Mini-dashboard PET labels live in a dedicated readout rail with ellipsis and a mobile stack, removing the previous overlap risk.

## Motion and asset budget

- Runtime animation assets: **0 GIFs, 0 videos, 0 canvas loops, 0 network requests**.
- Continuous layers per PET: one orbit plus three packet lines; the completion flare is finite.
- Continuous motion uses `transform` and `opacity`. Paint-heavy glow changes remain limited to existing task-state effects.
- New CSS + JS budget: target under 16 KB uncompressed across shared/main surfaces; no animation library.
- PET stages use layout/paint containment. Main PET panels use `content-visibility: auto` so offscreen companions do not consume the same rendering budget.
- Any future GIF must be smaller than an equivalent SVG/CSS treatment, below 250 KB, lazy loaded, non-looping by default, and have a reduced-motion replacement.

## Second-team visual rubric

Test Brain, Dev, Research, Business, and Security identities at 360, 768, 1024, and 1440 CSS pixels.

1. Long machine/status strings never cover the PET or escape their panel.
2. Lost signal is distinct without relying on animation alone.
3. Queue and running changes update motion on the next refresh without layout shift.
4. Five simultaneous PETs remain responsive; verify Chrome Performance has no sustained long tasks caused by animation.
5. `prefers-reduced-motion: reduce` produces a stable PET and preserves all state text.
6. Keyboard navigation and control IDs are unchanged.
7. Completion flare ends after two cycles and does not continuously distract operators.
8. No new external asset request appears in the Network panel.

## Recommended follow-up

Capture baseline screenshots at the four target widths, run a 10-minute soak with changing queue counts, and record frame timing on the lowest-powered laptop before promoting the visual layer beyond staged release.
