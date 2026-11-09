# Codex: independent review of this STWIFT sample

You are reviewing a fictional HTML/CSS repair demonstration. Do not treat it as an actual paid client engagement.

## Goal

Inspect the source, run the website and automated tests, and independently evaluate whether it convincingly demonstrates the advertised narrow Fiverr service: repairing minor HTML/CSS layout and responsiveness issues.

## Scope

1. Review the HTML semantics, CSS architecture, responsive breakpoints, accessibility, and maintainability.
2. Reproduce the broken state (`index.html?broken=1`) and compare it with the fixed state (`index.html`).
3. Execute the Playwright smoke test (`python tests/check_layout.py`) and inspect its assertions. Supplement it with meaningful checks at 320, 390, 768, 1024, and 1440px if helpful.
4. Verify that the gallery images are faithful to the real website screenshots and that the project is clearly labeled as a self-created demo, never as client work.
5. Identify any real errors, missing tests, misleading claims, or unsafe code. Rank by severity and support claims with file paths and reproducible evidence.
6. On the first pass, do NOT change code. Give a concise audit with an actionable improvement plan. Only implement fixes after approval.
7. Before proposing any public GitHub publication, verify no secrets, credentials, private material, or copyrighted third-party assets are included.

## Acceptance criteria

- At 390px viewport, `after` has no horizontal overflow; `before` clearly demonstrates the bug.
- At desktop viewport, corrected hero and navigation do not overlap.
- The repository runs locally without credentials or API keys.
- Gallery is in Fiverr-friendly 1280×769 PNG format.
- README explains how to reproduce both states and discloses that this is an independent demo.

Treat autonomous optimization suggestions as hypotheses until supported by tests or evidence.
