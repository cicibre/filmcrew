import json
import re

from filmcrew.base import BaseCrewMember
from apis.llm_api import LLMClient


class Storyboard(BaseCrewMember):
    role = "storyboard"

    def work(self, job, manifest):
        llm = LLMClient(self.config)
        plan = manifest.get("director_plan", {})
        screenplay = manifest.get("screenplay", {})

        system = (
            "You are a storyboard artist. Break the film into 5-8 discrete frames. "
            "For each frame give one vivid on-screen image, a detailed text-to-image "
            "prompt, a duration in seconds, and a short style note. "
            "Return ONLY a JSON array — no prose, no markdown fences. Each element is "
            'an object: {"shot": str, "prompt": str, "duration": int, "style": str}. '
            "The durations should sum to roughly the film's total duration."
        )
        user_prompt = self._prompt(job, plan, screenplay)
        result = llm.call(system, user_prompt)

        content = result["content"]
        if not isinstance(content, str):
            content = str(content)

        manifest["storyboard"] = {
            "mode": self.mode,
            "frames": self._parse_frames(content, job),
            "style_notes": plan.get("visual_style", "clean, documentary"),
            "tokens": result.get("usage", {}),
        }
        return manifest

    def _prompt(self, job, plan, screenplay):
        return (
            f"Create the storyboard for this ROVA film as a JSON array.\n\n"
            f"Title: {job.get('title')}\n"
            f"Total duration: {job.get('duration_seconds')}s\n"
            f"Visual style: {plan.get('visual_style', 'clean, documentary')}\n"
            f"Creative direction:\n{plan.get('creative_direction', '')[:1500]}\n\n"
            f"Voiceover script:\n{screenplay.get('voiceover', '[no script yet]')[:1200]}\n\n"
            "Produce 5-8 frames covering the whole film. "
            "Return ONLY the JSON array described in your instructions."
        )

    # ------------------------------------------------------------------
    # parsing — JSON-first, with tolerant fallbacks that never collapse
    # the whole storyboard into a single frame (the old failure mode).
    # ------------------------------------------------------------------
    def _parse_frames(self, content, job=None):
        frames = self._try_json(content) or self._fallback_split(content)

        clean = []
        for i, fr in enumerate(frames, 1):
            if not isinstance(fr, dict):
                fr = {"shot": str(fr)}
            shot = fr.get("shot") or fr.get("description") or fr.get("raw") or ""
            prompt = fr.get("prompt") or fr.get("image_prompt") or shot
            try:
                dur = int(fr.get("duration", 0)) or 0
            except (TypeError, ValueError):
                dur = 0
            clean.append({
                "frame": i,
                "shot": shot,
                "prompt": prompt,
                "duration": dur,
                "style": fr.get("style", ""),
            })

        # if the model gave no/zero durations, distribute the film length evenly
        total = job.get("duration_seconds") if job else None
        if clean and total and sum(f["duration"] for f in clean) == 0:
            each = max(1, int(total / len(clean)))
            for f in clean:
                f["duration"] = each
        return clean

    @staticmethod
    def _try_json(content):
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text).strip()
        if not text.startswith("["):
            start, end = text.find("["), text.rfind("]")
            if start != -1 and end > start:
                text = text[start:end + 1]
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("frames"), list):
            return data["frames"]
        return None

    @staticmethod
    def _fallback_split(content):
        # split on "Frame N" headers (markdown or plain)
        blocks = re.split(r"(?im)^\s*(?:#+\s*)?(?:\*\*)?frame\s*\d+\b", content)
        blocks = [b.strip() for b in blocks if b.strip()]
        if len(blocks) <= 1:
            # otherwise split on numbered list items
            blocks = re.split(r"(?m)^\s*\d+[\.\)]\s+", content)
            blocks = [b.strip() for b in blocks if b.strip()]
        return [{"shot": b[:400], "prompt": b[:400]} for b in blocks] or [{"shot": content[:400]}]
