def risk_label(score):
    if score >= 8:
        return "High"
    elif score >= 4:
        return "Medium"
    else:
        return "Low"


def print_priority_table(final_list, testcases, risk_scores, reasons):
    print("\n" + "-" * 70)
    print("{: <6} {: <8} {: <8} {: <40}".format("Rank", "TestID", "Risk", "Reason"))
    print("-" * 70)

    for rank, test_id in enumerate(final_list, start=1):
        tc = next(tc for tc in testcases if tc["id"] == test_id)
        score = risk_scores[test_id]
        reason = reasons[test_id]

        print("{: <6} {: <8} {: <8} {: <40}".format(
            rank, test_id, risk_label(score), reason
        ))

    print("-" * 70 + "\n")
