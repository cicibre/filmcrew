# ROVA Film Crew

> An AI agent film crew that documents and showcases ROVA — hovering alongside, ready when needed, independent when not.

## What This Is

A standalone Python project that autonomously produces AI-generated documentary and showcase video for [ROVA](https://github.com/cicibre/rova) (and by extension, the Heard ecosystem). Cofounders request films through **Clarity** (ROVA's strategy agent); Clarity hands off a formal job spec; the crew produces the finished film end-to-end with minimal human intervention.

## Architecture

```
User / Cofounder → Clarity (:5010) → jobs/inbox/*.json → Film Crew Pipeline → outputs/films/*.mp4
```

### The Crew

| Role | Module | Responsibility |
|------|--------|----------------|
| **Producer** | `producer.py` | Job intake, budget tracking, pipeline orchestration, delivery |
| **Director** | `director.py` | Creative vision, shot plan, cast assembly, tone guide |
| **Screenwriter** | `screenwriter.py` | Script, voiceover text, dialogue |
| **Storyboard Artist** | `storyboard.py` | Scene descriptions, visual prompts, frame sequencing |
| **Cinematographer** | `cinematographer.py` | Video/image generation via AI APIs |
| **Sound Designer** | `sound_designer.py` | Voice, music, and SFX generation |
| **Editor** | `editor.py` | Assembly, transitions, timing — ffmpeg-powered |
| **Archivist** | `archivist.py` | Media library, metadata, searchable history |

### Data Flow

```
Producer picks up job → Director plans → Screenwriter writes → Storyboard draws →
Cinematographer shoots → Sound Designer scores → Editor cuts → Producer delivers
```

## Quick Start

### 1. Install

```bash
cd /Users/cc/filmcrew
pip install -r requirements.txt
```

### 2. Configure

Edit `config.yaml`:

- Set `general.mode` to `dry_run` (default — no API calls, generates prompts/plans only)
- Add API keys when ready for real production:
  - `llm.api_key` — Anthropic (for scripting)
  - `video.api_key` — Runway or Kling
  - `image.api_key` — FLUX or Midjourney
  - `voice.api_key` — ElevenLabs
  - `music.api_key` — Suno or Udio

### 3. Run Dry-Run Demo

```bash
python main.py --dry-run --job templates/example_spotlight.json
```

This generates a full manifest (`outputs/manifests/`) showing what the crew *would* produce — without spending a single API credit.

### 4. Run Real Production

```bash
python main.py --job jobs/inbox/fc-spotlight-breakbot-001.json
```

This runs the full pipeline and delivers the finished film to `outputs/films/`.

## Clarity Handoff

Clarity writes job specs as JSON to `jobs/inbox/`. The Producer polls this directory (or responds to a filesystem event) and starts the pipeline.

### Job Spec Format

```json
{
  "job_id": "fc-spotlight-breakbot-001",
  "requested_by": "Ciara",
  "type": "agent_spotlight",
  "title": "Meet Breakbot",
  "subject": "Breakbot (port 5014)",
  "description": "A 60-second showcase video...",
  "target_audience": "builders evaluating AI agent infrastructure",
  "duration_seconds": 60,
  "tone": "sharp, slightly irreverent",
  "deliverables": ["video", "captions"],
  "reference_materials": ["AGENTS.md", "BREAKBOT_SPEC.md"]
}
```

## Modes

### Dry Run (default)
- No API calls
- Generates full prompts, scripts, shot lists
- Outputs `manifest.json` + metadata
- Use for: development, review, cost estimation

### Production
- Real API calls for video, images, voice, music
- Assembles final `.mp4` with ffmpeg
- Outputs finished film to `outputs/films/`
- Use for: actual deliverables

## Cofounder Workflow

```
1. You tell Clarity: "We need a film about X"
2. Clarity strategizes and writes a job spec
3. Film Crew picks it up automatically
4. [Optional] Review gates pause at key steps
5. Finished film appears in outputs/films/
6. Film is delivered to your configured inbox
```

## Review Gates

Set in `config.yaml`. When enabled, the pipeline pauses after key steps for human approval:

- `director_plan` — review the Director's plan
- `screenwriter_script` — review the script
- `storyboard_frames` — review the storyboard
- `final_cut` — review before delivery

Set all to `false` for fully automated mode.

## API Cost Estimation

The Producer tracks estimated costs per job before production begins. Rough benchmarks:

| Service | Cost | Unit |
|---------|------|------|
| Video (Runway) | ~$0.15 | per second |
| Image (FLUX) | ~$0.02 | per image |
| Voice (ElevenLabs) | ~$0.00003 | per character |
| Music (Suno) | ~$0.50 | per song |

Add keys in `config.yaml` to enable real cost tracking.
