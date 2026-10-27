"""Run Speech Data Lab processing jobs (docs/SPEECH_DATA_LAB.md, PR 2).

From the repository root, with SIAMSIL_DATABASE_URL set, migrations applied, and FFmpeg installed:

    python backend/scripts/run_speech_jobs.py            # run every waiting job, then stop
    python backend/scripts/run_speech_jobs.py --watch    # keep running, checking every 30 seconds
    python backend/scripts/run_speech_jobs.py --retry-blocked   # requeue blocked jobs first

Safe to run on several machines at once, and safe to stop at any point: a job a stopped worker
held is taken over when its lease expires, and finished work is never repeated.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from database import get_session_factory  # noqa: E402
from settings import get_settings  # noqa: E402
from speech.jobs import JobRunner, WorkerSettings  # noqa: E402
from speech.media import LocalMediaStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Speech Data Lab processing jobs.")
    parser.add_argument("--watch", action="store_true", help="keep running and pick up new jobs")
    parser.add_argument("--interval", type=int, default=30, help="seconds between checks with --watch")
    parser.add_argument("--limit", type=int, help="run at most this many jobs per pass")
    parser.add_argument("--retry-blocked", action="store_true", help="requeue blocked jobs (they block again if still not allowed)")
    args = parser.parse_args()

    factory = get_session_factory()
    if factory is None:
        sys.exit("SIAMSIL_DATABASE_URL is not set.")
    settings = get_settings()
    runner = JobRunner(
        factory.begin,
        LocalMediaStore(settings.speech_media_dir),
        WorkerSettings(
            ffmpeg=settings.speech_ffmpeg,
            ffprobe=settings.speech_ffprobe,
            lease_seconds=settings.speech_job_lease_seconds,
            max_attempts=settings.speech_job_max_attempts,
        ),
    )
    if args.retry_blocked:
        print(f"Requeued {runner.retry_blocked()} blocked job(s).")
    while True:
        counts = runner.run_all(limit=args.limit)
        if counts:
            print(", ".join(f"{count} {status}" for status, count in sorted(counts.items())), flush=True)
        if not args.watch:
            if not counts:
                print("No jobs waiting.")
            return 0
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
