"""
validator.py

Evaluates the performance of an agentic test prioritizer by computing:

1. APFD (Average Percentage of Faults Detected) - industry standard metric
2. Early Fault Detection - percentage of failures caught in first K tests
3. Baseline orderings - random, history-based, risk-based, flaky-aware
4. Comparative analysis - agentic vs. all baselines

The module works with standard testcase JSON schema:
{
  "id": int,
  "name": str,
  "component": str,
  "ui_element": str,
  "selector": str,
  "execution_time": float,
  "last_result": str,
  "flaky": bool
}

Usage example:
    validator = APFDValidator(testcases)
    agentic_order = [1, 2, 4, 5, 3, 6]
    failing_tests = {2, 5}
    apfd = validator.compute_apfd(agentic_order, failing_tests)
    report = validator.compare_against_baselines(agentic_order, failing_tests)

"""
from __future__ import annotations

import random
from typing import Dict, List, Set, Tuple, Any, Optional


class APFDValidator:
    """Validates test prioritization ordering using APFD and baseline comparisons."""

    def __init__(self, testcases: List[Dict[str, Any]]):
        """Initialize with a list of testcase dictionaries.

        Args:
            testcases: List of dicts with 'id', 'last_result', 'flaky', etc.
        """
        self.testcases = testcases
        self.testcase_map = {tc["id"]: tc for tc in testcases}

    def compute_apfd(self, prioritized_order: List[int], failing_tests: Set[int]) -> float:
        """Compute APFD (Average Percentage of Faults Detected).

        APFD measures how quickly a prioritized test order detects failures.
        Higher is better (0-1 scale).

        Formula:
            APFD = 1 - (sum(TFi) / (n*m)) + (1/(2*n))

        where:
            TFi = position of the ith failing test in the prioritized order
            n = total number of tests
            m = number of failing tests

        Args:
            prioritized_order: List of test IDs in prioritized order
            failing_tests: Set of test IDs that are known to fail

        Returns:
            APFD score between 0 and 1 (higher is better)
        """
        if not failing_tests:
            return 1.0

        n = len(prioritized_order)
        m = len(failing_tests)

        if m == 0 or n == 0:
            return 1.0

        # Find positions of failing tests (1-indexed)
        positions_of_failures = []
        for rank, test_id in enumerate(prioritized_order, start=1):
            if test_id in failing_tests:
                positions_of_failures.append(rank)

        # Sum of positions
        sum_positions = sum(positions_of_failures)

        # APFD formula
        apfd = 1 - (sum_positions / (n * m)) + (1 / (2 * n))
        return round(apfd, 4)

    def early_fault_detection(
        self, prioritized_order: List[int], failing_tests: Set[int], k_values: Optional[List[int]] = None
    ) -> Dict[int, float]:
        """Compute percentage of failing tests detected in first K positions.

        This metric shows how quickly failures are caught at different early stages.

        Args:
            prioritized_order: List of test IDs in prioritized order
            failing_tests: Set of test IDs that fail
            k_values: List of K positions to evaluate (default: [5, 10])

        Returns:
            Dict mapping K -> percentage (0-100) of failures caught by position K
        """
        if k_values is None:
            k_values = [5, 10]

        if not failing_tests:
            return {k: 100.0 for k in k_values}

        results = {}
        for k in k_values:
            # Get first k tests
            first_k = set(prioritized_order[:k])
            # Count how many failures are in first k
            failures_in_k = len(first_k & failing_tests)
            # Percentage
            percentage = (failures_in_k / len(failing_tests)) * 100
            results[k] = round(percentage, 2)

        return results

    def precision_at_k(
        self, prioritized_order: List[int], failing_tests: Set[int], k_values: Optional[List[int]] = None
    ) -> Dict[int, float]:
        """Compute the density of failures in the top K positions.
        
        Precision@K answers: "Of the tests we ran, how many were useful (failing)?"
        High precision builds trust that the agent isn't wasting resources.
        """
        if k_values is None:
            k_values = [5, 10]
            
        results = {}
        for k in k_values:
            # Avoid division by zero
            if k == 0:
                results[k] = 0.0
                continue
                
            first_k = set(prioritized_order[:k])
            failures_in_k = len(first_k & failing_tests)
            precision = (failures_in_k / k) * 100
            results[k] = round(precision, 2)
            
        return results

    def generate_baseline_orderings(self) -> Dict[str, List[int]]:
        """Generate baseline test orderings for comparison.

        Returns:
            Dict with keys: 'random', 'history_based', 'risk_based', 'flaky_aware'
            Each value is a list of test IDs in the baseline order
        """
        ids = [tc["id"] for tc in self.testcases]

        # 1. Random ordering
        random_order = ids.copy()
        random.shuffle(random_order)

        # 2. FIFO (First-In, First-Out) / Original order
        fifo_order = ids.copy() # Assuming `ids` are already in their original extraction order

        # 3. Reverse Order (Worst-case)
        reverse_order = ids[::-1] # Reverse the original order

        # 4. History-based: sort by pass rate (tests that failed more recently come first)
        history_order = sorted(
            ids,
            key=lambda tid: (
                self.testcase_map[tid]["last_result"] != "fail",  # failures first
                random.random(),  # secondary: random tie-breaker
            ),
        )

        # 5. Risk-based: sort by execution time (faster tests first)
        risk_order = sorted(ids, key=lambda tid: self.testcase_map[tid]["execution_time"])

        # 6. Flaky-aware: sort flaky tests first (they need more validation)
        flaky_order = sorted(
            ids,
            key=lambda tid: (
                not self.testcase_map[tid]["flaky"],  # flaky tests first (False < True)
                self.testcase_map[tid]["last_result"] != "fail",  # then failures
            ),
        )

        return {
            "random": random_order,
            "fifo": fifo_order,
            "reverse": reverse_order,
            "history_based": history_order,
            "risk_based": risk_order,
            "flaky_aware": flaky_order,
        }

    def compare_against_baselines(
        self, agentic_order: List[int], failing_tests: Set[int]
    ) -> Dict[str, float]:
        """Compute APFD for agentic order + all baseline orderings.

        This is the main evaluation function: it runs the prioritizer against
        standard baselines and returns comparative metrics.

        Args:
            agentic_order: Prioritized order from the agentic system
            failing_tests: Set of test IDs that actually fail

        Returns:
            Dict mapping ordering name -> APFD score
            Example:
            {
                "agentic_apfd": 0.82,
                "random_apfd": 0.51,
                "history_apfd": 0.66,
                "risk_apfd": 0.70,
                "flaky_aware_apfd": 0.60
            }
        """
        baselines = self.generate_baseline_orderings()

        results = {
            "agentic_apfd": self.compute_apfd(agentic_order, failing_tests),
        }

        for name, order in baselines.items():
            apfd = self.compute_apfd(order, failing_tests)
            results[f"{name}_apfd"] = apfd

        return results

    def generate_report(
        self, agentic_order: List[int], failing_tests: Set[int], k_values: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Generate a comprehensive evaluation report.

        Combines APFD, early fault detection, and baseline comparison into
        a single report dictionary, including new metrics.

        Args:
            agentic_order: Prioritized order from agentic system
            failing_tests: Set of failing test IDs
            k_values: List of K positions to evaluate for early fault detection (default: [5, 10, 20])

        Returns:
            Comprehensive report dict with APFD, EFD, new metrics, and baseline comparisons
        """
        if k_values is None:
            k_values = [int(len(self.testcases) * 0.1), int(len(self.testcases) * 0.2), int(len(self.testcases) * 0.3)]
            k_values = [k for k in k_values if k > 0] or [1]

        apfd_scores = self.compare_against_baselines(agentic_order, failing_tests)
        early_detection = self.early_fault_detection(agentic_order, failing_tests, k_values)
        precision_scores = self.precision_at_k(agentic_order, failing_tests, k_values)
        wasted_effort = self.calculate_wasted_effort(agentic_order, failing_tests)
        
        # Need random order for time saved and failing tests found earlier comparison
        baselines = self.generate_baseline_orderings()
        random_order = baselines.get("random", [])

        time_saved = self.calculate_time_saved(agentic_order, random_order, failing_tests)
        failing_tests_early = self.get_failing_tests_found_earlier(agentic_order, random_order, failing_tests, k_percent=0.2)
        
        # Calculate Lift (Factor of improvement)
        rand_score = apfd_scores.get("random_apfd", 0.001)
        if rand_score <= 0: rand_score = 0.001
        lift_factor = round(apfd_scores["agentic_apfd"] / rand_score, 2)

        return {
            "apfd_scores": apfd_scores,
            "early_fault_detection": early_detection,
            "precision_at_k": precision_scores,
            "wasted_effort": wasted_effort,
            "time_saved": time_saved,
            "lift_factor": lift_factor,
            "failing_tests_found_earlier_top_20_percent": failing_tests_early,
            "total_tests": len(self.testcases),
            "failing_tests": len(failing_tests),
            "agentic_apfd": apfd_scores["agentic_apfd"],
            "random_apfd": apfd_scores.get("random_apfd", 0),
            "improvement_over_random": round(
                apfd_scores["agentic_apfd"] - apfd_scores.get("random_apfd", 0), 4
            ),
        }

    def _get_execution_time(self, test_id: int) -> float:
        """Helper to get execution time for a given test ID."""
        return self.testcase_map.get(test_id, {}).get("execution_time", 1.0) # Default to 1 if not found

    def calculate_time_to_find_all_faults(self, order: List[int], failing_tests: Set[int]) -> float:
        """Calculates the cumulative execution time until all failing tests are found."""
        if not failing_tests:
            return 0.0

        current_time = 0.0
        faults_found = set()
        for test_id in order:
            current_time += self._get_execution_time(test_id)
            if test_id in failing_tests:
                faults_found.add(test_id)
            if faults_found == failing_tests:
                return current_time
        return current_time # If not all faults are found, return total time to run all tests in order

    def calculate_wasted_effort(self, prioritized_order: List[int], failing_tests: Set[int]) -> int:
        """
        Calculates the number of 'useless' (passing) tests executed before all faults are found.
        A lower number indicates less wasted effort.
        """
        if not failing_tests:
            return 0

        wasted_count = 0
        faults_found_count = 0
        for test_id in prioritized_order:
            if test_id in failing_tests:
                faults_found_count += 1
            else:
                wasted_count += 1

            if faults_found_count == len(failing_tests):
                break
        return wasted_count

    def calculate_time_saved(self, agentic_order: List[int], random_order: List[int], failing_tests: Set[int]) -> float:
        """
        Calculates the time saved by the agentic prioritization compared to a random baseline.
        Positive value means time was saved.
        """
        agentic_time = self.calculate_time_to_find_all_faults(agentic_order, failing_tests)
        random_time = self.calculate_time_to_find_all_faults(random_order, failing_tests)
        return round(random_time - agentic_time, 2)

    def get_failing_tests_found_earlier(self, agentic_order: List[int], random_order: List[int], failing_tests: Set[int], k_percent: float = 0.2) -> Dict[str, int]:
        """
        Compares how many failing tests are found earlier (within top K% of tests) by agentic vs random.
        Returns a dict with counts for agentic and random.
        """
        total_tests = len(self.testcases)
        k_count = int(total_tests * k_percent)
        if k_count == 0:
            return {"agentic": 0, "random": 0}

        agentic_early_faults = len(set(agentic_order[:k_count]).intersection(failing_tests))
        random_early_faults = len(set(random_order[:k_count]).intersection(failing_tests))
        
        return {"agentic": agentic_early_faults, "random": random_early_faults}


# ----------------------- Convenience functions -----------------------


def compute_apfd(prioritized_order: List[int], failing_tests: Set[int], total_tests: int) -> float:
    """Standalone APFD computation (no testcase metadata required).

    This is a simpler interface if you only have ordered IDs and failure info.

    Args:
        prioritized_order: List of test IDs in order
        failing_tests: Set of test IDs that fail
        total_tests: Total number of tests

    Returns:
        APFD score (0-1, higher is better)
    """
    if not failing_tests or total_tests == 0:
        return 1.0

    n = total_tests
    m = len(failing_tests)

    # Find positions of failures (1-indexed)
    positions = []
    for rank, test_id in enumerate(prioritized_order, start=1):
        if test_id in failing_tests:
            positions.append(rank)

    sum_positions = sum(positions)
    apfd = 1 - (sum_positions / (n * m)) + (1 / (2 * n))
    return round(apfd, 4)


def early_fault_detection_simple(
    prioritized_order: List[int], failing_tests: Set[int], k: int = 5
) -> float:
    """Standalone early fault detection at position K.

    Args:
        prioritized_order: List of test IDs in order
        failing_tests: Set of test IDs that fail
        k: Number of tests to check

    Returns:
        Percentage (0-100) of failures in first K tests
    """
    if not failing_tests:
        return 100.0

    first_k = set(prioritized_order[:k])
    caught = len(first_k & failing_tests)
    return round((caught / len(failing_tests)) * 100, 2)
