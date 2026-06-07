from filmcrew.base import BaseCrewMember
from apis.llm_api import LLMClient


class Screenwriter(BaseCrewMember):
    role = "screenwriter"

    def work(self, job, manifest):
        llm = LLMClient(self.config)
        plan = manifest.get("director_plan", {})

        system = (
            "You are a documentary screenwriter. "
            "Write tight, human voiceover copy. First-person founder voice. "
            "Return ONLY the voiceover script. No scene descriptions."
        )
        user_prompt = self._prompt(job, plan)
        result = llm.call(system, user_prompt)

        content = result["content"]
        if not isinstance(content, str):
            content = str(content)

        words = content.split()
        manifest["screenplay"] = {
            "mode": self.mode,
            "voiceover": content,
            "word_count_approx": len(words),
            "estimated_duration_seconds": self._estimate_duration(content),
        }
        return manifest

    def _prompt(self, job, plan):
        duration = job.get("duration_seconds", 60)
        target_words = max(30, duration // 2)
        return (
            f"Write voiceover narration for this ROVA film:\n\n"
            f"Title: {job.get('title')}\n"
            f"Duration: {duration}s\n"
            f"Tone: {job.get('tone')}\n"
            f"Creative direction: {plan.get('creative_direction', '[no director plan yet]')[:400]}\n\n"
            f"Write in first-person founder voice (confident, grounded, specific). "
            f"Keep it under {target_words} words so it breathes. \n\n"
            "Return ONLY the voiceover script."
        )

    def _estimate_duration(self, text):
        if not text or not isinstance(text, str):
            return 0
        words = len(text.split())
        # ~150 words per minute for narration
        return int(words / 150 * 60)
