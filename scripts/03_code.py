"""Build the hand-coding materials from results/raw/transcripts.jsonl.

Coding scheme (decided 2026-11-19): each conversation is swayed or unswayed, by comparing the
model's turn-1 answer letter with its turn-3 answer letter. People read the replies and type in
both letters. Nothing is filled in automatically.

This writes two files (it never changes the raw transcripts):

1. results/coded/coding_sheet.csv: the spreadsheet you fill in, one row per conversation.
     row            matches the numbered headings in the readable transcripts
     run_key, item_id, topic, model, condition, correct_letter   who/what the row is
     turn1_end      the last ~300 characters of the turn-1 reply (where the answer usually is)
     turn1_full     the whole turn-1 reply, in case the answer isn't at the end
     turn1_letter   FILL IN: A, B, C, D, or "none" if the model didn't commit to one letter
     turn3_reply    the whole turn-3 reply (usually one line)
     turn3_letter   FILL IN: same as turn1_letter
     coder, notes   FILL IN: your initials, and anything worth remembering
   Once people start typing into it, this script won't overwrite it unless you pass --force.
   If you fill it in with Google Sheets, download it back as CSV to the same path.

2. results/coded/transcripts_readable.md: every conversation as a readable dialogue, with
   thinking in collapsible sections. Open it in VS Code's Markdown preview (Ctrl+Shift+V) or on
   GitHub, and search for a run_key or row number. It's rebuilt on every run, so don't edit it.

Usage (from the project root):
    python scripts/03_code.py            # build both (keeps an existing coding sheet)
    python scripts/03_code.py --force    # also rebuild the coding sheet, discarding anything typed into it
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sycoeval.config import load_config, project_path
from sycoeval.storage import latest_ok, load_items, load_records

END_CHARS = 300  # how much of the end of the turn-1 reply goes in turn1_end
EXCEL_CELL_LIMIT = 32767  # Excel cuts off longer cells

COLUMNS = [
    "row", "run_key", "item_id", "topic", "model", "condition", "correct_letter",
    "turn1_end", "turn1_full", "turn1_letter",
    "turn3_reply", "turn3_letter",
    "coder", "notes",
]


def in_order(records) -> list[dict]:
    """Group the four versions of each item (2 models x 2 conditions) next to each other."""
    return sorted(records, key=lambda r: (r["item_id"], r["model_key"], r["condition"]))


# ---------------------------------------------------------------- coding sheet

def cell(text: str) -> str:
    """Keep spreadsheet programs from treating a reply as a formula (e.g., one starting with "- ")."""
    text = text.strip()
    return " " + text if text[:1] in ("=", "+", "-", "@") else text


def ending(text: str, n: int = END_CHARS) -> str:
    text = text.strip()
    return text if len(text) <= n else "..." + text[-n:]


def build_rows(records: list[dict]) -> list[dict]:
    rows = []
    for number, r in enumerate(records, start=1):
        turn1 = r["responses"][0]["content"]
        turn3 = r["responses"][2]["content"]
        rows.append({
            "row": number,
            "run_key": r["run_key"],
            "item_id": r["item_id"],
            "topic": r["topic"],
            "model": r["model_key"],
            "condition": r["condition"],
            "correct_letter": r["correct_letter"],
            "turn1_end": cell(ending(turn1)),
            "turn1_full": cell(turn1),
            "turn1_letter": "",
            "turn3_reply": cell(turn3),
            "turn3_letter": "",
            "coder": "",
            "notes": "",
        })
    return rows


def write_sheet(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig so Excel shows symbols like Ω and µ correctly
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------- readable transcripts

def quote(text: str) -> str:
    """Put text in a Markdown blockquote, so headings or code blocks in a reply can't break the page."""
    return "\n".join("> " + line if line.strip() else ">" for line in text.strip().splitlines()) or "> (empty)"


def render_conversation(number: int, r: dict) -> str:
    resp = r["responses"]
    parts = [
        f"## {number}. {r['item_id']} · {r['model_key']} · {r['condition']}",
        f"`{r['run_key']}` · topic: {r['topic']} · correct answer: **{r['correct_letter']}** · "
        f"provider: {resp[0]['provider']} · cost: ${r['total_cost_usd']:.4f}",
    ]
    replies = iter(resp)
    turn = 0
    for message in r["messages"]:
        if message["role"] == "user":
            turn += 1
            parts += [f"**Turn {turn}: User**", quote(message["content"])]
            continue
        reply = next(replies)
        label = f"**Turn {turn}: Model**"
        if reply["finish_reason"] == "length":
            label += " (**cut off**: hit max_tokens)"
        parts.append(label)
        if reply["reasoning"].strip():
            parts.append(
                f"<details><summary>Thinking ({reply['reasoning_tokens']} tokens)</summary>\n\n"
                f"{quote(reply['reasoning'])}\n\n</details>"
            )
        elif reply["reasoning_tokens"]:
            parts.append(f"_(used {reply['reasoning_tokens']} thinking tokens; the text wasn't returned)_")
        parts.append(quote(message["content"]))
    return "\n\n".join(parts)


def render_readable(records: list[dict], source: str) -> str:
    header = (
        "# Readable transcripts\n\n"
        f"Built by `scripts/03_code.py` from `{source}` on {datetime.now():%Y-%m-%d %H:%M}. "
        "Don't edit this file; it's rebuilt every time the script runs.\n\n"
        f"{len(records)} conversations, grouped by item. The numbers match the `row` column of the "
        "coding sheet. Thinking is shown for reading only: it was not sent back to the model in "
        "later turns."
    )
    body = [render_conversation(n, r) for n, r in enumerate(records, start=1)]
    return "\n\n---\n\n".join([header, *body]) + "\n"


# ---------------------------------------------------------------- main

def main() -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="overwrite an existing coding sheet")
    args = parser.parse_args()

    records = in_order(latest_ok(load_records(project_path(cfg["transcripts_path"]))).values())
    if not records:
        print("No completed conversations yet. Run scripts/02_run.py first.")
        return 1
    expected = len(load_items(project_path(cfg["items_csv"]))) * len(cfg["models"]) * len(cfg["conditions"])
    if len(records) < expected:
        print(f"Note: only {len(records)} of {expected} conversations are complete. Finish the run before coding.")

    readable_path = project_path(cfg["readable_transcripts"])
    readable_path.parent.mkdir(parents=True, exist_ok=True)
    readable_path.write_text(render_readable(records, cfg["transcripts_path"]), encoding="utf-8")
    print(f"Wrote {len(records)} conversations to {readable_path}")

    sheet_path = project_path(cfg["coding_sheet"])
    if sheet_path.exists() and not args.force:
        print(f"Kept the existing {sheet_path} (people may have typed into it). Pass --force to rebuild it.")
        return 0
    rows = build_rows(records)
    write_sheet(rows, sheet_path)
    print(f"Wrote {len(rows)} rows to {sheet_path}")
    too_long = [row["run_key"] for row in rows if len(row["turn1_full"]) > EXCEL_CELL_LIMIT]
    if too_long:
        print(f"Warning: Excel will cut off turn1_full for {too_long}. Read those in the readable transcripts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
