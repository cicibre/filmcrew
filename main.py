#!/usr/bin/env python3
"""ROVA Film Crew — Pipeline Orchestrator.

One command runs the entire film crew:
    python main.py --job templates/example_spotlight.json --dry-run
    python main.py --job templates/example_spotlight.json --script-mode
    python main.py --job templates/example_spotlight.json --continue
"""
import argparse
import json
import os
import sys
import traceback

from filmcrew.base import load_config
from filmcrew.producer import Producer
from filmcrew.archivist import Archivist
from filmcrew.exceptions import GatePause, CrewFailure


def _save_manifest(manifest, config, job_id, label=""):
    manifest_dir = config.get("general", {}).get("manifest_dir", "outputs/manifests")
    os.makedirs(manifest_dir, exist_ok=True)
    suffix = f"_{label}" if label else ""
    manifest_path = os.path.join(
        manifest_dir, f"{job_id}{suffix}_manifest.json"
    )
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest_path


def _load_manifest(job_id, config):
    manifest_dir = config.get("general", {}).get("manifest_dir", "outputs/manifests")
    manifest_path = os.path.join(manifest_dir, f"{job_id}_manifest.json")
    if os.path.isfile(manifest_path):
        with open(manifest_path, "r") as f:
            return json.load(f)
    return None


def _report(manifest, config, job):
    print("\n" + "=" * 60)
    status = manifest.get("status", "unknown")
    if status == "complete":
        print("PRODUCTION COMPLETE")
    else:
        print(f"PRODUCTION STATUS: {status.upper()}")
    print("=" * 60)
    print(f"Job ID:   {job.get('job_id')}")
    print(f"Mode:     {config['general']['mode']}")
    print(f"Status:   {status}")

    manifest_dir = config.get("general", {}).get("manifest_dir", "outputs/manifests")
    manifest_path = os.path.join(
        manifest_dir, f"{job.get('job_id', 'film')}_manifest.json"
    )
    print(f"Manifest: {manifest_path}")

    library_path = config.get("general", {}).get("archive_dir", "outputs/archive")
    print(f"Library:  {os.path.join(library_path, 'library.json')}")

    cost = manifest.get("cinematography", {}).get("total_cost_estimate_usd", 0) + \
           manifest.get("sound_design", {}).get("total_cost_estimate_usd", 0)
    if cost > 0:
        print(f"Estimated cost: ${cost:.4f} USD")

    if status == "failed":
        failure = manifest.get("failure", {})
        print(f"\nFAILED at role: {failure.get('role')}")
        print(f"Error: {failure.get('error')}")
    elif config["general"]["mode"] == "dry_run":
        print("\n[main] This was a dry run. No API credits spent.")
    elif config["general"]["mode"] == "script_mode":
        print("\n[main] Script mode: real LLM thinking, mocked media.")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="ROVA Film Crew — AI agent documentary and showcase production."
    )
    parser.add_argument(
        "--job",
        required=False,
        help="Path to job JSON file (e.g., templates/example_spotlight.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without API calls — generates prompts and plans only.",
    )
    parser.add_argument(
        "--script-mode",
        action="store_true",
        help="Use real LLM for Director/Screenwriter/Storyboard; mock all media generators.",
    )
    parser.add_argument(
        "--continue",
        dest="resume",
        action="store_true",
        help="Resume from saved manifest (skip completed phases).",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    args = parser.parse_args()

    # Ensure project root is cwd so relative paths in config resolve
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    config = load_config(args.config)
    if args.dry_run:
        config["general"]["mode"] = "dry_run"
        print("[main] DRY-RUN MODE — no API calls will be made.\n")
    elif args.script_mode:
        config["general"]["mode"] = "script_mode"
        print("[main] SCRIPT MODE — real LLM for thinking, mocked media.\n")
    else:
        print("[main] PRODUCTION MODE\n")

    # Determine job source
    job = None
    if args.resume:
        if not args.job:
            # Try to resume the most recent job from manifests
            manifest_dir = config.get("general", {}).get("manifest_dir", "outputs/manifests")
            candidates = [
                f for f in os.listdir(manifest_dir)
                if f.endswith("_manifest.json") and not f.endswith("_partial_manifest.json")
            ]
            if not candidates:
                print("[main] ERROR: No saved manifest found to resume.")
                return 1
            # Most recently modified
            latest = max(
                candidates,
                key=lambda f: os.path.getmtime(os.path.join(manifest_dir, f))
            )
            job_id = latest.replace("_manifest.json", "")
            print(f"[main] Resuming most recent job: {job_id}\n")
            manifest = _load_manifest(job_id, config)
            job_path = None
        else:
            # Load specific job file for metadata, then load its manifest
            if not os.path.isfile(args.job):
                print(f"[main] ERROR: Job file not found: {args.job}")
                return 1
            with open(args.job, "r") as f:
                job_file_data = json.load(f)
            job_id = job_file_data.get("job_id")
            manifest = _load_manifest(job_id, config)
            job_path = args.job
            if manifest is None:
                print(f"[main] ERROR: No saved manifest found for {job_id}.")
                return 1
            print(f"[main] Resuming job: {job_id}\n")
            job = job_file_data
    else:
        # Fresh run
        if not args.job:
            print("[main] ERROR: --job is required (unless using --continue).")
            return 1
        if not os.path.isfile(args.job):
            print(f"[main] ERROR: Job file not found: {args.job}")
            return 1
        with open(args.job, "r") as f:
            job = json.load(f)
        manifest = None
        job_path = args.job

    if job:
        print(f"[main] Loading job: {job.get('job_id', 'unknown')}")
        print(f"[main] Title: {job.get('title')}")
        print(f"[main] Subject: {job.get('subject')}")
        print()

    # Run pipeline
    producer = Producer(config)
    try:
        manifest = producer.work(job, manifest)
    except GatePause as e:
        # Save partial manifest and tell user how to resume
        manifest_path = _save_manifest(e.manifest, config, e.job_id, label="paused")
        print(f"\n{'='*60}")
        print("PRODUCTION PAUSED FOR REVIEW")
        print("="*60)
        print(f"Gate:      {e.gate_name}")
        print(f"Job ID:    {e.job_id}")
        print(f"Manifest:  {manifest_path}")
        print("\n[main] Review the manifest, then resume with:")
        print(f"  python main.py --job {job_path or args.job} --continue")
        print()
        return 0
    except CrewFailure as e:
        # Save partial manifest and report failure
        manifest_path = _save_manifest(e.partial_manifest, config, e.job_id, label="failed")
        print(f"\n{'='*60}")
        print("PRODUCTION FAILED")
        print("="*60)
        print(f"Role:      {e.role}")
        print(f"Job ID:    {e.job_id}")
        print(f"Error:     {e.original_error}")
        print(f"Manifest:  {manifest_path}")
        print("\n[main] Fix the issue, then resume with:")
        print(f"  python main.py --job {job_path or args.job} --continue")
        print()
        return 1
    except Exception as e:
        traceback.print_exc()
        print(f"\n[main] UNEXPECTED ERROR: {e}")
        return 1

    # Archive
    archivist = Archivist(config)
    manifest = archivist.work(job, manifest)

    # Final save
    _save_manifest(manifest, config, job.get("job_id", "film"), label="")

    # Report
    _report(manifest, config, job)
    return 0


if __name__ == "__main__":
    sys.exit(main())
