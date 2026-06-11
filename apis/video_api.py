"""Video generation via Runway ML API.

Docs: https://docs.runwayml.com/reference/imageToVideo
Generative video: POST /v1/generations with promptImage + promptText.
Large previews: GET /v1/generations/{id} and poll until status == SUCCEEDED.
"""
import time
from pathlib import Path

import requests


class VideoAPI:
    BASE_URL = "https://api.runwayml.com"

    def __init__(self, config):
        self.config = config.get("video", {})
        self.mode = config.get("general", {}).get("mode", "dry_run")
        self.api_key = self.config.get("api_key", "")
        self.provider = self.config.get("provider", "runway")
        self.cost_per_second = self.config.get("cost_per_second_usd", 0.15)

    def generate(self, prompt, duration=5, image_path=None, **kwargs):
        if self.mode != "production":
            return self._mock(prompt, duration, **kwargs)
        return self._real(prompt, duration, image_path, **kwargs)

    def _mock(self, prompt, duration, **kwargs):
        cost = self.cost_per_second * duration
        return {
            "mode": "dry_run",
            "type": "video",
            "prompt": prompt,
            "duration": duration,
            "path": "[PLACEHOLDER] video would be generated here",
            "cost_estimate_usd": round(cost, 3),
        }

    def _real(self, prompt, duration, image_path, **kwargs):
        if not self.api_key:
            raise RuntimeError("Video API key not configured. Add video.api_key to config.yaml.")

        # Replicate hosts video models (minimax/video-01, etc.) on the SAME
        # predictions API the image path uses — one key drives image + video.
        # (Added 2026-06-11, claude_b.)
        if self.provider == "replicate":
            return self._replicate(prompt, duration, image_path, **kwargs)

        # --- Runway (default) ---
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        payload = {
            "taskType": "gen3",
            "promptText": prompt,
            "duration": min(duration, 10),  # Runway Gen3 supports up to 10s
        }

        if image_path and Path(image_path).is_file():
            # Upload image or provide URL
            # For simplicity, we assume the image is already accessible via URL
            # In production, you'd upload it first
            pass  # TODO: image upload

        resp = requests.post(
            f"{self.BASE_URL}/v1/generations",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        gen_id = data.get("id")
        if not gen_id:
            raise RuntimeError(f"Runway returned no generation id: {data}")

        # Poll for completion
        video_url = self._poll_generation(gen_id, headers)
        cost = self.cost_per_second * duration
        return {
            "mode": "production",
            "type": "video",
            "prompt": prompt,
            "duration": duration,
            "path": video_url,
            "cost_estimate_usd": round(cost, 3),
        }

    def _replicate(self, prompt, duration, image_path=None, **kwargs):
        # Default to a reliable, cheap text-to-video model. (minimax/video-01 was
        # the original pick but its hosted backend was returning account_deactivated
        # on Replicate — pick a working model, keep it configurable. 2026-06-11.)
        model = self.config.get("model", "lightricks/ltx-video")
        headers = {"Authorization": f"Token {self.api_key}", "Content-Type": "application/json"}
        version = model
        if "/" in model:
            # Resolve "owner/name" slug -> latest version hash. Works for BOTH
            # official and community models (the model-scoped /predictions endpoint
            # only exists for official models, so we always go via /v1/predictions
            # with a resolved hash). (2026-06-11.)
            mr = requests.get(f"https://api.replicate.com/v1/models/{model}",
                              headers=headers, timeout=30)
            mr.raise_for_status()
            version = (mr.json().get("latest_version") or {}).get("id")
            if not version:
                raise RuntimeError(f"Replicate model {model} has no latest version.")
        resp = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers=headers,
            json={"version": version, "input": {"prompt": prompt}},
            timeout=30,
        )
        resp.raise_for_status()
        pred_id = resp.json().get("id")
        if not pred_id:
            raise RuntimeError(f"Replicate returned no prediction id: {resp.json()}")
        video_url = self._poll_replicate_video(pred_id, headers)
        return {
            "mode": "production",
            "type": "video",
            "prompt": prompt,
            "duration": duration,
            "path": video_url,
            "provider": "replicate",
            "model": model,
            "cost_estimate_usd": round(self.cost_per_second * duration, 3),
        }

    def _poll_replicate_video(self, pred_id, headers, max_attempts=90, interval=10):
        for _ in range(max_attempts):
            r = requests.get(
                f"https://api.replicate.com/v1/predictions/{pred_id}",
                headers=headers, timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            status = data.get("status", "").lower()
            if status == "succeeded":
                out = data.get("output")
                url = out[0] if isinstance(out, list) and out else out
                if isinstance(url, str) and url:
                    return url
                raise RuntimeError(f"Replicate pred {pred_id} succeeded but no video URL: {out}")
            if status in ("failed", "canceled"):
                raise RuntimeError(f"Replicate pred {pred_id} {status}: {data.get('error', '')}")
            time.sleep(interval)
        raise RuntimeError(f"Replicate video pred {pred_id} timed out after {max_attempts * interval}s.")

    def _poll_generation(self, gen_id, headers, max_attempts=60, interval=5):
        for _ in range(max_attempts):
            r = requests.get(
                f"{self.BASE_URL}/v1/generations/{gen_id}",
                headers=headers,
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            status = data.get("status", "").upper()
            if status == "SUCCEEDED":
                video_url = data.get("output", {}).get("url")
                if video_url:
                    return video_url
                raise RuntimeError(f"Runway gen {gen_id} succeeded but no URL.")
            if status in ("FAILED", "CANCELLED"):
                raise RuntimeError(f"Runway gen {gen_id} {status}: {data.get('failureReason', '')}")
            time.sleep(interval)
        raise RuntimeError(f"Runway gen {gen_id} timed out after {max_attempts * interval}s.")
