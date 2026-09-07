# Vbee Release Readiness Checkpoint

**Date:** 2026-09-07  
**Branch:** `fix/vbee-release-readiness`  
**Baseline:** `60b3b93`  
**Status:** PASS for the repaired Vbee scope; full desktop release gate remains PARTIAL.

## Evidence and root causes

- Runtime profile audit found the signed-in automation profile at
  `%LOCALAPPDATA%\VKDubStudio\browser_profiles\vbee` and Chromium's `Last Browser`
  marker points to Microsoft Edge.
- Historical Windows event evidence tied the hard crash to background-thread QWidget
  mutation in `Qt6Gui.dll`. Current code uses `VbeeWorkflowJob` Qt signals for all UI
  state/progress delivery; the regression test proves receiving slots run on the GUI
  thread.
- The latest captured Vbee page shows a real provider rejection (`Không đủ điểm`), not
  a local file-permission failure. Selectors now classify that state as quota failure.
- Previous download handling wrote directly to the final filename, trusted the provider
  filename and could leave partial files. Downloads now use a sanitized filename, a
  bounded HTTPS fallback, a temporary `.part` file and atomic promotion.

## Implemented

- Reuse the one canonical Vbee profile and the browser executable recorded by that
  profile; no per-run profile is created.
- Pass the explicit staging download directory to Playwright.
- Remove only Vbee `.part` and `.crdownload` staging files after interrupted runs.
- Redact technical failures before logging/signalling and preserve actionable browser,
  timeout, file and quota messages.
- Fix missing `redact` import in Vbee API error handling.

## Verification

| Gate | Result |
|---|---|
| Vbee focused tests | PASS — 41 passed |
| Ruff, changed Vbee files | PASS |
| mypy, Vbee modules/controller | PASS |
| Live profile smoke | PASS — canonical profile reused, `logged_in=True`, dubbing URL reached |

The live smoke only navigated to the Vbee Dubbing page and checked authentication. It
did not submit a paid conversion. A paid end-to-end conversion is currently blocked by
the provider account's insufficient points and is therefore not claimed as verified.
