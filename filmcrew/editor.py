import os
import subprocess

from filmcrew.base import BaseCrewMember


class Editor(BaseCrewMember):
    role = "editor"

    def work(self, job, manifest):
        cinematography = manifest.get("cinematography", {})
        sound_design = manifest.get("sound_design", {})

        assets = cinematography.get("assets", [])
        voiceover = sound_design.get("voiceover", {})
        music = sound_design.get("music", {})

        if self.mode == "dry_run":
            return self._assemble_dry_run(job, manifest, assets, voiceover, music)
        return self._assemble_real(job, manifest, assets, voiceover, music)

    def _assemble_dry_run(self, job, manifest, assets, voiceover, music):
        edit_plan = {
            "mode": "dry_run",
            "title": job.get("title"),
            "estimated_duration": job.get("duration_seconds", 60),
            "scenes": [
                {
                    "frame": a["frame"],
                    "prompt": a["prompt"],
                    "note": "would be placed on timeline here",
                }
                for a in assets
            ],
            "audio_tracks": {
                "voiceover": voiceover.get("text_preview", "[no voiceover]"),
                "music": music.get("prompt", "[no music]"),
            },
            "transitions": ["fade" for _ in range(len(assets) - 1)],
            "output_path": "[PLACEHOLDER] final cut would be rendered here",
        }
        manifest["edit"] = edit_plan
        return manifest

    def _assemble_real(self, job, manifest, assets, voiceover, music):
        output_dir = self.config.get("general", {}).get("output_dir", "outputs/films")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir, f"{job.get('job_id', 'film')}.mp4"
        )

        # TODO: Real assembly with ffmpeg
        # For now, generate a placeholder text file describing the assembly
        assembly_note = os.path.join(
            output_dir, f"{job.get('job_id', 'film')}_assembly.txt"
        )
        with open(assembly_note, "w") as f:
            f.write(f"Assembly plan for {job.get('title')}\n")
            for a in assets:
                f.write(f"- Frame {a['frame']}: {a.get('prompt', '')}\n")
            f.write(f"Voiceover: {voiceover.get('text_preview', '')}\n")
            f.write(f"Music: {music.get('prompt', '')}\n")
            f.write(f"Target output: {output_path}\n")

        manifest["edit"] = {
            "mode": "production",
            "output_path": output_path,
            "assembly_note": assembly_note,
            "status": "assembly plan written — real ffmpeg integration pending",
        }
        return manifest

    def _run_ffmpeg(self, cmd):
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, check=True
            )
            return {"success": True, "stdout": result.stdout}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": e.stderr}
