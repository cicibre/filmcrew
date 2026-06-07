from filmcrew.base import BaseCrewMember
from apis.llm_api import LLMClient


class Director(BaseCrewMember):
    role = "director"

    def work(self, job, manifest):
        llm = LLMClient(self.config)

        system = (
            "You are a documentary film director. "
            "You create concise, visual, specific creative plans. "
            "Output plain text: opening shot, 3-5 key beats, closing shot, music mood, visual style."
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
            "music_mood": self._extract_music_mood(content),
            "visual_style": self._extract_visual_style(content),
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
            "Provide:\n"
            "1. Opening shot description\n"
            "2. 3-5 key beats\n"
            "3. Closing shot\n"
            "4. Suggested music mood\n"
            "5. Visual style notes\n"
        )

    def _extract_music_mood(self, text):
        if "music mood:" in text.lower():
            for line in text.splitlines():
                if "music mood:" in line.lower():
                    return line.split(":", 1)[-1].strip()
        return "ambient, understated"

    def _extract_visual_style(self, text):
        if "visual style" in text.lower():
            for line in text.splitlines():
                if "visual style" in line.lower():
                    return line.split(":", 1)[-1].strip()
        return "clean, documentary"
