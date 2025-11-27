"""
main.py

Main orchestration script for the agentic test prioritizer.
Automatically extracts testcases if missing, runs prioritization,
and saves feedback to memory.json.

Usage:
    python main.py                    # Auto-extract + run
    python main.py --dataset medium   # Extract & run on medium dataset
    python main.py --fixture          # Use fixture only (no extraction)
    python main.py --no-extract       # Use existing data only
"""
from __future__ import annotations

import argparse
import json
import logging
import random
from pathlib import Path
import time
from typing import Dict, Optional

from core.prioritizer import prioritize_tests
from core.feedback import load_feedback, save_feedback
from core.report import generate_html_report
from validate import validate_dataset, generate_validation_report

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
APPS_DIR = PROJECT_ROOT / "apps"
REPORT_DIR = Path("D:/PBL/reports")  # Root reports directory
REPORT_DIR.mkdir(exist_ok=True)  # Ensure it exists

DATASET_PATHS = {
    "small": DATA_DIR / "small_testcases.json",
    "medium": DATA_DIR / "medium_testcases.json",
}

APP_ROOTS = {
    "small": APPS_DIR / "sample-app-web",
    "medium": APPS_DIR / "the-internet",
}

FIXTURE_TESTCASES = DATA_DIR / "testcases.json"


# ----------------------- Auto-extraction -------------------------

def auto_extract_if_missing(skip_extraction: bool = False) -> bool:
    """Auto-extract datasets if they don't exist."""
    if skip_extraction:
        logger.info("Skipping extraction (--no-extract)")
        return all(p.exists() for p in DATASET_PATHS.values())
    
    any_missing = any(not p.exists() for p in DATASET_PATHS.values())
    if not any_missing:
        logger.info("All datasets exist; skipping extraction")
        return True
    
    logger.info("Auto-extracting missing datasets...")
    
    # Process each dataset
    for dataset_key, dataset_path in DATASET_PATHS.items():
        if dataset_key == "large":
            continue  # Skip large dataset extraction as requested
            
        should_extract = not dataset_path.exists()
        if dataset_path.exists():
            try:
                with dataset_path.open() as f:
                    data = json.load(f)
                    if len(data) == 0:
                        should_extract = True
                        logger.info(f"Dataset {dataset_key} is empty, re-extracting.")
            except Exception:
                should_extract = True
                logger.info(f"Dataset {dataset_key} is corrupted or unreadable, re-extracting.")
        
        if should_extract and APP_ROOTS[dataset_key].exists():
            try:
                if dataset_key == "small":
                    logger.info("Extracting SauceDemo tests (small)...")
                    from extraction.extract_saucedemo_tests import main as extract_saucedemo
                    extract_saucedemo(str(APP_ROOTS[dataset_key]), str(DATASET_PATHS[dataset_key]))
                elif dataset_key == "medium":
                    logger.info("Extracting The Internet tests (medium)...")
                    from extraction.extract_theinternet_tests import main as extract_theinternet
                    extract_theinternet(str(APP_ROOTS[dataset_key]), str(DATASET_PATHS[dataset_key]))
                elif dataset_key == "large":
                    logger.info("Extracting Moodle tests (large)...")
                    from extraction.extract_moodle_phpunit_tests import main as extract_moodle_phpunit
                    extract_moodle_phpunit(argv=[str(APP_ROOTS[dataset_key]), "--out", str(DATASET_PATHS[dataset_key])])
            except Exception as exc:
                logger.warning(f"Failed to extract {dataset_key} dataset: {exc}")
    
    return any(p.exists() for p in DATASET_PATHS.values())


def load_dataset(dataset_name: str, use_fixture: bool = False) -> Optional[list]:
    """Load a single dataset by name."""
    if use_fixture and FIXTURE_TESTCASES.exists():
        logger.info("Loading fixture (testcases.json)...")
        with FIXTURE_TESTCASES.open() as f:
            return json.load(f)
    
    path = DATASET_PATHS.get(dataset_name)
    if not path or not path.exists():
        logger.error(f"Dataset '{dataset_name}' not found at {path}")
        return None
    
    with path.open() as f:
        testcases = json.load(f)
    logger.info(f"Loaded {len(testcases)} {dataset_name} testcases")
    return testcases


# ----------------------- Main pipeline -------------------------

def format_validation_table(validation_result: Dict, dataset_name: str) -> str:
    """Format validation results as a readable terminal table.
    
    Args:
        validation_result: Dict from validate_dataset()
        dataset_name: Name of dataset
        
    Returns:
        Formatted string ready for terminal output
    """
    output = []
    output.append("\n" + "="*60)
    output.append(f"VALIDATION: {dataset_name.upper()} APPLICATION")
    output.append("="*60)
    
    if "error" in validation_result:
        output.append(f"⚠ {validation_result['error']}")
        return "\n".join(output)
    
    apfd_scores = validation_result.get("apfd_scores", {})
    early_detection = validation_result.get("early_fault_detection", {})
    wasted_effort = validation_result.get("wasted_effort", 0)
    time_saved = validation_result.get("time_saved", 0.0)
    
    # APFD Scores
    agentic_apfd = apfd_scores.get("agentic_apfd", 0)
    random_apfd = apfd_scores.get("random_apfd", 0)
    fifo_apfd = apfd_scores.get("fifo_apfd", 0)
    
    output.append(f"APFD (Agentic AI): {agentic_apfd:.4f}")
    output.append(f"APFD (Random):     {random_apfd:.4f}")
    output.append(f"APFD (Original):   {fifo_apfd:.4f}")
    
    # Early Fault Detection
    if early_detection:
        output.append("\nEarly Fault Detection:")
        for k in sorted(early_detection.keys()):
            k_percent = round(100 * k / max(1, validation_result.get("total_tests", 1)), 1)
            # Get baseline detection counts
            baseline = validation_result.get("failing_tests_found_earlier_top_20_percent", {})
            output.append(f"{k_percent:.0f}% -> AI: {early_detection[k]:.2f}%")
    
    # Wasted Effort and Time Saved
    output.append(f"\nWasted Effort: {wasted_effort} passing tests")
    output.append(f"Time Saved vs Random: {time_saved:.2f} seconds")
    output.append("="*60 + "\n")
    
    return "\n".join(output)


