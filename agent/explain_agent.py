import google.generativeai as genai
import ast
import re

class ExplainAgent:
    def __init__(self):
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def explain(self, final_ranking, testcases, change_summary):
        prompt = f"""
You are an AI test analyst.

STRICT OUTPUT RULE:
- Output ONLY a valid Python dictionary
- Keys MUST be strings
- Format EXACTLY like this: {{"1": "reason", "2": "reason"}}
- NO markdown, NO ``` blocks, NO explanation outside the dict.

Test Order: {final_ranking}
Testcases: {testcases}
Code/UI Change Summary: {change_summary}

For EACH test ID in the ranking, give ONE sentence explaining why it got that priority.

OUTPUT ONLY THE PYTHON DICT.
"""
        response = self.model.generate_content(prompt)
        text = response.text.strip()

        # 1. Remove code blocks if Gemini adds them
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL).strip()

        # 2. Try strict parsing
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, dict):
                # force string keys
                return {str(k): v for k, v in parsed.items()}
        except Exception:
            pass

        # 3. Fallback: create generic meaningful explanations
        fallback = {
            str(tc["id"]): (
                "AI could not generate explanation due to formatting errors, "
                "but this test was ranked based on its risk score and LLM priority."
            )
            for tc in testcases
        }
        return fallback
