"""
validate.py

Validation runner for the agentic test prioritizer. This script:

1. Loads synthetic testcase datasets (small, medium, large)
2. Extracts ground truth (failing vs passing tests from last_result)
3. Calls the agentic prioritizer to get prioritized order
4. Computes APFD, early fault detection, and baseline comparisons
5. Generates a consolidated HTML report

Usage:
    python validate.py

The script is modular and designed for reuse in Phase 4. Main entry points:
    - validate_dataset(dataset_name, testcases, agentic_order)
    - generate_validation_report(validation_results)
    - main() - orchestrates the full pipeline

"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from datetime import datetime

from validation.validator import APFDValidator
from core.prioritizer import prioritize_tests
from core.feedback import load_feedback

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ----------------------- Dataset loading -------------------------


def load_testcases_from_json(json_path: Path) -> List[Dict[str, Any]]:
    """Load testcases from a JSON file.

    Args:
        json_path: Path to JSON file with testcase list

    Returns:
        List of testcase dictionaries
    """
    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        logger.warning(f"Unexpected JSON structure in {json_path}, expected list")
        return []
    except Exception as exc:
        logger.error(f"Failed to load {json_path}: {exc}")
        return []


def extract_ground_truth(testcases: List[Dict[str, Any]]) -> Set[int]:
    """Extract failing test IDs from testcase last_result.

    Args:
        testcases: List of testcase dicts with 'id' and 'last_result' fields

    Returns:
        Set of test IDs where last_result == 'fail'
    """
    return {tc["id"] for tc in testcases if tc.get("last_result") == "fail"}


def load_datasets() -> Dict[str, List[Dict[str, Any]]]:
    """Load all three testcase datasets.

    Returns:
        Dict mapping dataset name -> list of testcases
    """
    project_root = Path(__file__).parent
    datasets = {}

    dataset_paths = {
        "small": project_root / "data" / "small_testcases.json",
        "medium": project_root / "data" / "medium_testcases.json",
        "large": project_root / "data" / "large_testcases.json",
    }

    for name, path in dataset_paths.items():
        if path.exists():
            testcases = load_testcases_from_json(path)
            if testcases:
                datasets[name] = testcases
                logger.info(f"Loaded {len(testcases)} testcases from {name}")
            else:
                logger.warning(f"No testcases loaded from {name}")
        else:
            logger.warning(f"Dataset not found: {path}")

    return datasets


# ----------------------- Agentic prioritization wrapper -------------------------


def get_agentic_order(testcases: List[Dict[str, Any]]) -> List[int]:
    """Call the agentic prioritizer and return ordered test IDs.

    Args:
        testcases: List of testcase dicts

    Returns:
        List of test IDs in prioritized order
    """
    try:
        # Prepare inputs for prioritizer
        change_summary = "Generic code change for validation."
        feedback_history = load_feedback()

        # Call prioritizer (returns: corrected list, explanations dict, testcases)
        prioritized, _, _ = prioritize_tests(change_summary, feedback_history)

        # Map testcase names back to IDs if needed; assume prioritized is already IDs
        if not prioritized:
            logger.warning("Agentic prioritizer returned empty order, using sequential fallback")
            prioritized = [tc["id"] for tc in testcases]

        return prioritized
    except Exception as exc:
        logger.error(f"Agentic prioritizer failed: {exc}, using sequential fallback")
        return [tc["id"] for tc in testcases]


# ----------------------- Validation computation -------------------------


def validate_dataset(
    dataset_name: str, testcases: List[Dict[str, Any]], agentic_order: List[int]
) -> Dict[str, Any]:
    """Validate a single dataset and compute metrics.

    Args:
        dataset_name: Name of dataset (small, medium, large)
        testcases: List of testcase dicts
        agentic_order: Prioritized order from agentic system

    Returns:
        Dict with validation results including APFD, early detection, baselines
    """
    failing_tests = extract_ground_truth(testcases)
    num_failing = len(failing_tests)
    total_tests = len(testcases)

    if num_failing == 0:
        logger.warning(f"{dataset_name}: No failing tests found; skipping validation")
        return {
            "dataset": dataset_name,
            "total_tests": total_tests,
            "failing_tests": 0,
            "apfd_scores": {},
            "early_fault_detection": {},
            "error": "No failing tests",
        }

    validator = APFDValidator(testcases)

    # Generate a comprehensive report from the validator
    validation_report_data = validator.generate_report(agentic_order, failing_tests)

    # Add dataset name and total/failing tests to the report data
    validation_report_data["dataset"] = dataset_name
    validation_report_data["total_tests"] = total_tests
    validation_report_data["failing_tests"] = num_failing

    return validation_report_data


# ----------------------- HTML Report Generation -------------------------


def generate_validation_report(validation_results: List[Dict[str, Any]]) -> str:
    """Generate a consolidated HTML report from validation results.

    Args:
        validation_results: List of result dicts from validate_dataset()

    Returns:
        HTML string ready to be written to file
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Agentic Test Prioritizer Validation Report</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #f5f7fa;
                padding: 20px;
                color: #333;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px 20px;
                text-align: center;
            }}
            header h1 {{
                font-size: 2.5em;
                margin-bottom: 10px;
            }}
            header p {{
                font-size: 0.95em;
                opacity: 0.9;
            }}
            .content {{
                padding: 40px;
            }}
            .dataset-section {{
                margin-bottom: 40px;
                padding: 20px;
                background: #f9fafb;
                border-left: 4px solid #667eea;
                border-radius: 4px;
            }}
            .dataset-section h2 {{
                color: #667eea;
                margin-bottom: 15px;
                font-size: 1.5em;
            }}
            .metrics-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-bottom: 20px;
            }}
            .metric-card {{
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 15px;
                text-align: center;
            }}
            .metric-label {{
                font-size: 0.85em;
                color: #6b7280;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 8px;
            }}
            .metric-value {{
                font-size: 1.8em;
                font-weight: bold;
                color: #667eea;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                background: white;
                border-radius: 6px;
                overflow: hidden;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            }}
            thead {{
                background: #f3f4f6;
                border-bottom: 2px solid #e5e7eb;
            }}
            th {{
                padding: 12px 15px;
                text-align: left;
                font-weight: 600;
                color: #374151;
                font-size: 0.9em;
            }}
            td {{
                padding: 12px 15px;
                border-bottom: 1px solid #e5e7eb;
            }}
            tbody tr:hover {{
                background: #f9fafb;
            }}
            .score-high {{
                color: #10b981;
                font-weight: bold;
            }}
            .score-medium {{
                color: #f59e0b;
                font-weight: bold;
            }}
            .score-low {{
                color: #ef4444;
                font-weight: bold;
            }}
            footer {{
                background: #f3f4f6;
                padding: 20px;
                text-align: center;
                color: #6b7280;
                font-size: 0.9em;
                border-top: 1px solid #e5e7eb;
            }}
            .summary {{
                background: #ecf0ff;
                border: 1px solid #d6dcff;
                padding: 15px;
                border-radius: 6px;
                margin-bottom: 20px;
            }}
            .summary p {{
                margin: 5px 0;
                font-size: 0.95em;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>🧪 Agentic Test Prioritizer Validation</h1>
                <p>Generated: {timestamp}</p>
            </header>

            <div class="content">
    """

    # Generate section for each dataset
    for result in validation_results:
        dataset = result.get("dataset", "unknown")
        total = result.get("total_tests", 0)
        failing = result.get("failing_tests", 0)
        apfd_scores = result.get("apfd_scores", {})
        efd = result.get("early_fault_detection", {})
        improvement = result.get("improvement_over_random", 0)

        agentic_apfd = apfd_scores.get("agentic_apfd", 0)

        # Color code the APFD score
        if agentic_apfd >= 0.75:
            score_class = "score-high"
        elif agentic_apfd >= 0.5:
            score_class = "score-medium"
        else:
            score_class = "score-low"

        html += f"""
            <div class="dataset-section">
                <h2>Dataset: {dataset.upper()}</h2>
                <div class="summary">
                    <p><strong>Total Tests:</strong> {total}</p>
                    <p><strong>Failing Tests:</strong> {failing}</p>
                    <p><strong>Pass Rate:</strong> {round(100 * (total - failing) / max(1, total), 1)}%</p>
                    <p><strong>Wasted Effort (Passing Tests Before All Faults Found):</strong> {result.get("wasted_effort", "N/A")}</p>
                    <p><strong>Time Saved vs Random:</strong> {result.get("time_saved", "N/A")} seconds</p>
                </div>

                <h3 style="margin-top: 20px; margin-bottom: 10px; font-size: 1.1em; color: #374151;">
                    APFD Scores
                </h3>
                <div class="metrics-grid">
        """

        # APFD metric cards
        for name, score in sorted(apfd_scores.items()):
            score_display = f"{score:.4f}"
            card_class = "score-high" if score >= 0.75 else "score-medium" if score >= 0.5 else "score-low"
            html += f"""
                    <div class="metric-card">
                        <div class="metric-label">{name.replace('_apfd', '')}</div>
                        <div class="metric-value {card_class}">{score_display}</div>
                    </div>
            """

        html += """
                </div>

                <h3 style="margin-top: 20px; margin-bottom: 10px; font-size: 1.1em; color: #374151;">
                    Baseline Comparison (APFD)
                </h3>
                <table>
                    <thead>
                        <tr>
                            <th>Strategy</th>
                            <th>APFD Score</th>
                            <th>vs Agentic</th>
                        </tr>
                    </thead>
                    <tbody>
        """

        agentic = apfd_scores.get("agentic_apfd", 0)
        for strategy in ["random", "fifo", "reverse", "history_based", "risk_based", "flaky_aware"]:
            key = f"{strategy}_apfd"
            score = apfd_scores.get(key, 0)
            diff = agentic - score
            diff_text = f"+{diff:.4f}" if diff > 0 else f"{diff:.4f}"
            html += f"""
                        <tr>
                            <td><strong>{strategy.replace('_', ' ').title()}</strong></td>
                            <td>{score:.4f}</td>
                            <td class="{'score-high' if diff > 0 else 'score-low'}">{diff_text}</td>
                        </tr>
            """

        html += """
                    </tbody>
                </table>

                <h3 style="margin-top: 20px; margin-bottom: 10px; font-size: 1.1em; color: #374151;">
                    Early Fault Detection (% of Failures by Position K)
                </h3>
                <table>
                    <thead>
                        <tr>
                            <th>Position K</th>
                            <th>% Failures Detected (Agentic)</th>
                            <th>% Failures Detected (Random)</th>
                        </tr>
                    </thead>
                    <tbody>
        """

        # Early Fault Detection data from the result dict
        efd_agentic = result.get("early_fault_detection_agentic", {})
        efd_random = result.get("early_fault_detection_random", {})

        # Get all unique K values from both
        all_k_values = sorted(list(set(efd_agentic.keys()) | set(efd_random.keys())))

        for k in all_k_values:
            pct_agentic = efd_agentic.get(k, 0.0)
            pct_random = efd_random.get(k, 0.0)
            
            # Color code for agentic vs random comparison
            agentic_class = "score-high" if pct_agentic >= pct_random else "score-low"

            html += f"""
                        <tr>
                            <td><strong>First {k} tests</strong></td>
                            <td class="{agentic_class}">{pct_agentic:.1f}%</td>
                            <td>{pct_random:.1f}%</td>
                        </tr>
            """
        
        # Add the failing tests found earlier metric
        failing_tests_early = result.get("failing_tests_found_earlier_top_20_percent", {})
        html += f"""
                        <tr>
                            <td><strong>Failing Tests Found Earlier (Top 20%)</strong></td>
                            <td class="score-high">Agentic: {failing_tests_early.get("agentic", "N/A")}</td>
                            <td>Random: {failing_tests_early.get("random", "N/A")}</td>
                        </tr>
            """

        html += """
                    </tbody>
                </table>
            </div>
        """

    html += """
            </div>

            <footer>
                <p><strong>Agentic Test Prioritizer</strong> | Phase 3 Validation Report</p>
                <p>This report compares agentic ordering against random, history-based, risk-based, and flaky-aware baselines.</p>
            </footer>
        </div>
    </body>
    </html>
    """

    # Save the report and return path (don't return html string)
    if validation_results:
        dataset_name = validation_results[0].get("dataset", "validation")
        report_path = save_html_report(html, dataset_name)
        return report_path
    else:
        return Path("unknown")


def save_html_report(html_content: str, dataset_name: str = "validation", output_path: Optional[Path] = None) -> Path:
    """Save HTML report to file.

    Args:
        html_content: HTML string
        dataset_name: Name of dataset for filename
        output_path: Path to output file (default: validation report directory)

    Returns:
        Path to saved report
    """
    if output_path is None:
        # Create report in dataset-specific folder
        report_dir = Path("D:/PBL/reports") / dataset_name.lower()
        report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_path = report_dir / f"validation_report_{timestamp}.html"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"Validation HTML report saved to: {output_path}")
    return output_path


# ----------------------- Main orchestration -------------------------


def main() -> int:
    """Main validation pipeline.

    Steps:
    1. Load datasets
    2. Get agentic order for each
    3. Validate and compute metrics
    4. Generate HTML report
    """
    logger.info("Starting validation pipeline...")

    # Load datasets
    datasets = load_datasets()
    if not datasets:
        logger.error("No datasets found. Exiting.")
        return 1

    validation_results = []

    # Validate each dataset
    for dataset_name, testcases in datasets.items():
        logger.info(f"Validating {dataset_name} dataset ({len(testcases)} tests)...")

        # Get agentic order
        agentic_order = get_agentic_order(testcases)

        # Validate
        result = validate_dataset(dataset_name, testcases, agentic_order)
        validation_results.append(result)

        logger.info(
            f"  Agentic APFD: {result['apfd_scores'].get('agentic_apfd', 'N/A')} | "
            f"Improvement vs random: {result['improvement_over_random']}"
        )

    # Generate report
    logger.info("Generating HTML report...")
    html = generate_validation_report(validation_results)
    report_path = save_html_report(html)

    logger.info(f"Validation complete. Report: {report_path}")
    return 0


if __name__ == "__main__":
    exit(main())
