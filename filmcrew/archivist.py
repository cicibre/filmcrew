import json
import os
from datetime import datetime

from filmcrew.base import BaseCrewMember


class Archivist(BaseCrewMember):
    role = "archivist"

    def work(self, job, manifest):
        archive_dir = self.config.get("general", {}).get(
            "archive_dir", "outputs/archive"
        )
        os.makedirs(archive_dir, exist_ok=True)

        tokens = self._extract_tokens(manifest)
        entry = {
            "job_id": job.get("job_id"),
            "title": job.get("title"),
            "type": job.get("type"),
            "requested_by": job.get("requested_by"),
            "subject": job.get("subject"),
            "started_at": manifest.get("started_at"),
            "finished_at": manifest.get("finished_at"),
            "mode": manifest.get("mode"),
            "cost_estimate_usd": self._extract_cost(manifest),
            "tokens": tokens,
            "status": manifest.get("status"),
            "manifest_path": self._manifest_path(job),
        }

        library_path = os.path.join(archive_dir, "library.json")
        library = []
        if os.path.isfile(library_path):
            with open(library_path, "r") as f:
                library = json.load(f)

        # Update or append
        updated = False
        for i, item in enumerate(library):
            if item.get("job_id") == entry["job_id"]:
                library[i] = entry
                updated = True
                break
        if not updated:
            library.append(entry)

        with open(library_path, "w") as f:
            json.dump(library, f, indent=2)

        manifest["archivist"] = {
            "mode": self.mode,
            "library_path": library_path,
            "total_entries": len(library),
            "entry": entry,
        }
        print(f"[Archivist] Recorded in library: {entry['job_id']}")
        return manifest

    def _extract_cost(self, manifest):
        total = 0.0
        for key in ["cinematography", "sound_design"]:
            section = manifest.get(key, {})
            if isinstance(section, dict):
                total += section.get("total_cost_estimate_usd", 0)
        return round(total, 4)

    def _extract_tokens(self, manifest):
        tokens = {}
        for key in ["director_plan", "screenplay", "storyboard"]:
            section = manifest.get(key, {})
            if isinstance(section, dict) and "tokens" in section:
                for tkey, tval in section["tokens"].items():
                    tokens[f"{key}.{tkey}"] = tval
        total_in = sum(v for k, v in tokens.items() if "input" in k)
        total_out = sum(v for k, v in tokens.items() if "output" in k)
        tokens["TOTAL_input"] = total_in
        tokens["TOTAL_output"] = total_out
        tokens["TOTAL_all"] = total_in + total_out
        return tokens

    def _manifest_path(self, job):
        manifest_dir = self.config.get("general", {}).get(
            "manifest_dir", "outputs/manifests"
        )
        return os.path.join(
            manifest_dir, f"{job.get('job_id', 'film')}_manifest.json"
        )
