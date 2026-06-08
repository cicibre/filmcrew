class MusicAPI:
    def __init__(self, config):
        self.config = config.get("music", {})
        self.mode = config.get("general", {}).get("mode", "dry_run")

    def generate(self, prompt, duration=60, **kwargs):
        if self.mode == "production":
            return self._real(prompt, duration, **kwargs)
        return self._mock(prompt, duration, **kwargs)

    def _mock(self, prompt, duration, **kwargs):
        cost = self.config.get("cost_per_song_usd", 0.50)
        return {
            "mode": "dry_run",
            "type": "music",
            "prompt": prompt,
            "duration": duration,
            "path": "[PLACEHOLDER] music would be generated here",
            "cost_estimate_usd": round(cost, 2),
        }

    def _real(self, prompt, duration, **kwargs):
        raise NotImplementedError("Real music generation not yet implemented.")
