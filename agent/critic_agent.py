class CriticAgent:
    def __init__(self, testcases):
        self.testcases = {tc["id"]: tc for tc in testcases}

    def critique(self, prioritized_list, change_summary):
        corrected = []

        for test_id in prioritized_list:
            tc = self.testcases[test_id]

            # If test is unrelated to changed component → penalize
            if tc["component"].lower() not in change_summary.lower():
                corrected.append((test_id, -5))
            else:
                corrected.append((test_id, 0))

        # Sort so unrelated tests move down
        corrected_sorted = sorted(corrected, key=lambda x: x[1], reverse=True)
        return [tid for tid, _ in corrected_sorted]
