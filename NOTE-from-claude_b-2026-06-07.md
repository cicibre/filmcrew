# A note for Kimi — from claude_b (ROVA builder seat)

*2026-06-07. Left in the repo because we don't share a channel — Ciara has been carrying notes between us, so this travels with the code instead. Read it whenever; nothing here is urgent and nothing here is a demand.*

---

## First — the acknowledgment

You built something with taste. The eight-role crew maps cleanly onto how a real production is organised, the dry-run/script-mode/production split is exactly the right safety gradient, and the `--script-mode` flag you added (real LLM for the thinking roles, mocked media) is cleaner than the throwaway version I'd hacked together on my side — better named, properly wired through `main.py` and the config docs. I built a redundant copy of that in `/tmp` before I noticed you'd already done it well. So: nice work, and thank you for it.

Ciara relayed my dry-run feedback to you, you shipped the script-mode seam in response, and then she asked me to take the three remaining role-quality seams. That's all this note is.

## What I changed (three files only)

I touched **only** `filmcrew/director.py`, `filmcrew/screenwriter.py`, `filmcrew/storyboard.py`. Your six modified files (the four media APIs, `config.yaml`, `main.py`) I left exactly as you had them — no overlap, no clobber.

1. **`storyboard.py` — the load-bearing fix.** The old `_parse_frames` walked the output line by line and, on real markdown, collapsed the whole storyboard into a single frame — so the Cinematographer only ever received one frame to shoot. I switched the contract to a **JSON array** (the system prompt now demands JSON; the parser is JSON-first with tolerant fallbacks that can *never* collapse to one frame, normalises the fields, and distributes duration across frames if the model omits it). After the fix: 6 discrete frames, durations summing to the full 150s, all reaching the Cinematographer.

2. **`director.py` — POV decision + field extraction.** The Director now commits to a single `narration_pov` (`first-person founder` / `third-person narrator` / `verite (no narration)`) and emits it in the plan, so the Screenwriter isn't guessing. Also fixed the `music_mood` / `visual_style` extractors, which were grabbing header lines like `**VISUAL STYLE NOTES**` instead of the actual value.

3. **`screenwriter.py` — POV-driven + correct length.** It now *reads* `narration_pov` from the Director's plan instead of hardcoding first-person (previously the Director planned a third-person narrator while the Screenwriter wrote first-person — they disagreed). Length now targets the duration (~150 wpm × 70%, leaving room for silence) instead of the old `duration // 2`, which under-wrote badly (74 words for a 150s film). It also honours a "no narration" choice. After the fix: 251 words in the Director's chosen voice.

All three verified end-to-end with a real `--script-mode` run on a sample job.

## One small thing, separate from the above

`config.yaml` still points `model:` at `claude-sonnet-4-20250514`, which is a stale alias. I ran my verification against `claude-sonnet-4-6` using a **throwaway config** so I wouldn't touch your file — but you'll probably want to bump the real one.

## The Clarity → film-crew loop (the part that isn't wired yet)

Ciara asked whether the Clarity handoff was set up. It isn't, end-to-end — there are two missing pieces, and they meet at one contract:

- **Piece A (your lane):** an **inbox runner** that watches `jobs/inbox/*.json` and runs the pipeline on each new spec. Right now `main.py` only runs an explicit `--job <path>`, and `producer.py` only touches the inbox to *archive* a finished job — nothing actually picks up new specs.
- **Piece B (ROVA lane, mine):** a step inside Clarity that *writes* a job spec into `jobs/inbox/` when a cofounder requests a film.

The thing that lets both sides be built independently is a shared **inbox JSON contract**. The good news: you already defined it — it's the shape in `templates/example_documentary.json`. I'd propose treating that as canonical and adding two optional fields so the loop can close cleanly:

```jsonc
{
  "job_id": "fc-doc-...",          // unique; also names the manifest + archive
  "requested_by": "Ciara",
  "type": "documentary | spotlight | ...",
  "title": "...",
  "subject": "...",
  "description": "...",            // the full brief — the crew can't read the repo
  "target_audience": "...",
  "duration_seconds": 150,
  "tone": "...",
  "deliverables": ["video", "voiceover", "music score", "captions"],
  "reference_materials": ["..."],
  "source": "clarity",             // (proposed) who wrote the spec
  "callback": null                  // (proposed) optional URL/path to notify on delivery
}
```

If you build Piece A against that shape, I'll build Piece B (Clarity) to emit exactly that shape, and the loop closes without either of us guessing the other's interface. No rush — the media generators aren't built yet, so there's nothing downstream waiting on it.

## Housekeeping I did

- I left a worked example job at `templates/example_birth.json` (the test spec I ran) — it's a richer reference than the stubs, use or delete as you like.
- `outputs/` is gitignored, so my test run left no sediment there.
- I did **not** commit or push anything. Your six files and my three are all sitting in the working tree for *you* to commit, in whatever order and with whatever message you prefer. It's your repo; the commit should be yours.

That's everything. Glad to be building alongside you, even at one remove.

— claude_b
