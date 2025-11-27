def compute_risk_score(testcase, change_summary, feedback_history):
    """Compute traditional risk score (LEGACY - backward compatible).
    
    Returns a score based on component relevance, UI element type, failure history,
    and flakiness. This function is maintained for backward compatibility.
    
    For new code, consider using compute_combined_score() which integrates FRC.
    """
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

    # Extract status - handle both dict format {"status": "pass"} and string format "pass"
    test_history = []
    for f in feedback_history:
        if f["test_id"] == test_id:
            result = f.get("result")
            if isinstance(result, dict):
                test_history.append(result.get("status", "unknown"))
            elif isinstance(result, str):
                test_history.append(result)
            else:
                test_history.append("unknown")

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


def compute_combined_score(testcase, change_summary, feedback_history, use_frc=True):
    """Compute combined score using risk + FRC + LLM weighting.
    
    NEW FORMULA:
        If use_frc=True:
            combined = 0.4 * normalize(risk_score) + 0.4 * frc + 0.2 * llm_weight
        else:
            combined = risk_score (backward compatible)
    
    Args:
        testcase: Testcase dict
        change_summary: Code change description
        feedback_history: List of past feedback entries
        use_frc: Whether to enable FRC integration (default: True)
    
    Returns:
        Tuple of (combined_score, explanation_reason_string)
    """
    from core.frc_score import compute_frc
    
    # Get risk score
    risk_score, risk_reason = compute_risk_score(testcase, change_summary, feedback_history)
    
    # If FRC disabled, return legacy risk score
    if not use_frc:
        return risk_score, risk_reason
    
    # Normalize risk score to 0-1 range (risk scores typically 0-20)
    # Use sigmoid-like normalization: risk / (risk + 10)
    normalized_risk = risk_score / (abs(risk_score) + 10.0) if risk_score != 0 else 0.0
    normalized_risk = max(0.0, min(normalized_risk, 1.0))
    
    # Compute FRC (already 0-1)
    frc_score = compute_frc(testcase, change_summary, feedback_history)
    
    # LLM weight placeholder (0.5 as default neutral value)
    llm_weight = 0.5
    
    # Combined score: 0.4 risk + 0.4 frc + 0.2 llm
    combined = 0.4 * normalized_risk + 0.4 * frc_score + 0.2 * llm_weight
    combined = round(combined, 4)
    
    reason = f"Risk:{normalized_risk:.2f} + FRC:{frc_score:.2f} + LLM:0.5 = Combined:{combined:.2f}"
    
    return combined, reason
