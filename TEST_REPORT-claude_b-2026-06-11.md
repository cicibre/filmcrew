# Filmcrew test report — claude_b, 2026-06-11

Tested the "all 12 fixes complete" build (HEAD `79c28c3`) on macOS (Python 3.14, ffmpeg present). Ran dry-run end-to-end, drove the gates, drove resume, exercised the validator. Honest results below — the headline is that **the pipeline cannot currently complete a job through its intended gated flow, and produces no video.** Two real bugs, both small fixes. The architecture itself is sound.

## ✅ Confirmed working
- **#1 Gate pause** — genuinely raises `GatePause`, halts the pipeline, writes `_paused_manifest.json`, exits clean. Real.
- **#10 Schema validator** — `validate(bad)` returns 8 precise missing-field errors + a defaults-warning; `validate(good)` passes clean. Solid.
- **#5 Model alias** — config pins `claude-sonnet-4-6` (correct ROVA snapshot).
- **Orchestration** — with gates off, all 8 roles run in sequence (Director→Screenwriter→Storyboard→Cinematographer→Sound→Editor→deliver→Archivist) and reach `status: complete`. library.json + manifest written (#7 persistence half-works — see #3).

## ❌ Confirmed broken
### #3 Resume (`--continue`) — BLOCKING, infinite loop
`--continue` re-pauses at the *first* gate (`director_plan`) forever; no job can finish via the intended flow.
**Root cause:** systematic key mismatch. `producer.py` `self.phases` uses keys `("director","screenwriter","storyboard",...)`, but each role writes its output under a *semantic* key (`director.py` → `manifest["director_plan"]`, screenwriter → `screenplay`, etc.). The resume-skip check is `if phase_key in manifest` (producer.py:57) → `"director" in manifest` is always False (only `"director_plan"` is present) → the gated phase never skips → re-runs → its gate re-fires → re-pauses.
**Fix:** make the skip-check use the role's real output key. Add a `phase → output_key` map (mirror the existing `_gate_name_for_phase`: director→director_plan, screenwriter→screenplay, storyboard→storyboard, cinematographer→cinematography, sound_designer→sound_design, editor→edit) and skip when `output_key in manifest`. (Or normalize every role to write under `manifest[phase_key]`.)

### #2 ffmpeg render — produces NO .mp4 on macOS
`[Editor] Frame 1 render failed:` (empty error), no clips, no final mp4 — only `_concat.txt`.
**Root cause (likely):** `editor.py` builds `drawtext=text=...` with no `fontfile=`. macOS ffmpeg's drawtext has no default font and fails. Secondary issue: the error path prints `r.stderr[:200]` but it came through empty — the failure reporting itself is weak (you can't see *why* it failed).
**Fix:** pass an explicit `fontfile=` (e.g. `/System/Library/Fonts/Supplemental/Arial.ttf`, or detect per-OS), and surface the real ffmpeg stderr on failure.

## ⚠ Not verifiable without keys / production mode
- **#4 real media APIs** (Runway/Replicate/ElevenLabs/Suno) — production-only, untested.
- **#8 cost tracking** — needs real LLM calls (script-mode + ANTHROPIC_API_KEY + `anthropic` pkg, which isn't installed locally). Dry-run only prints the Producer's *budget estimate* (~$23), not real token spend.
- **#9 delivery channels** (Flow/Telegram) — needs a real run to confirm they fire.
- **#6 Clarity handoff server** — endpoint not exercised.

## Verdict
4 fixes verified working, **2 broken (one blocking)**, ~4 unverifiable locally. The "all 12 complete" status was optimistic — the core loop doesn't close (resume) and there's no video (render). Both fixes are small and the orchestration underneath is genuinely good. Recommend: fix #3 + #2 first (they unblock everything and are needed to even *see* #4/#8/#9 work), then re-test with a real key.

— claude_b (tested, did not modify any source; config gate-toggle was reverted clean)

---

## RESOLUTION — both bugs fixed + verified (2026-06-11, claude_b)

Ciara said fix them. Done. Fixing resume turned out to need **four** sub-fixes (the bug had layers), and render needed **four** too — each only visible after the previous was cleared.

**#3 Resume — now completes the full gated flow.** Verified: fresh dry-run pauses at gate 1, then 4× `--continue` advances director→screenwriter→storyboard→final_cut→**COMPLETE**.
- `producer.py`: skip-check now uses each role's real output key (`_output_key_for_phase`), not `phase_key`.
- `main.py` `_load_manifest`: now finds `_paused_manifest.json` / `_partial_manifest.json` (was only looking for the bare `_manifest.json`, so a paused job could never be reloaded).
- `main.py`: resume restores the job's saved **mode** (was silently flipping dry-run → PRODUCTION / real API spend).
- `producer.py` + `main.py`: added a real **gate-approval** mechanism (`_approved_gates` / `_paused_at_gate`) — without it the always-re-run editor re-fired `final_cut` forever. There was previously *no way to approve a gate*.

**#2 ffmpeg render — now produces a real .mp4.** Verified: 150s · 1920×1080 · valid H.264.
- `editor.py`: switched both ffmpeg calls from hand-escaped `shell=True` strings to **argument lists** (the quote-escaping was emitting "Invalid argument").
- Removed `2>&1` so failures are actually visible (they were being swallowed → empty error).
- Collapse all whitespace in the caption text (newlines were breaking the command).
- Concat list now uses **absolute paths** (ffmpeg resolves relative entries against the list-file dir).
- Added a font probe + a **graceful fallback**: this ffmpeg has no `drawtext` (built without libfreetype) — so it renders a plain colored clip instead of failing. Real video on any ffmpeg build.

**Still not verified** (need a real key / production mode): #4 media APIs, #8 token cost-tracking, #9 delivery channels, #6 handoff server. Recommend a real-key `--script-mode` smoke next.
