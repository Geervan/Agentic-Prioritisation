import json
from pathlib import Path
from typing import Any, Dict, List
import ast
from agent.explain_agent import ExplainAgent
from core.scoring import compute_risk_score
from agent.critic_agent import CriticAgent
from agent.agent import TestAgent
from core.display import print_priority_table
from agent.planner_agent import PlannerAgent


def load_testcases() -> List[Dict[str, Any]]:
    """Load testcases from data/testcases.json."""
    base = Path(__file__).resolve().parent.parent
    path = base / "data" / "testcases.json"
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def parse_llm_output(text: str) -> List[int]:
    """Safely parse LLM output like '[1, 2, 3]' into a Python list."""
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [int(x) for x in parsed if isinstance(x, int) or str(x).isdigit()]
    except Exception:
        pass
    return []


def prioritize_tests(change_summary: str, feedback_history: List[Dict[str, Any]]):
    # Load testcases
    testcases = load_testcases()
    agent = TestAgent(testcases)

    # 1. LLM prioritization
    raw_output = agent.prioritize(change_summary, feedback_history)
    llm_priority = parse_llm_output(raw_output)

    # 2. Risk scoring + reason collection
    scored = []
    risk_scores = {}
    risk_reasons = {}

    for tc in testcases:
        score, reason = compute_risk_score(tc, change_summary, feedback_history)
        risk_scores[tc["id"]] = score
        risk_reasons[tc["id"]] = reason
        scored.append((tc["id"], score))

    # 3. Sort by score + secondary LLM reasoning
    final_ranking = sorted(
        scored,
        key=lambda x: (
            x[1],
            llm_priority.index(x[0]) if x[0] in llm_priority else 999
        ),
        reverse=True
    )

    corrected = [tc_id for tc_id, _ in final_ranking]

    # 4. Critic agent improves ordering
    critic = CriticAgent(testcases)
    corrected = critic.critique(corrected, change_summary)

    # 5. Display readable table
    print_priority_table(corrected, testcases, risk_scores, risk_reasons)

    # 6. Explanation agent
    explainer = ExplainAgent()
    explanations_dict = explainer.explain(corrected, testcases, change_summary)
    #print("Explanation of Prioritization:\n", explanations_dict)

    # 7. Planner agent
    planner = PlannerAgent()
    strategy = planner.decide_strategy(change_summary, feedback_history)
    print("Planned Testing Strategy:\n", strategy)

    # Return everything needed for reports
    return corrected, explanations_dict, testcases
