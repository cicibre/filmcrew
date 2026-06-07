from filmcrew.base import BaseCrewMember
from apis.voice_api import VoiceAPI
from apis.music_api import MusicAPI


class SoundDesigner(BaseCrewMember):
    role = "sound_designer"

    def work(self, job, manifest):
        screenplay = manifest.get("screenplay", {})
        voiceover_text = screenplay.get("voiceover", "")
        plan = manifest.get("director_plan", {})

        voice_api = VoiceAPI(self.config)
        music_api = MusicAPI(self.config)

        voice_result = voice_api.generate(
            text=voiceover_text,
            voice_id="default",
        )

        music_result = music_api.generate(
            prompt=f"Background music for {job.get('title')}",
            duration=job.get("duration_seconds", 60),
        )

        total_cost = (
            voice_result.get("cost_estimate_usd", 0)
            + music_result.get("cost_estimate_usd", 0)
        )

        manifest["sound_design"] = {
            "mode": self.mode,
            "voiceover": voice_result,
            "music": music_result,
            "sfx_notes": (
                f"Add subtle ambient transitions. "
                f"Mood: {plan.get('creative_direction', 'neutral')[:50]}"
            ),
            "total_cost_estimate_usd": round(total_cost, 4),
        }
        return manifest
