#!/usr/bin/env python3
"""ROVA Film Crew — Pipeline Orchestrator.

One command runs the entire film crew:
    python main.py --job templates/example_spotlight.json --dry-run
"""
import argparse
import json
import os
import sys

from filmcrew.base import load_config
from filmcrew.producer import Producer
from filmcrew.archivist import Archivist


def main():
    parser = argparse.ArgumentParser(
        description="ROVA Film Crew — AI agent documentary and showcase production."
    )
    parser.add_argument(
        "--job",
        required=True,
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

    if not os.path.isfile(args.job):
        print(f"[main] ERROR: Job file not found: {args.job}")
        return 1

    with open(args.job, "r") as f:
        job = json.load(f)

    print(f"[main] Loading job: {job.get('job_id', 'unknown')}")
    print(f"[main] Title: {job.get('title')}")
    print(f"[main] Subject: {job.get('subject')}")
    print()

    # Run pipeline
    producer = Producer(config)
    manifest = producer.work(job)

    # Archive
    archivist = Archivist(config)
    manifest = archivist.work(job, manifest)

    # Report
    print("\n" + "=" * 60)
    print("PRODUCTION COMPLETE")
    print("=" * 60)
    print(f"Job ID:   {job.get('job_id')}")
    print(f"Mode:     {config['general']['mode']}")
    print(f"Status:   {manifest.get('status')}")

    manifest_dir = config.get("general", {}).get(
        "manifest_dir", "outputs/manifests"
    )
    manifest_path = os.path.join(
        manifest_dir, f"{job.get('job_id', 'film')}_manifest.json"
    )
    print(f"Manifest: {manifest_path}")

    library_path = config.get("general", {}).get(
        "archive_dir", "outputs/archive"
    )
    print(f"Library:  {os.path.join(library_path, 'library.json')}")

    if config["general"]["mode"] == "dry_run":
        print("\n[main] This was a dry run. No API credits spent.")
        print("[main] Add API keys to config.yaml to generate real output.")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
