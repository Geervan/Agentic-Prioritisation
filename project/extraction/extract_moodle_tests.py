"""
extract_moodle_tests.py

Extract lightweight testcase metadata from Moodle Selenium test suite.
Scans Java test files under the Moodle project, extracts @Test methods,
UI selectors, and synthetic metadata, then writes to data/large_testcases.json.

This script is tailored for Moodle's test structure and generates the
"large" dataset for agentic test prioritization.

Usage:
    python extraction/extract_moodle_tests.py /path/to/moodle/tests
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# Reuse helpers from Cypress extractor
import sys
sys.path.insert(0, str(Path(__file__).parent))
from extract_cypress_tests import (
    infer_ui_element,
    generate_last_result,
    write_small_testcases,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ----------------------- Java selector extraction -------------------------


def extract_selectors_from_java(java_text: str) -> List[str]:
    """Extract literal selector strings from Java Selenium code."""
    patterns = [
        r'By\.id\(\s*(["\'])(.*?)\1\s*\)',
        r'By\.cssSelector\(\s*(["\'])(.*?)\1\s*\)',
        r'By\.xpath\(\s*(["\'])(.*?)\1\s*\)',
        r'By\.className\(\s*(["\'])(.*?)\1\s*\)',
        r'By\.name\(\s*(["\'])(.*?)\1\s*\)',
    ]

    selectors: List[str] = []
    for pat in patterns:
        for m in re.finditer(pat, java_text, flags=re.DOTALL):
            sel = m.group(2).strip() if m.lastindex >= 2 else None
            if sel:
                selectors.append(sel)

    # Deduplicate preserving order
    seen = set()
    uniq = []
    for s in selectors:
        if s not in seen:
            uniq.append(s)
            seen.add(s)
    return uniq


def infer_ui_element_java(selector: str) -> str:
    """Infer UI element type for Java selectors."""
    s = selector.strip()
    if s.startswith("//") or s.startswith(".//") or s.startswith("/"):
        low = s.lower()
        if re.search(r"//?\w*button\b", low) or "@type='submit'" in low or "@type=\"submit\"" in low:
            return "button"
        if re.search(r"//?\w*(input|textarea|select)\b", low) or "@type='text'" in low:
            return "input"
        if re.search(r"//?\w*a\b", low) or "@href" in low:
            return "link"
        return "unknown"
    return infer_ui_element(selector)


def generate_synthetic_results() -> Tuple[float, str, bool]:
    """Generate synthetic execution_time (1-6s), last_result and flaky flag."""
    execution_time = round(random.uniform(1.0, 6.0), 2)
    last_result = generate_last_result()
    flaky = random.random() < 0.10
    return execution_time, last_result, flaky


def _find_test_methods(java_text: str) -> Iterable[Tuple[str, str]]:
    """Yield tuples (method_name, method_body) for @Test annotated methods."""
    for m in re.finditer(r"@Test\b", java_text):
        idx = m.end()
        paren_idx = java_text.find(')', idx)
        if paren_idx == -1:
            continue
        brace_idx = java_text.find('{', paren_idx)
        if brace_idx == -1:
            continue

        depth = 0
        end_idx = brace_idx
        for i in range(brace_idx, len(java_text)):
            if java_text[i] == '{':
                depth += 1
            elif java_text[i] == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break

        method_block = java_text[idx:end_idx + 1]
        sig_portion = java_text[idx:paren_idx]
        name_match = re.search(r"(\w+)\s*$", sig_portion)
        method_name = name_match.group(1) if name_match else "unknown"

        yield method_name, method_block


def process_java_file(java_path: Path) -> List[Dict]:
    """Process a single Java test file and extract testcase dicts."""
    try:
        text = java_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not read %s: %s", java_path, exc)
        return []

    class_match = re.search(r"class\s+(\w+)", text)
    class_name = class_match.group(1) if class_match else java_path.stem
    component = java_path.parent.name or class_name

    entries: List[Dict] = []

    for method_name, body in _find_test_methods(text):
        selectors = extract_selectors_from_java(body)
        if not selectors:
            continue
        selector = selectors[0]
        ui_element = infer_ui_element_java(selector)
        execution_time, last_result, flaky = generate_synthetic_results()

        entries.append(
            {
                "name": method_name,
                "component": component,
                "ui_element": ui_element,
                "selector": selector,
                "execution_time": execution_time,
                "last_result": last_result,
                "flaky": flaky,
            }
        )

    return entries


def scan_java_tests(root: Path) -> List[Dict]:
    """Scan for Java test files under root and return collected entries."""
    collected: List[Dict] = []
    for p in root.rglob("*.java"):
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if "@Test" not in txt:
            continue
        logger.debug("Processing Java test: %s", p)
        collected.extend(process_java_file(p))

    return collected


def main(argv: Optional[List[str]] = None) -> int:
    """Extract Moodle testcases and write to data/large_testcases.json."""
    parser = argparse.ArgumentParser(description="Extract Moodle Selenium test cases")
    parser.add_argument("root", nargs="?", default=".", help="Moodle project root")
    parser.add_argument("--out", default=None, help="Output JSON path")

    args = parser.parse_args(argv)
    project_root = Path(args.root).resolve()

    logger.info("Scanning Moodle tests under: %s", project_root)
    tests = scan_java_tests(project_root)

    if not tests:
        logger.warning("No Moodle tests found")
        return 1

    # Default output: data/large_testcases.json
    if args.out:
        out_path = Path(args.out)
    else:
        # Write to PBL/project/data/, not apps/moodle/data/
        project_data_dir = Path(__file__).resolve().parent.parent / "data"
        out_path = project_data_dir / "large_testcases.json"
    write_small_testcases(tests, out_path)
    logger.info("Moodle large testcases written to: %s", out_path)
    return 0


if __name__ == "__main__":
    exit(main())
