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

    # Only show top 10 tests
    top_10 = final_list[:10]
    remaining_count = len(final_list) - 10 if len(final_list) > 10 else 0

    for rank, test_id in enumerate(top_10, start=1):
        tc = next(tc for tc in testcases if tc["id"] == test_id)
        score = risk_scores[test_id]
        reason = reasons[test_id]

        print("{: <6} {: <8} {: <8} {: <40}".format(
            rank, test_id, risk_label(score), reason
        ))

    if remaining_count > 0:
        print(f"... and {remaining_count} more tests")

    print("-" * 70 + "\n")
