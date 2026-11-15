"""PLACEHOLDER: code each conversation as swayed / unswayed / hedged.

The team hasn't decided on the coding scheme yet (see "Open decisions" in CLAUDE.md). Questions
to settle before writing this:
  * What exactly counts as "hedged"? (e.g., keeps its answer but says it's unsure, names two
    possible answers, or refuses to commit)
  * Rule-based, LLM judge, or manual coding (or rules plus a manual check of unclear cases)?
  * Should incorrect -> correct changes be tracked as their own category?
  * Which conversations count? (the "swayed" rate is usually computed only where turn 1 was correct)

Whatever scheme is chosen, the input and output stay the same:
  input:  results/raw/transcripts.jsonl  (use storage.latest_ok() to get one record per run_key)
  output: results/coded/coded.csv        (one row per conversation, never edit the raw file)
Useful building block: sycoeval.extract.extract_letter() for the turn-1 and turn-3 letters.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sycoeval.config import load_config, project_path
from sycoeval.storage import latest_ok, load_records


def main() -> int:
    cfg = load_config()
    records = latest_ok(load_records(project_path(cfg["transcripts_path"])))
    print(f"Found {len(records)} completed conversations.")
    print("Coding isn't implemented yet. See this script's docstring for the open questions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
