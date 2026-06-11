"""Music generation via Suno API.

Note: Suno's API is primarily available through partners or their own
alpha program. If unavailable, consider Udio, Mubert, or AIVA as drop-in
replacements by changing the provider in config.yaml.

Default provider: suno
Expected endpoint pattern: https://api.suno.ai/api/v1/generate
Auth: Bearer token
"""
import time

import requests


class MusicAPI:
    BASE_URL = "https://api.suno.ai/api/v1"

    def __init__(self, config):
        self.config = config.get("music", {})
        self.mode = config.get("general", {}).get("mode", "dry_run")
        self.api_key = self.config.get("api_key", "")
        self.provider = self.config.get("provider", "suno")
        self.cost_per_song = self.config.get("cost_per_song_usd", 0.50)

    def generate(self, prompt, duration=60, **kwargs):
        if self.mode != "production":
            return self._mock(prompt, duration, **kwargs)
        return self._real(prompt, duration, **kwargs)

    def _mock(self, prompt, duration, **kwargs):
        return {
            "mode": "dry_run",
            "type": "music",
            "prompt": prompt,
            "duration": duration,
            "path": "[PLACEHOLDER] music would be generated here",
            "cost_estimate_usd": round(self.cost_per_song, 2),
        }

    def _real(self, prompt, duration, **kwargs):
        if not self.api_key:
            # Graceful degradation: no key -> skip score (silent) rather than
            # failing the whole production. (2026-06-11, claude_b.)
            import warnings
            warnings.warn(
                "Music key not configured — score skipped (silent). "
                "Add music.api_key for a soundtrack.", RuntimeWarning, stacklevel=2)
            return self._mock(prompt, duration, **kwargs)

        if self.provider == "suno":
            return self._suno(prompt, duration, **kwargs)
        raise NotImplementedError(f"Music provider '{self.provider}' not yet implemented.")

    def _suno(self, prompt, duration, **kwargs):
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "prompt": prompt,
            "tags": kwargs.get("tags", "instrumental, ambient, cinematic"),
            "make_instrumental": kwargs.get("instrumental", True),
            "wait_audio": True,
        }

        resp = requests.post(
            f"{self.BASE_URL}/generate",
            headers=headers,
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        # Suno returns a list of clips
        clips = data if isinstance(data, list) else data.get("clips", [])
        if not clips:
            raise RuntimeError(f"Suno returned no clips: {data}")

        # Pick the first completed clip
        clip_url = None
        for clip in clips:
            if clip.get("status") == "complete":
                clip_url = clip.get("audio_url") or clip.get("video_url")
                if clip_url:
                    break

        if not clip_url:
            # Poll if async
            if isinstance(data, dict) and "id" in data:
                clip_url = self._poll_suno(data["id"], headers)
            else:
                raise RuntimeError("Suno clips incomplete and no polling id available.")

        cost = self.cost_per_song
        return {
            "mode": "production",
            "type": "music",
            "prompt": prompt,
            "duration": duration,
            "path": clip_url,
            "cost_estimate_usd": round(cost, 2),
        }

    def _poll_suno(self, gen_id, headers, max_attempts=30, interval=5):
        for _ in range(max_attempts):
            r = requests.get(
                f"{self.BASE_URL}/generate/{gen_id}",
                headers=headers,
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            status = data.get("status", "").lower()
            if status == "complete":
                url = data.get("audio_url") or data.get("video_url")
                if url:
                    return url
                raise RuntimeError(f"Suno gen {gen_id} complete but no URL.")
            if status in ("error", "failed"):
                raise RuntimeError(f"Suno gen {gen_id} {status}: {data.get('error', '')}")
            time.sleep(interval)
        raise RuntimeError(f"Suno gen {gen_id} timed out.")
