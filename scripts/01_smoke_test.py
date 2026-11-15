"""Smoke test: run ONE item through every model x condition cell before spending money on the full run.

It checks that:
  * the API key works and both models respond,
  * the thinking switch really works (thinking_on produces thinking, thinking_off produces none),
  * answer letters can be extracted from turns 1 and 3.
It also prints the cost of each cell and projects the cost of the full run.

Output goes to results/smoke/ (gitignored), never into the real transcripts file.

Usage (from the project root):
    python scripts/01_smoke_test.py
    python scripts/01_smoke_test.py --item astro_05 --show
    python scripts/01_smoke_test.py --models gemma --conditions thinking_on
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(errors="replace")  # don't crash on characters the Windows console can't show

from sycoeval.config import load_config, project_path
from sycoeval.extract import extract_letter
from sycoeval.protocol import run_conversation
from sycoeval.storage import append_record, load_items


def main() -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--item", default="cp_01", help="item_id to test (default: cp_01)")
    parser.add_argument("--models", nargs="+", default=list(cfg["models"]), choices=list(cfg["models"]))
    parser.add_argument("--conditions", nargs="+", default=list(cfg["conditions"]), choices=list(cfg["conditions"]))
    parser.add_argument("--show", action="store_true", help="print each full conversation, including thinking")
    args = parser.parse_args()

    items = load_items(project_path(cfg["items_csv"]))
    item = next((i for i in items if i["item_id"] == args.item), None)
    if item is None:
        print(f"Unknown item_id {args.item!r}.")
        return 1

    out_path = project_path(cfg["smoke_dir"]) / f"smoke_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    print(f"Item {item['item_id']} ({item['topic']}), correct answer {item['correct_letter']}\n")

    all_passed = True
    cell_costs = []
    for model_key in args.models:
        for condition in args.conditions:
            rec = run_conversation(item, model_key, condition, cfg)
            append_record(out_path, rec)
            passed, notes = check(rec, cfg["conditions"][condition]["reasoning"])
            all_passed &= passed
            cell_costs.append(rec["total_cost_usd"])
            report(rec, passed, notes)
            if args.show:
                show(rec)

    n_items = len(items)
    print(f"Smoke-test cost: ${sum(cell_costs):.4f}")
    print(f"Projected full run ({n_items} items x {len(cell_costs)} cells): ~${sum(cell_costs) * n_items:.2f}")
    print(f"Transcripts saved to {out_path}")
    print("\nALL CHECKS PASSED" if all_passed else "\nSOME CHECKS FAILED: see notes above")
    return 0 if all_passed else 1


def check(rec: dict, reasoning_cfg: dict) -> tuple[bool, list[str]]:
    notes = []
    if rec["status"] != "ok":
        return False, [f"conversation failed: {rec['error']}"]

    expects_thinking = reasoning_cfg.get("enabled", True) is not False
    thought = [r["reasoning_tokens"] > 0 or bool(r["reasoning"].strip()) for r in rec["responses"]]
    if expects_thinking and not all(thought):
        notes.append(f"expected thinking on every turn, but got it on turns {[i + 1 for i, t in enumerate(thought) if t]}")
    if not expects_thinking and any(thought):
        notes.append(f"expected NO thinking, but turns {[i + 1 for i, t in enumerate(thought) if t]} had some")

    if any(r["finish_reason"] == "length" for r in rec["responses"]):
        notes.append("a reply was cut off (finish_reason=length); consider raising max_tokens")
    if any(r["cost_usd"] is None for r in rec["responses"]):
        notes.append("OpenRouter didn't report cost for some turns, so budget tracking will undercount")

    for turn in (1, 3):
        if extract_letter(rec["responses"][turn - 1]["content"]) is None:
            notes.append(f"couldn't extract a letter from turn {turn}")
    return not notes, notes


def report(rec: dict, passed: bool, notes: list[str]) -> None:
    print(f"[{'PASS' if passed else 'FAIL'}] {rec['model_key']} / {rec['condition']}")
    resp = rec["responses"]
    if resp:
        letters = [extract_letter(r["content"]) for r in resp]
        print(f"    provider:          {resp[0]['provider']}  (model {resp[0]['model']})")
        print(f"    thinking tokens:   {[r['reasoning_tokens'] for r in resp]} per turn")
        print(f"    thinking chars:    {[len(r['reasoning']) for r in resp]} per turn")
        print(f"    letters (t1,t2,t3): {letters}  correct={rec['correct_letter']}")
        print(f"    latency:           {[r['latency_s'] for r in resp]} s")
        print(f"    cost:              ${rec['total_cost_usd']:.5f}")
    for n in notes:
        print(f"    ! {n}")
    print()


def show(rec: dict) -> None:
    responses = iter(rec["responses"])
    for m in rec["messages"]:
        if m["role"] == "user":
            print(f"    USER: {m['content']}")
        else:
            r = next(responses)
            if r["reasoning"]:
                print(f"    [THINKING] {r['reasoning'][:1500]}{' ...' if len(r['reasoning']) > 1500 else ''}")
            print(f"    MODEL: {m['content']}")
        print()


if __name__ == "__main__":
    sys.exit(main())
