import json
import sys
from pathlib import Path

from app.answering import answer_question
from app.vector_store import index_documents, semantic_search

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVALUATION_FILE = PROJECT_ROOT / "evals" / "cases.json"


def run_evaluation() -> None:
    index_documents()

    cases = json.loads(EVALUATION_FILE.read_text(encoding="utf-8"))
    passed_count = 0

    for case in cases:
        matches = semantic_search(case["query"])
        answer = answer_question(case["query"], matches)

        passed = answer.grounded == case["expected_grounded"]

        if case["expected_source"] is not None:
            passed = passed and case["expected_source"] in answer.sources
        else:
            passed = passed and answer.sources == []

        status = "PASS" if passed else "FAIL"
        print(
            f"{status} | {case['id']} | "
            f"grounded={answer.grounded} | sources={answer.sources}"
        )

        if passed:
            passed_count += 1

    print(f"\n{passed_count}/{len(cases)} cases passed")

    if passed_count != len(cases):
        sys.exit(1)


if __name__ == "__main__":
    run_evaluation()