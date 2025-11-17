from core.prioritizer import prioritize_tests
from core.feedback import load_feedback, save_feedback
from core.report import generate_html_report
import json


def main() -> None:
    
    change_summary = (
        "Refactor API client error handling and adjust retry logic for transient failures."
    )

    
    feedback_history = load_feedback()

    # PRIORITIZE TESTS (LLM + scoring + critic)
    prioritized, explanations_dict, testcases = prioritize_tests(change_summary, feedback_history)

    print("Prioritized test IDs:", prioritized)

    # SAVE FULL EXPLANATIONS
    with open("project/data/explanation_log.json", "w", encoding="utf-8") as f:
        json.dump(explanations_dict, f, indent=2)

    # GENERATE HTML REPORT
    report_path = generate_html_report(testcases, prioritized, explanations_dict)
    print(f"HTML Report saved to: {report_path}")

    # Simulate execution results
    results = {}
    for i, tid in enumerate(prioritized):
        results[tid] = {"status": "pass" if i % 2 == 0 else "fail"}

    # Save results back to memory (feedback)
    for tid, res in results.items():
        save_feedback(tid, res)

    print("Saved feedback for", len(results), "tests.")


if __name__ == "__main__":
    main()
