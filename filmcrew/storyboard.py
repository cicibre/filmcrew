from filmcrew.base import BaseCrewMember
from apis.llm_api import LLMClient


class Storyboard(BaseCrewMember):
    role = "storyboard"

    def work(self, job, manifest):
        llm = LLMClient(self.config)
        plan = manifest.get("director_plan", {})
        screenplay = manifest.get("screenplay", {})

        system = (
            "You are a storyboard artist. "
            "For each beat, describe one vivid visual image and camera treatment. "
            "Return numbered frames with: shot description, text-to-image prompt, duration, style."
        )
        user_prompt = self._prompt(job, plan, screenplay)
        result = llm.call(system, user_prompt)

        content = result["content"]
        if not isinstance(content, str):
            content = str(content)

        manifest["storyboard"] = {
            "mode": self.mode,
            "frames": self._parse_frames(content),
            "style_notes": plan.get("visual_style", "clean, documentary"),
        }
        return manifest

    def _prompt(self, job, plan, screenplay):
        return (
            f"Create a storyboard for this ROVA film:\n\n"
            f"Title: {job.get('title')}\n"
            f"Duration: {job.get('duration_seconds')}s\n"
            f"Visual style: {plan.get('visual_style', 'clean, documentary')}\n"
            f"Voiceover: {screenplay.get('voiceover', '[no script yet]')[:300]}...\n\n"
            "For each of 5-8 frames, provide:\n"
            "- Frame number\n"
            "- Shot description (what is on screen)\n"
            "- Text-to-image prompt (detailed, prompt-engineered)\n"
            "- Duration in seconds\n"
            "- Visual style note\n"
        )

    def _parse_frames(self, content):
        frames = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            if line[0].isdigit() or line.lower().startswith("frame"):
                frames.append({"raw": line, "duration": 3})
            elif line.lower().startswith("shot"):
                if frames:
                    frames[-1]["shot"] = line.split(":", 1)[-1].strip()
            elif line.lower().startswith("prompt"):
                if frames:
                    frames[-1]["prompt"] = line.split(":", 1)[-1].strip()
        if not frames:
            frames = [{"raw": content[:200], "duration": 3}]
        return frames
