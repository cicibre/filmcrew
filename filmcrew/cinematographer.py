from filmcrew.base import BaseCrewMember
from apis.video_api import VideoAPI
from apis.image_api import ImageAPI


class Cinematographer(BaseCrewMember):
    role = "cinematographer"

    def work(self, job, manifest):
        storyboard = manifest.get("storyboard", {})
        frames = storyboard.get("frames", [])

        video_api = VideoAPI(self.config)
        image_api = ImageAPI(self.config)

        assets = []
        for i, frame in enumerate(frames[:8], 1):
            prompt = frame.get("prompt", frame.get("raw", "abstract visual"))
            duration = frame.get("duration", 3)

            result = video_api.generate(prompt, duration=duration)
            assets.append({
                "frame": i,
                "prompt": prompt,
                "result": result,
            })

        manifest["cinematography"] = {
            "mode": self.mode,
            "assets": assets,
            "total_frames": len(assets),
            "total_cost_estimate_usd": sum(
                a["result"].get("cost_estimate_usd", 0) for a in assets
            ),
        }
        return manifest
