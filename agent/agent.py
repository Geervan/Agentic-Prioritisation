import json
import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

class TestAgent:
    def __init__(self, testcases):
        self.testcases = testcases
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def prioritize(self, change_summary, feedback_history):
        prompt = f"""
        You are an autonomous agent that prioritizes GUI regression test cases.

        Testcases:
        {json.dumps(self.testcases, indent=2)}

        Recent code changes:
        {change_summary}

        Past feedback:
        {json.dumps(feedback_history, indent=2)}

        Rules:
        - Rank test case IDs by how likely they are affected by the change.
        - Consider UI component, selector, last failures, and execution time.
        - Output ONLY a Python list of integers. No text.
        """

        response = self.model.generate_content(prompt)
        return response.text
