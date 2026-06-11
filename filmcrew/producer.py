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
from filmcrew.exceptions import GatePause, CrewFailure


class Producer(BaseCrewMember):
    role = "producer"

    PHASE_ORDER = [
        ("director", "director"),
        ("screenwriter", "screenwriter"),
        ("storyboard", "storyboard"),
        ("cinematographer", "cinematographer"),
        ("sound_designer", "sound_designer"),
        ("editor", "editor"),
    ]

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
        job_id = job.get("job_id", "unknown")

        if manifest is None:
            manifest = {}
        else:
            print(f"[Producer] Resuming production: {job_id}")

        manifest["job_id"] = job_id
        if "started_at" not in manifest:
            manifest["started_at"] = datetime.utcnow().isoformat()
        manifest["mode"] = self.mode

        print(f"[Producer] Starting production: {job_id}")

        # Gates that have already been reviewed + approved (the human re-ran
        # --continue past them). A gate only pauses if it is NOT yet approved —
        # otherwise the last gate (final_cut, on the always-re-run editor) would
        # re-fire forever and the job could never complete. (Added 2026-06-11.)
        approved_gates = manifest.setdefault("_approved_gates", [])

        for phase_key, role_name in self.PHASE_ORDER:
            # Resume: skip if this phase already has output.
            # NB: each role writes its output under a *semantic* key (e.g.
            # director -> "director_plan"), which differs from phase_key. We must
            # look up that real key — checking `phase_key in manifest` never
            # matched, so on --continue no phase was skipped and any gated phase
            # re-ran + re-paused forever. (Fixed 2026-06-11, claude_b.)
            output_key = self._output_key_for_phase(phase_key)
            if output_key in manifest and phase_key != "editor":
                print(f"[Producer] {role_name.capitalize()} already done — skipping.")
                continue
            # Editor is special: re-run always to reflect latest upstream changes

            print(f"[Producer] Calling {role_name.capitalize()}...")
            try:
                manifest = self.crew[phase_key].work(job, manifest)
            except Exception as e:
                manifest["status"] = "failed"
                manifest["failed_at"] = datetime.utcnow().isoformat()
                manifest["failure"] = {"role": role_name, "error": str(e)}
                self._deliver(job, manifest)
                raise CrewFailure(role_name, job_id, e, manifest) from e

            gate_name = self._gate_name_for_phase(phase_key)
            if gate_name and self._gate(gate_name) and gate_name not in approved_gates:
                self._pause_for_review(gate_name, job_id, manifest)

        manifest["finished_at"] = datetime.utcnow().isoformat()
        manifest["status"] = "complete"

        # Delivery
        self._deliver(job, manifest)
        self._notify(job, manifest)
        self._archive_job(job)

        print(f"[Producer] Production complete: {job_id}")
        return manifest

    def _gate_name_for_phase(self, phase_key):
        mapping = {
            "director": "director_plan",
            "screenwriter": "screenwriter_script",
            "storyboard": "storyboard_frames",
            "editor": "final_cut",
        }
        return mapping.get(phase_key)

    def _output_key_for_phase(self, phase_key):
        # The manifest key each role writes its output under (differs from
        # phase_key for most roles). Keep in sync with the role implementations.
        mapping = {
            "director": "director_plan",
            "screenwriter": "screenplay",
            "storyboard": "storyboard",
            "cinematographer": "cinematography",
            "sound_designer": "sound_design",
            "editor": "edit",
        }
        return mapping.get(phase_key, phase_key)

    def _gate(self, gate_name):
        return self.gates.get(gate_name, True)

    def _pause_for_review(self, gate_name, job_id, manifest):
        # Record where we paused so resume knows which gate the human approved.
        manifest["_paused_at_gate"] = gate_name
        print(f"[Producer] GATE: {gate_name} — review required.")
        print("[Producer] To continue, re-run with --continue after reviewing.")
        raise GatePause(gate_name, job_id, manifest)

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

    def _notify(self, job, manifest):
        status = manifest.get("status", "unknown")
        job_id = job.get("job_id", "unknown")
        title = job.get("title", "Untitled")
        manifest_dir = self.config.get("general", {}).get(
            "manifest_dir", "outputs/manifests"
        )
        manifest_path = os.path.join(
            manifest_dir, f"{job_id}_manifest.json"
        )

        # Flow notification
        flow_cfg = self.config.get("delivery", {}).get("flow", {})
        if flow_cfg.get("enabled"):
            try:
                import requests
                requests.post(
                    flow_cfg.get("url", "http://flow:5018/flow/api/ai-channel"),
                    json={
                        "user": flow_cfg.get("user", "FILM_CREW"),
                        "type": "film_complete",
                        "message": f"Film '{title}' is {status}. Manifest: {manifest_path}",
                    },
                    timeout=5,
                )
                print(f"[Producer] Notified Flow: {status}")
            except Exception as e:
                print(f"[Producer] Flow notification failed: {e}")

        # Telegram notification
        tg_cfg = self.config.get("delivery", {}).get("telegram", {})
        if tg_cfg.get("enabled"):
            try:
                import requests
                bot_token = tg_cfg.get("bot_token", "")
                chat_id = tg_cfg.get("chat_id", "")
                text = (
                    f"🎬 *ROVA Film Crew*\n"
                    f"Job: {job_id}\n"
                    f"Title: {title}\n"
                    f"Status: {status.upper()}"
                )
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                    timeout=5,
                )
                print(f"[Producer] Notified Telegram: {status}")
            except Exception as e:
                print(f"[Producer] Telegram notification failed: {e}")
