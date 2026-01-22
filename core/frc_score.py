"""
frc_score.py

Failure Risk Coverage (FRC) scoring for test prioritization.

FRC combines four factors into a single 0-1 score:
  - Failure History (0.4): How often the test has failed historically
  - Component Criticality (0.3): How critical the affected component is
  - Selector Fragility (0.2): How brittle the UI selector is (flaky or complex)
  - Flakiness (0.1): Explicit flakiness flag

This module computes FRC independent of other scoring methods, enabling
flexible combination with risk scores, LLM weights, etc.

"""
from __future__ import annotations

import re
from typing import Any, Dict, List


# ----------------------- Component criticality database -------------------------
# Map component names to criticality scores (0-1, higher = more critical)
COMPONENT_CRITICALITY = {
    "login": 1.0,
    "authentication": 1.0,
    "auth": 1.0,
    "checkout": 0.95,
    "payment": 0.95,
    "cart": 0.9,
    "profile": 0.7,
    "dashboard": 0.6,
    "settings": 0.5,
    "search": 0.7,
    "navigation": 0.5,
    "footer": 0.2,
    "header": 0.4,
    "sidebar": 0.4,
    "homepage": 0.3,
}


def _get_component_criticality(component: str) -> float:
    """Get criticality score for a component (0-1).

    If exact match not found, use substring matching as fallback.
    """
    component_lower = component.lower()

    # Exact match
    if component_lower in COMPONENT_CRITICALITY:
        return COMPONENT_CRITICALITY[component_lower]

    # Substring match
    for key, score in COMPONENT_CRITICALITY.items():
        if key in component_lower:
            return score

    # Default: medium criticality
    return 0.5


def _compute_failure_history_score(testcase: Dict[str, Any], feedback_history: List[Dict[str, Any]]) -> float:
    """Compute failure history score (0-1).

    Higher score if the test has failed frequently in the past.
    Uses exponential weighting: more recent failures matter more.

    Args:
        testcase: Testcase dict with 'id' field
        feedback_history: List of feedback entries with 'test_id' and 'result'

    Returns:
        Score between 0 and 1
    """
    test_id = testcase.get("id")
    if not test_id or not feedback_history:
        return 0.0

    # Extract results for this test
    results = [f["result"]["status"] for f in feedback_history if f["test_id"] == test_id]

    if not results:
        return 0.0

    total = len(results)
    failures = results.count("fail")

    # Failure rate
    failure_rate = failures / total if total > 0 else 0.0

    # Exponential weight for recent runs (most recent = highest weight)
    # We assume results are in chronological order
    recent_weight = 0.0
    for i, result in enumerate(results[-5:]):  # Last 5 runs
        weight = 0.5 ** (len(results[-5:]) - i - 1)  # Exponential decay
        recent_weight += weight if result == "fail" else 0

    # Combine: 70% overall rate, 30% recent trend
    score = 0.7 * failure_rate + 0.3 * min(recent_weight / 5.0, 1.0)
    return min(score, 1.0)


def _compute_selector_fragility_score(selector: str) -> float:
    """Compute selector fragility score (0-1).

    Higher score = more fragile (more likely to break).

    Heuristics:
      - XPath with position indices: very fragile
      - XPath with complex predicates: fragile
      - CSS with deep nesting: somewhat fragile
      - Simple ID or class: robust

    Args:
        selector: CSS selector or XPath string

    Returns:
        Fragility score 0-1
    """
    if not selector:
        return 0.5

    selector_lower = selector.lower()
    fragility = 0.0

    # XPath is generally more fragile than CSS
    if selector.startswith("//") or selector.startswith(".//") or selector.startswith("/"):
        fragility += 0.3
        # Position predicates are very brittle
        if "[" in selector and re.search(r"\[\d+\]", selector):
            fragility += 0.4
        # Complex predicates
        if selector.count("[") > 1:
            fragility += 0.2
    else:
        # CSS selector
        # Deep nesting (many > or spaces)
        nesting_depth = max(selector.count(" "), selector.count(">"))
        fragility += min(nesting_depth * 0.05, 0.2)

        # Attribute selectors with partial matches are fragile
        if re.search(r'\[.*\*=', selector):  # *= (contains)
            fragility += 0.15
        if re.search(r'\[.*\^=', selector):  # ^= (starts with)
            fragility += 0.1

        # ID selectors are most robust
        if selector.startswith("#"):
            fragility = max(0, fragility - 0.2)

    return min(fragility, 1.0)


def compute_frc(
    testcase: Dict[str, Any],
    change_summary: str,
    feedback_history: List[Dict[str, Any]],
) -> float:
    """Compute Failure Risk Coverage (FRC) score.

    Combines four weighted factors into a single score (0-1).

    Factors:
      - Failure History (0.4): Past failure frequency with recency weighting
      - Component Criticality (0.3): How critical the component is
      - Selector Fragility (0.2): How brittle the UI selector is
      - Flakiness (0.1): Explicit flakiness flag

    Args:
        testcase: Testcase dict with 'id', 'component', 'selector', 'flaky'
        change_summary: Code change summary (currently unused, reserved for future)
        feedback_history: List of past feedback entries

    Returns:
        FRC score between 0 and 1 (higher = higher risk)
    """
    # 1. Failure history (0.4 weight)
    failure_history_score = _compute_failure_history_score(testcase, feedback_history)

    # 2. Component criticality (0.3 weight)
    component = testcase.get("component", "")
    component_criticality = _get_component_criticality(component)

    # 3. Selector fragility (0.2 weight)
    selector = testcase.get("selector", "")
    selector_fragility = _compute_selector_fragility_score(selector)

    # 4. Flakiness (0.1 weight)
    flaky = testcase.get("flaky", False)
    flakiness_score = 1.0 if flaky else 0.0

    # Weighted combination
    frc = (
        0.4 * failure_history_score
        + 0.3 * component_criticality
        + 0.2 * selector_fragility
        + 0.1 * flakiness_score
    )

    return round(min(frc, 1.0), 4)


def compute_frc_batch(
    testcases: List[Dict[str, Any]],
    change_summary: str,
    feedback_history: List[Dict[str, Any]],
) -> Dict[int, float]:
    """Compute FRC scores for multiple testcases.

    Args:
        testcases: List of testcase dicts
        change_summary: Code change summary
        feedback_history: List of feedback entries

    Returns:
        Dict mapping testcase ID -> FRC score
    """
    return {tc["id"]: compute_frc(tc, change_summary, feedback_history) for tc in testcases}
