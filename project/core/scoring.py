def compute_risk_score(testcase, change_summary, feedback_history):
    score = 0
    reasons = []

    # ---- 1. Component + UI relevance ----
    if testcase["component"].lower() in change_summary.lower():
        score += 5
        reasons.append("Component changed")

    if testcase["ui_element"] in ["textbox", "button", "dropdown"]:
        score += 2
        reasons.append("Important UI element")

    if testcase["selector"] in change_summary:
        score += 3
        reasons.append("Selector match")

    # ---- 2. Long-term memory (history analysis) ----
    test_id = testcase["id"]

    test_history = [f["result"]["status"] for f in feedback_history if f["test_id"] == test_id]

    failures = test_history.count("fail")
    passes = test_history.count("pass")

    # Long-term failure weight (exponential)
    if failures > 0:
        score += (2 ** failures)   # 1 fail = +2, 2 fails = +4, 3 fails = +8…
        reasons.append(f"{failures} historical failures")

    # Flakiness detection
    if "fail" in test_history and "pass" in test_history:
        score += 3
        reasons.append("Flaky behavior detected")

    # High pass rate = stable test
    if passes >= 3 and failures == 0:
        score -= 2
        reasons.append("Consistently stable test")

    # Failure trend (recent 3 runs matter more)
    recent = test_history[-3:]
    if recent.count("fail") >= 2:
        score += 4
        reasons.append("Recent failure trend")

    # ---- 3. Performance factor ----
    if testcase["execution_time"] > 4:
        score -= 1
        reasons.append("Slow test penalty")

    return score, ", ".join(reasons) if reasons else "No major risk factors"
