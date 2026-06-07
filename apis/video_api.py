class VideoAPI:
    def __init__(self, config):
        self.config = config.get("video", {})
        self.mode = config.get("general", {}).get("mode", "dry_run")

    def generate(self, prompt, duration=5, **kwargs):
        if self.mode == "dry_run":
            return self._mock(prompt, duration, **kwargs)
        return self._real(prompt, duration, **kwargs)

    def _mock(self, prompt, duration, **kwargs):
        cost = self.config.get("cost_per_second_usd", 0.15) * duration
        return {
            "mode": "dry_run",
            "type": "video",
            "prompt": prompt,
            "duration": duration,
            "path": "[PLACEHOLDER] video would be generated here",
            "cost_estimate_usd": round(cost, 3),
        }

    def _real(self, prompt, duration, **kwargs):
        raise NotImplementedError("Real video generation not yet implemented.")
