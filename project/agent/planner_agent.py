import google.generativeai as genai

class PlannerAgent:
    def __init__(self):
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def decide_strategy(self, change_summary, feedback_summary):
        prompt = f"""
        You are a test planning expert.

        Change Summary:
        {change_summary}

        Feedback Summary:
        {feedback_summary}

        Decide which strategy to use:
        - HIGH_RISK_FIRST
        - FAILURE_HISTORY_WEIGHTED
        - UI_COMPONENT_SENSITIVE
        - FAST_TESTS_FIRST

        Return only the strategy name.
        """

        response = self.model.generate_content(prompt)
        return response.text.strip()
