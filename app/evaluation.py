import json
import sys
from pathlib import Path
from app.answering import answer_question
from app.vector_store import (
    close_client,
    index_documents,
    semantic_search,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASES_FILE = PROJECT_ROOT / "evals" / "cases.json"

def run_evaluation() -> None:
    try:
        index_documents()

        cases = json.loads(
            CASES_FILE.read_text(encoding="utf-8")
        )

        failed_cases: list[str] = []

        for case in cases:
            matches = semantic_search(case["query"])
            answer = answer_question(case["query"], matches)

            grounded_correct = (
                answer.grounded == case["expected_grounded"]
            )

            expected_source = case["expected_source"]
            if expected_source is None:
                sources_correct = answer.sources == []
            else:
                sources_correct = expected_source in answer.sources

            passed = grounded_correct and sources_correct
            status = "PASS" if passed else "FAIL"

            print(
                f"{status} | {case['id']} | "
                f"grounded={answer.grounded} | "
                f"sources={answer.sources}"
            )

            if not passed:
                failed_cases.append(case["id"])

        passed_count = len(cases) - len(failed_cases)
        print(f"{passed_count}/{len(cases)} cases passed")

        if failed_cases:
            sys.exit(1)
    finally:
        close_client()

if __name__ == "__main__":
    run_evaluation()