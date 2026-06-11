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

---

## SCRIPT-MODE SMOKE — real Claude, verified (2026-06-11, claude_b)

Ran `--script-mode` against the live Anthropic API (real key, ~$0.04 spent). This is the first time the real-LLM path has ever executed.

**✅ The LLM API path WORKS.**
- Real `messages.create` calls succeeded for Director / Screenwriter / Storyboard — no mock fallback. Auth, the `claude-sonnet-4-6` model alias, and response parsing all good.
- Output is genuine + on-theme (Director: *"A terminal screen in a dark room, timestamp 21:14… the faint mechanical exhale…"*; music mood: *"a single cello note that arrives only at Pass 306 and grows… the way a room changes when someone enters it who was expected home."*).
- Real storyboard produced 6 frames (vs 1 mock) → all 6 rendered to a 150s/1080p .mp4.
- **#8 token capture works** per role (director 674/873, screenplay 648/368, storyboard 939/1034 in/out).

**⚠ Minor gap:** the per-role tokens are captured but the `total_cost` rollup is `None` — the data is there, the aggregation isn't wired. Easy follow-up.

**Still UNVERIFIED — needs the 4 media keys + real $:** #4 media APIs (Runway/Replicate/ElevenLabs/Suno), #9 delivery channels firing. That code has still never run.

**Bottom line:** with a correct Anthropic key, the thinking half works for real. The media-generation half is written but unproven — that's the next (more expensive) test.

---

## PRODUCTION MEDIA TEST — real Replicate generation (2026-06-11, claude_b)

Funded with $5 of Replicate credit. Tested the real media-generation path.

**✅ Image generation WORKS** — `apis/image_api.py` unchanged. Generated a real 1344×768 WebP via flux-schnell. (My suspected version-slug bug was wrong — the slug works.) Note: `replicate.delivery` URLs expire fast; must download immediately.

**✅ Video generation WORKS** — after fixes to `apis/video_api.py`:
- added a **Replicate provider** (was Runway-only) so ONE Replicate key drives image + video (no Runway needed)
- resolve `owner/name` slug → latest **version hash** (community models need the hash, not the slug or model-endpoint)
- default model `minimax/video-01` was **broken on Replicate's side** (its hosted backend returned `account_deactivated`); switched default to **`lightricks/ltx-video`** — reliable (172k runs), fast (~21s), cheap.
- Result: real H.264 MP4, 768×512, 3.88s.
- `config.yaml` video section now points at Replicate.

**⚠ STILL UNTESTED:** voice (ElevenLabs — has a free tier) and music (Suno — natively takes stablecoin). Need their own keys.

**🚧 THE REAL REMAINING GAP — the editor doesn't assemble the generated media.** `editor.py::_assemble_real` (the production path) is a stub: its own comment says "collect real media paths if present, else fallback to placeholder" — but it never collects; it just calls `_render_placeholder_clips`, the SAME color-card-with-text renderer as dry-run. So **even in production you get a real .mp4, but it's placeholder color cards, NOT the real Replicate images/video.** Generation works; assembly-from-real-media is not implemented.

**Bottom line:** the brain works (Anthropic), and image + video generation work (Replicate, one key). The piece that turns "generates media" into "makes a film" — downloading the assets and stitching them with the voiceover/music — is the next real build.
