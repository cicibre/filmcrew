from filmcrew.base import BaseCrewMember
from apis.llm_api import LLMClient


class Director(BaseCrewMember):
    role = "director"

    def work(self, job, manifest):
        llm = LLMClient(self.config)

        system = (
            "You are a documentary film director. "
            "You create concise, visual, specific creative plans. "
            "Output plain text with clearly labelled sections: Opening shot, "
            "Key beats (3-5), Closing shot, Narration POV, Music mood, Visual style. "
            "You MUST commit to one Narration POV and state it on its own line as "
            "'Narration POV: <first-person founder | third-person narrator | "
            "verite (no narration)>' — this single decision governs the screenwriter."
        )
        user_prompt = self._prompt(job)
        result = llm.call(system, user_prompt)

        content = result["content"]
        if not isinstance(content, str):
            content = str(content)

        manifest["director_plan"] = {
            "mode": self.mode,
            "creative_direction": content,
            "estimated_shots": 5,
            "narration_pov": self._extract_pov(content),
            "music_mood": self._extract_field(content, "music mood", "ambient, understated"),
            "visual_style": self._extract_field(content, "visual style", "clean, documentary"),
            "tokens": result.get("usage", {}),
        }
        return manifest

    def _prompt(self, job):
        return (
            f"Create a creative plan for this ROVA film:\n\n"
            f"Job: {job.get('title')}\n"
            f"Type: {job.get('type')}\n"
            f"Duration: {job.get('duration_seconds')}s\n"
            f"Subject: {job.get('subject')}\n"
            f"Tone: {job.get('tone')}\n"
            f"Audience: {job.get('target_audience')}\n"
            f"Description: {job.get('description')}\n\n"
            "Provide, each clearly labelled:\n"
            "1. Opening shot description\n"
            "2. 3-5 key beats\n"
            "3. Closing shot\n"
            "4. Narration POV — choose ONE and commit (this governs the screenwriter). "
            "Write it on its own line as exactly one of:\n"
            "   'Narration POV: first-person founder'\n"
            "   'Narration POV: third-person narrator'\n"
            "   'Narration POV: verite (no narration)'\n"
            "5. Music mood — one line starting 'Music mood: ...'\n"
            "6. Visual style — one line starting 'Visual style: ...'\n"
        )

    def _extract_pov(self, text):
        for line in text.splitlines():
            if "narration pov" in line.lower():
                val = line.split(":", 1)[-1].strip().strip("*").strip()
                if val:
                    return val
        low = text.lower()
        if "verite" in low or "vérité" in low or "no narration" in low:
            return "verite (no narration)"
        if "first-person" in low or "first person" in low:
            return "first-person founder"
        return "third-person narrator"

    def _extract_field(self, text, label, default):
        """Return the value after 'label:' — only when an actual value follows,
        so header-only lines like '**Visual style**' don't get mistaken for the value."""
        for line in text.splitlines():
            if label in line.lower() and ":" in line:
                val = line.split(":", 1)[-1].strip().strip("*").strip()
                if val:
                    return val
        return default
