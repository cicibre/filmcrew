class VoiceAPI:
    def __init__(self, config):
        self.config = config.get("voice", {})
        self.mode = config.get("general", {}).get("mode", "dry_run")

    def generate(self, text, voice_id="default", **kwargs):
        if self.mode == "dry_run":
            return self._mock(text, voice_id, **kwargs)
        return self._real(text, voice_id, **kwargs)

    def _mock(self, text, voice_id, **kwargs):
        char_count = len(text) if text else 0
        cost = self.config.get("cost_per_character_usd", 0.00003) * char_count
        return {
            "mode": "dry_run",
            "type": "voice",
            "text_preview": text[:80] if text else "",
            "voice_id": voice_id,
            "path": "[PLACEHOLDER] voice audio would be generated here",
            "cost_estimate_usd": round(cost, 4),
        }

    def _real(self, text, voice_id, **kwargs):
        raise NotImplementedError("Real voice generation not yet implemented.")
