from filmcrew.base import BaseCrewMember
from apis.llm_api import LLMClient


class Screenwriter(BaseCrewMember):
    role = "screenwriter"

    def work(self, job, manifest):
        llm = LLMClient(self.config)
        plan = manifest.get("director_plan", {})
        pov = plan.get("narration_pov", "third-person narrator")

        # honour a director who chose no narration
        if "verite" in pov.lower() or "vérité" in pov.lower() or "no narration" in pov.lower():
            manifest["screenplay"] = {
                "mode": self.mode,
                "voiceover": "",
                "narration_pov": pov,
                "word_count_approx": 0,
                "estimated_duration_seconds": 0,
                "note": "Director chose verite — no voiceover written.",
            }
            return manifest

        system = (
            "You are a documentary screenwriter. Write tight, human voiceover copy "
            f"in this point of view: {pov}. Match the director's tone exactly. "
            "Leave room for silence — do not over-write. "
            "Return ONLY the voiceover script. No scene descriptions, no headers."
        )
        user_prompt = self._prompt(job, plan, pov)
        result = llm.call(system, user_prompt)

        content = result["content"]
        if not isinstance(content, str):
            content = str(content)

        words = content.split()
        manifest["screenplay"] = {
            "mode": self.mode,
            "voiceover": content,
            "narration_pov": pov,
            "word_count_approx": len(words),
            "estimated_duration_seconds": self._estimate_duration(content),
            "tokens": result.get("usage", {}),
        }
        return manifest

    def _prompt(self, job, plan, pov):
        duration = job.get("duration_seconds", 60)
        # ~150 wpm narration; assume ~70% of runtime carries voice, rest is silence/image
        target_words = int(duration / 60 * 150 * 0.7)
        speaking_s = int(duration * 0.7)
        return (
            f"Write the voiceover narration for this ROVA film.\n\n"
            f"Title: {job.get('title')}\n"
            f"Total film duration: {duration}s\n"
            f"Narration point of view: {pov}\n"
            f"Tone: {job.get('tone')}\n\n"
            f"Director's creative direction:\n"
            f"{plan.get('creative_direction', '[no director plan]')[:1500]}\n\n"
            f"Write approximately {target_words} words — that fills about {speaking_s}s of "
            f"narration at a documentary pace, leaving the rest of the {duration}s for "
            f"silence and image. Stay in the chosen point of view throughout. Be specific "
            f"and grounded; earn emotion through detail, never through hype.\n\n"
            "Return ONLY the voiceover script."
        )

    def _estimate_duration(self, text):
        if not text or not isinstance(text, str):
            return 0
        words = len(text.split())
        # ~150 words per minute for narration
        return int(words / 150 * 60)