def run_prioritization(testcases: list, dataset_name: str, enable_validation: bool = False) -> None:
    """Run the full prioritization pipeline on a dataset."""
    if not testcases:
        logger.error(f"No testcases to prioritize for {dataset_name}")
        return
    
    logger.info(f"Running prioritizer on {dataset_name} ({len(testcases)} tests)...")
    
    # Define synthetic code change
    change_summary = f"Modified authentication and payment flow in {dataset_name} app"
    
    # Load feedback history (dataset-specific)
    feedback_history = load_feedback(dataset_name)
    logger.info(f"Loaded {len(feedback_history)} historical feedback entries from {dataset_name} dataset")
    
    # Get prioritized order
    num_retries = 3
    for attempt in range(num_retries):
        try:
            prioritized_ids, explanations_dict, _ = prioritize_tests(change_summary, feedback_history, testcases=testcases)
            logger.info(f"Agentic prioritizer returned {len(prioritized_ids)} test IDs")
            break # Exit loop if successful
        except Exception as exc:
            if "ResourceExhausted" in str(exc) and attempt < num_retries - 1:
                retry_delay = 60 * (2 ** attempt) # Exponential backoff
                logger.warning(f"Rate limit exceeded. Retrying in {retry_delay} seconds (Attempt {attempt + 1}/{num_retries})...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Prioritization failed for {dataset_name}: {exc}")
                return
    
    # Run validation FIRST if requested (so we display it before test cases)
    validation_result = None
    if enable_validation:
        try:
            validation_result = validate_dataset(dataset_name, testcases, prioritized_ids)
            
            # Print validation table to terminal (BEFORE test cases)
            validation_table = format_validation_table(validation_result, dataset_name)
            print(validation_table)
        except Exception as exc:
            logger.error(f"Validation failed: {exc}")
    
    # Print prioritized test order (top 10 only)
    print(f"\nPrioritized test order ({dataset_name}):")
    print(f"   Top 10: {prioritized_ids[:10]}")
    if len(prioritized_ids) > 10:
        print(f"   ... and {len(prioritized_ids) - 10} more tests\n")
    else:
        print()
    
    # Simulate test execution with REALISTIC FLAKINESS
    # High-risk tests (Login/Checkout) fail 60% of the time
    # Other tests fail 5% of the time (baseline noise)
    sample_size = len(prioritized_ids)
    test_map = {tc["id"]: tc for tc in testcases}
    results = {}
    
    for test_id in prioritized_ids[:sample_size]:
        tc = test_map.get(test_id, {})
        base_result = tc.get("last_result", "pass")
        
        # Determine if this is a high-risk test (Login/Checkout)
        test_name = tc.get("name", "").lower()
        component = tc.get("component", "").lower()
        is_high_risk = "login" in test_name or "checkout" in test_name or "login" in component or "checkout" in component
        
        # Apply flakiness probability
        if base_result == "fail":
            # Tests marked as "fail" have a chance to actually fail
            fail_probability = 0.60 if is_high_risk else 0.05
        else:
            # Tests marked as "pass" rarely fail (noise)
            fail_probability = 0.05 if is_high_risk else 0.01
        
        # Simulate execution with flakiness
        actual_result = "fail" if random.random() < fail_probability else "pass"
        results[test_id] = actual_result
    
    passed = sum(1 for r in results.values() if r == "pass")
    logger.info(f"Simulated execution: {passed}/{sample_size} passed (with realistic flakiness)")
    
    # Save results to dataset-specific memory file
    for test_id, result_status in results.items():
        save_feedback(test_id, {"status": result_status}, dataset_name)
    logger.info(f"Feedback saved to {dataset_name}_memory.json")
    
    # Generate HTML report (with validation data if available)
    report_path = generate_html_report(testcases, prioritized_ids, explanations_dict, dataset_name, validation_result)
    logger.info(f"Report generated at {report_path}")


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Agentic test prioritizer with auto-extraction"
    )
    p.add_argument(
        "--dataset",
        default="small",
        choices=["small", "medium", "large"],
        help="Which dataset to prioritize (default: small)",
    )
    p.add_argument(
        "--fixture",
        action="store_true",
        help="Use fixture mode (testcases.json) only",
    )
    p.add_argument(
        "--no-extract",
        action="store_true",
        help="Skip auto-extraction; use existing data only",
    )
    p.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip validation suite (runs by default)",
    )
    return p


def main() -> int:
    parser = build_cli()
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Agentic Test Prioritizer")
    logger.info("=" * 60)

    # Auto-extract if needed
    if not args.fixture:
        auto_extract_if_missing(skip_extraction=args.no_extract)

    # Iterate through all datasets and run prioritization
    for dataset_name in DATASET_PATHS.keys():
        if dataset_name == "large":
            logger.info("Skipping 'large' dataset due to rate limit concerns.")
            continue

        testcases = load_dataset(dataset_name, use_fixture=args.fixture)
        if not testcases:
            logger.error(f"No testcases available for dataset '{dataset_name}'. Skipping.")
            continue

        run_prioritization(testcases, dataset_name, enable_validation=not args.no_validate)

    logger.info("=" * 60)
    logger.info("✅ Pipeline complete!")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    exit(main())
