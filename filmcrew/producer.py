import json
import os
import shutil
from datetime import datetime

from filmcrew.base import BaseCrewMember
from filmcrew.director import Director
from filmcrew.screenwriter import Screenwriter
from filmcrew.storyboard import Storyboard
from filmcrew.cinematographer import Cinematographer
from filmcrew.sound_designer import SoundDesigner
from filmcrew.editor import Editor


class Producer(BaseCrewMember):
    role = "producer"

    def __init__(self, config):
        super().__init__(config)
        self.crew = {
            "director": Director(config),
            "screenwriter": Screenwriter(config),
            "storyboard": Storyboard(config),
            "cinematographer": Cinematographer(config),
            "sound_designer": SoundDesigner(config),
            "editor": Editor(config),
        }
        self.gates = config.get("gates", {})

    def work(self, job, manifest=None):
        if manifest is None:
            manifest = {}

        job_id = job.get("job_id", "unknown")
        manifest["job_id"] = job_id
        manifest["started_at"] = datetime.utcnow().isoformat()
        manifest["mode"] = self.mode

        print(f"[Producer] Starting production: {job_id}")

        # Phase 1: Director
        print("[Producer] Calling Director...")
        manifest = self.crew["director"].work(job, manifest)
        if self._gate("director_plan"):
            self._pause_for_review("director_plan", manifest)

        # Phase 2: Screenwriter
        print("[Producer] Calling Screenwriter...")
        manifest = self.crew["screenwriter"].work(job, manifest)
        if self._gate("screenwriter_script"):
            self._pause_for_review("screenwriter_script", manifest)

        # Phase 3: Storyboard
        print("[Producer] Calling Storyboard Artist...")
        manifest = self.crew["storyboard"].work(job, manifest)
        if self._gate("storyboard_frames"):
            self._pause_for_review("storyboard_frames", manifest)

        # Phase 4: Cinematographer
        print("[Producer] Calling Cinematographer...")
        manifest = self.crew["cinematographer"].work(job, manifest)

        # Phase 5: Sound Designer
        print("[Producer] Calling Sound Designer...")
        manifest = self.crew["sound_designer"].work(job, manifest)

        # Phase 6: Editor
        print("[Producer] Calling Editor...")
        manifest = self.crew["editor"].work(job, manifest)
        if self._gate("final_cut"):
            self._pause_for_review("final_cut", manifest)

        manifest["finished_at"] = datetime.utcnow().isoformat()
        manifest["status"] = "complete"

        # Delivery
        self._deliver(job, manifest)
        self._archive_job(job)

        print(f"[Producer] Production complete: {job_id}")
        return manifest

    def _gate(self, gate_name):
        return self.gates.get(gate_name, True)

    def _pause_for_review(self, gate_name, manifest):
        print(f"[Producer] GATE: {gate_name} — review required.")
        print("[Producer] To continue, re-run without the gate or approve in config.")
        # In a real app, this would block/wait. For now we log and continue.

    def _deliver(self, job, manifest):
        manifest_dir = self.config.get("general", {}).get(
            "manifest_dir", "outputs/manifests"
        )
        os.makedirs(manifest_dir, exist_ok=True)
        manifest_path = os.path.join(
            manifest_dir, f"{job.get('job_id', 'film')}_manifest.json"
        )
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"[Producer] Manifest delivered: {manifest_path}")

    def _archive_job(self, job):
        inbox = self.config.get("general", {}).get("jobs_inbox", "jobs/inbox")
        archive = self.config.get("general", {}).get("jobs_archive", "jobs/archive")
        os.makedirs(archive, exist_ok=True)

        job_id = job.get("job_id", "")
        for fname in os.listdir(inbox):
            if fname.endswith(".json") and job_id in fname:
                src = os.path.join(inbox, fname)
                dst = os.path.join(archive, fname)
                shutil.move(src, dst)
                print(f"[Producer] Job archived: {fname}")
                break
