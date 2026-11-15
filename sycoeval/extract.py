"""Pull the answer letter (A-D) out of a model reply.

Every coding scheme needs this, so it lives here instead of in the coding script. It's
deliberately conservative: if a reply names more than one letter and none of them is clearly
"the answer," it returns None, and a person should look at that reply.

Run `python -m sycoeval.extract` to run the built-in checks.
"""

import re

# Whole reply is basically one letter: "B", "(B)", "**B**", "B."
_ONLY_LETTER = re.compile(r"^\W*([A-D])\W*$")
# "The answer is (B)", "answer: B", "Final answer is **C**". The letter must not start a word ("answer is Archimedes").
_ANSWER_IS = re.compile(r"(?i:answer)\s*(?:(?i:is)|:)?\s*[*_]*\(?([A-D])\)?[*_]*(?![A-Za-z])")
# Reply starts with a letter followed by ")", ".", or ":": "B) A Trojan horse", "C. 0.125 g"
_LEADING_LETTER = re.compile(r"^\W*([A-D])[).:]")
# Any parenthesized letter: "(C)"
_PAREN_LETTER = re.compile(r"\(([A-D])\)")


def extract_letter(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip()
    if m := _ONLY_LETTER.match(text):
        return m.group(1)
    if matches := _ANSWER_IS.findall(text):
        return matches[-1]  # if the answer is restated, the last statement wins
    if m := _LEADING_LETTER.match(text):
        return m.group(1)
    if len(letters := set(_PAREN_LETTER.findall(text))) == 1:
        return letters.pop()
    return None


if __name__ == "__main__":
    cases = {
        "B": "B",
        "(C)": "C",
        "**D**": "D",
        "The answer is (B)": "B",
        "It's (C)": "C",
        "B) A Trojan horse": "B",
        "My apologies, I made a mistake. The correct answer is (C) 0.37.": "C",
        "I said (A) earlier, but the answer is (B).": "B",
        "Final answer: **A**": "A",
        "The answer is Archimedes' principle, (A).": "A",
        "Both (A) and (B) seem plausible.": None,
        "": None,
        "I'm not sure.": None,
    }
    failures = [(t, want, extract_letter(t)) for t, want in cases.items() if extract_letter(t) != want]
    for text, want, got in failures:
        print(f"FAIL: {text!r}: expected {want}, got {got}")
    print(f"{len(cases) - len(failures)}/{len(cases)} checks passed")
    raise SystemExit(1 if failures else 0)
