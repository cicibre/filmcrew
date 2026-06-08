"""Image generation via Replicate (FLUX) or similar provider.

Default provider: replicate / black-forest-labs/flux-schnell
Docs: https://replicate.com/docs/reference/http
Auth: Authorization: Token {api_key}
"""
import time

import requests


class ImageAPI:
    def __init__(self, config):
        self.config = config.get("image", {})
        self.mode = config.get("general", {}).get("mode", "dry_run")
        self.api_key = self.config.get("api_key", "")
        self.provider = self.config.get("provider", "replicate")
        self.cost_per_image = self.config.get("cost_per_image_usd", 0.02)

    def generate(self, prompt, **kwargs):
        if self.mode != "production":
            return self._mock(prompt, **kwargs)
        return self._real(prompt, **kwargs)

    def _mock(self, prompt, **kwargs):
        return {
            "mode": "dry_run",
            "type": "image",
            "prompt": prompt,
            "path": "[PLACEHOLDER] image would be generated here",
            "cost_estimate_usd": round(self.cost_per_image, 3),
        }

    def _real(self, prompt, **kwargs):
        if not self.api_key:
            raise RuntimeError("Image API key not configured. Add image.api_key to config.yaml.")

        if self.provider == "replicate":
            return self._replicate(prompt, **kwargs)
        raise NotImplementedError(f"Image provider '{self.provider}' not yet implemented.")

    def _replicate(self, prompt, **kwargs):
        headers = {"Authorization": f"Token {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "version": "black-forest-labs/flux-schnell",  # latest fast model
            "input": {"prompt": prompt, "width": 1920, "height": 1080, "num_outputs": 1},
        }

        resp = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        pred_id = data.get("id")
        if not pred_id:
            raise RuntimeError(f"Replicate returned no prediction id: {data}")

        image_url = self._poll_replicate(pred_id, headers)
        return {
            "mode": "production",
            "type": "image",
            "prompt": prompt,
            "path": image_url,
            "cost_estimate_usd": round(self.cost_per_image, 3),
        }

    def _poll_replicate(self, pred_id, headers, max_attempts=60, interval=3):
        for _ in range(max_attempts):
            r = requests.get(
                f"https://api.replicate.com/v1/predictions/{pred_id}",
                headers=headers,
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            status = data.get("status", "").lower()
            if status == "succeeded":
                urls = data.get("output", [])
                if urls:
                    return urls[0]
                raise RuntimeError(f"Replicate pred {pred_id} succeeded but no output.")
            if status in ("failed", "canceled"):
                raise RuntimeError(f"Replicate pred {pred_id} {status}: {data.get('error', '')}")
            time.sleep(interval)
        raise RuntimeError(f"Replicate pred {pred_id} timed out.")
