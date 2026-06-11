"""Text-to-speech via ElevenLabs API.

Docs: https://elevenlabs.io/docs/api-reference/text-to-speech
Endpoint: POST /v1/text-to-speech/{voice_id}
Auth: xi-api-key header
"""
import requests


class VoiceAPI:
    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self, config):
        self.config = config.get("voice", {})
        self.mode = config.get("general", {}).get("mode", "dry_run")
        self.api_key = self.config.get("api_key", "")
        self.default_voice_id = self.config.get("default_voice_id", "")
        self.cost_per_character = self.config.get("cost_per_character_usd", 0.00003)

    def generate(self, text, voice_id="default", **kwargs):
        if self.mode != "production":
            return self._mock(text, voice_id, **kwargs)
        return self._real(text, voice_id, **kwargs)

    def _mock(self, text, voice_id, **kwargs):
        char_count = len(text) if text else 0
        cost = self.cost_per_character * char_count
        return {
            "mode": "dry_run",
            "type": "voice",
            "text_preview": text[:80] if text else "",
            "voice_id": voice_id,
            "path": "[PLACEHOLDER] voice audio would be generated here",
            "cost_estimate_usd": round(cost, 4),
        }

    def _real(self, text, voice_id, **kwargs):
        if not self.api_key:
            # Graceful degradation: no key -> skip narration (silent) rather than
            # failing the whole production. (2026-06-11, claude_b.)
            import warnings
            warnings.warn(
                "ElevenLabs key not configured — voiceover skipped (silent). "
                "Add voice.api_key for narration.", RuntimeWarning, stacklevel=2)
            return self._mock(text, voice_id, **kwargs)

        voice_id = voice_id if voice_id != "default" else self.default_voice_id
        if not voice_id:
            raise RuntimeError("No voice_id provided and no default_voice_id configured.")

        headers = {"xi-api-key": self.api_key, "Content-Type": "application/json"}
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }

        resp = requests.post(
            f"{self.BASE_URL}/text-to-speech/{voice_id}",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()

        ext = kwargs.get("output_format", "mp3")
        path = kwargs.get("output_path", f"outputs/films/_voice_{voice_id}.{ext}")
        with open(path, "wb") as f:
            f.write(resp.content)

        cost = self.cost_per_character * len(text)
        return {
            "mode": "production",
            "type": "voice",
            "text_preview": text[:80] if text else "",
            "voice_id": voice_id,
            "path": path,
            "cost_estimate_usd": round(cost, 4),
        }
