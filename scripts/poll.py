#!/usr/bin/env python3
"""ROVA Film Crew — Inbox Mailbox Pickup Runner.

Watches jobs/inbox/ for new JSON job specs and auto-runs the pipeline.
Usage:
    python scripts/poll.py --once          # process all pending jobs and exit
    python scripts/poll.py --daemon        # loop forever, polling inbox
    python scripts/poll.py --mode dry_run  # override mode
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime


def get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config(config_path="config.yaml"):
    import yaml
    root = get_project_root()
    path = os.path.join(root, config_path)
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_jobs(inbox_dir):
    """Return list of .json files in inbox, sorted oldest first."""
    if not os.path.isdir(inbox_dir):
        return []
    jobs = []
    for fname in sorted(os.listdir(inbox_dir)):
        if fname.endswith(".json"):
            jobs.append(os.path.join(inbox_dir, fname))
    return jobs


def validate_job(path):
    """Basic validation: valid JSON with required fields."""
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return None, str(e)

    required = ["job_id", "title", "type"]
    missing = [r for r in required if r not in data or not data[r]]
    if missing:
        return None, f"missing fields: {missing}"
    return data, None


def run_pipeline(job_path, mode_override=None):
    """Run the film crew pipeline on a single job."""
    root = get_project_root()
    main = os.path.join(root, "main.py")
    flags = [sys.executable, main, "--job", job_path]
    if mode_override:
        flags.append(f"--{mode_override}")
    else:
        flags.append("--script-mode")

    print(f"\n{'='*60}")
    print(f"[{datetime.utcnow().isoformat()}] Processing: {os.path.basename(job_path)}")
    print("="*60)
    try:
        result = subprocess.run(
            flags, cwd=root, capture_output=False, text=True, check=False
        )
        return result.returncode == 0
    except Exception as e:
        print(f"ERROR running pipeline: {e}")
        return False


def archive_job(job_path, archive_dir):
    """Move processed job to archive."""
    os.makedirs(archive_dir, exist_ok=True)
    basename = os.path.basename(job_path)
    dst = os.path.join(archive_dir, basename)
    # If duplicate, append timestamp
    if os.path.exists(dst):
        name, ext = os.path.splitext(basename)
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        dst = os.path.join(archive_dir, f"{name}-{ts}{ext}")
    os.rename(job_path, dst)
    print(f"[poll] Archived: {dst}")


def process_all(config, mode_override=None):
    inbox = config.get("general", {}).get("jobs_inbox", "jobs/inbox")
    archive = config.get("general", {}).get("jobs_archive", "jobs/archive")
    root = get_project_root()
    inbox_dir = os.path.join(root, inbox)
    archive_dir = os.path.join(root, archive)

    jobs = get_jobs(inbox_dir)
    if not jobs:
        print("[poll] Inbox empty. Nothing to process.")
        return 0

    processed = 0
    for job_path in jobs:
        data, err = validate_job(job_path)
        if data is None:
            print(f"[poll] INVALID job, skipping: {os.path.basename(job_path)} — {err}")
            # Move bad jobs to archive anyway so they don't block
            archive_job(job_path, archive_dir)
            continue

        ok = run_pipeline(job_path, mode_override)
        if ok:
            processed += 1
            archive_job(job_path, archive_dir)
        else:
            print(f"[poll] Pipeline FAILED for {data.get('job_id')}. Leaving in inbox.")
            # Do NOT archive failed jobs — they stay for retry

    return processed


def main():
    parser = argparse.ArgumentParser(
        description="Film Crew Mailbox Pickup — auto-run pipeline on new job specs"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process all pending jobs and exit (default if no flag)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Loop forever, polling inbox every 10 seconds",
    )
    parser.add_argument(
        "--mode",
        default=None,
        choices=["dry_run", "script_mode", "production"],
        help="Override crew mode for this run",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Polling interval in seconds (daemon mode only)",
    )
    args = parser.parse_args()

    config = load_config()
    mode = args.mode  # None means default to script_mode in run_pipeline

    if args.daemon:
        print(f"[poll] Daemon started. Polling every {args.interval}s. Press Ctrl+C to stop.\n")
        try:
            while True:
                process_all(config, mode)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[poll] Daemon stopped.")
            return 0
    else:
        count = process_all(config, mode)
        print(f"\n[poll] Done. Processed {count} job(s).")
        return 0 if count >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
