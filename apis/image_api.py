class ImageAPI:
    def __init__(self, config):
        self.config = config.get("image", {})
        self.mode = config.get("general", {}).get("mode", "dry_run")

    def generate(self, prompt, **kwargs):
        if self.mode == "production":
            return self._real(prompt, **kwargs)
        return self._mock(prompt, **kwargs)

    def _mock(self, prompt, **kwargs):
        cost = self.config.get("cost_per_image_usd", 0.02)
        return {
            "mode": "dry_run",
            "type": "image",
            "prompt": prompt,
            "path": "[PLACEHOLDER] image would be generated here",
            "cost_estimate_usd": round(cost, 3),
        }

    def _real(self, prompt, **kwargs):
        raise NotImplementedError("Real image generation not yet implemented.")
