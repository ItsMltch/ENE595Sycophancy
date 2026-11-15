"""PLACEHOLDER: summarize the coded results into tables and charts for the report.

Planned outputs (to be finalized once 03_code.py exists):
  * Turn-1 accuracy per model x condition (how many items are eligible to be "swayed")
  * Swayed / unswayed / hedged rates per model x condition, among items answered correctly at turn 1
  * The same broken down by topic (conceptual physics, astronomy, electrical engineering)
  * Total cost and token usage per cell (from the raw transcripts)
  * Figures saved to results/figures/

  input:  results/coded/coded.csv  (+ results/raw/transcripts.jsonl for cost/tokens)
  output: results/figures/*.png, results/summary.csv
"""

import sys


def main() -> int:
    print("Analysis isn't implemented yet. Write 03_code.py first.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
