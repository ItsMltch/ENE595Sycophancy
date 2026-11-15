"""Full run: every item x model x condition, saved to results/raw/transcripts.jsonl.

  * Can resume: conversations that already finished successfully are skipped, so if the run
    crashes or you press Ctrl+C, just run it again.
  * Failed conversations are logged with status "error" and retried on the next run.
  * Stops starting new conversations once logged spending passes run.budget_usd in config.yaml.

Usage (from the project root):
    python scripts/02_run.py --dry-run          # show what would run, without calling the API
    python scripts/02_run.py --limit 8          # small practice batch
    python scripts/02_run.py                    # everything that's left
    python scripts/02_run.py --models haiku --conditions thinking_off
"""

import argparse
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(errors="replace")

from sycoeval.config import load_config, project_path
from sycoeval.protocol import build_first_prompt, run_conversation, run_key
from sycoeval.storage import append_record, latest_ok, load_items, load_records, total_cost


def main() -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=list(cfg["models"]), choices=list(cfg["models"]))
    parser.add_argument("--conditions", nargs="+", default=list(cfg["conditions"]), choices=list(cfg["conditions"]))
    parser.add_argument("--limit", type=int, help="only run this many of the remaining conversations")
    parser.add_argument("--dry-run", action="store_true", help="list the work and show a sample prompt, without any API calls")
    args = parser.parse_args()

    out_path = project_path(cfg["transcripts_path"])
    items = load_items(project_path(cfg["items_csv"]))
    existing = load_records(out_path)
    done = set(latest_ok(existing))
    spent = total_cost(existing)
    budget = cfg["run"]["budget_usd"]

    jobs = [
        (item, m, c)
        for m in args.models
        for c in args.conditions
        for item in items
        if run_key(item["item_id"], m, c) not in done
    ]
    total_jobs = len(items) * len(args.models) * len(args.conditions)
    print(f"{total_jobs - len(jobs)}/{total_jobs} already done; {len(jobs)} remaining. Spent so far: ${spent:.4f} of ${budget:.2f} budget.")
    if args.limit is not None:
        jobs = jobs[: args.limit]
    if not jobs:
        print("Nothing to do.")
        return 0

    if args.dry_run:
        print(f"Would run {len(jobs)} conversations, for example:")
        for item, m, c in jobs[:5]:
            print(f"    {run_key(item['item_id'], m, c)}")
        print("\nSample turn-1 prompt:\n" + build_first_prompt(jobs[0][0], cfg["protocol"].get("turn1_suffix", "")))
        return 0

    lock = threading.Lock()
    state = {"spent": spent, "finished": 0, "ok": 0, "error": 0, "skipped": 0}

    def work(item, model_key, condition):
        with lock:
            if state["spent"] >= budget:
                state["skipped"] += 1
                return None
        rec = run_conversation(item, model_key, condition, cfg)
        append_record(out_path, rec, lock)
        with lock:
            state["spent"] += rec["total_cost_usd"]
            state["finished"] += 1
            state[rec["status"]] += 1
            status = "ok" if rec["status"] == "ok" else f"ERROR: {rec['error']}"
            print(f"[{state['finished']}/{len(jobs)}] {rec['run_key']:<32} ${rec['total_cost_usd']:.4f}  (total ${state['spent']:.3f})  {status}")
        return rec

    pool = ThreadPoolExecutor(max_workers=cfg["run"]["max_workers"])
    try:
        futures = [pool.submit(work, *job) for job in jobs]
        for f in as_completed(futures):
            f.result()
    except KeyboardInterrupt:
        print("\nInterrupted: finishing the conversations already in progress. Run again to resume.")
        pool.shutdown(wait=True, cancel_futures=True)
        return 130
    pool.shutdown()

    print(f"\nDone. ok={state['ok']} error={state['error']} skipped_for_budget={state['skipped']}  total spent ${state['spent']:.4f}")
    if state["error"]:
        print("Errors are saved in the transcripts file. Run the script again to retry them.")
    return 1 if state["error"] or state["skipped"] else 0


if __name__ == "__main__":
    sys.exit(main())
