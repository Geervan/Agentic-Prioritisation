"""
extract_opencart_phpunit_tests.py

Extracts testcase metadata from OpenCart's PHPUnit test suite.
This script scans for `*_test.php` or `*Test.php` files, parses test 
method names, and generates synthetic metadata for the "medium" dataset.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Adjust import path for extract_cypress_tests
sys.path.insert(0, str(Path(__file__).parent.parent))

# Common helpers
from extraction.extract_cypress_tests import (
    infer_ui_element,
    generate_last_result,
    write_small_testcases,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def process_php_file(file_path: Path) -> List[Dict]:
    """Extracts test cases from a single PHPUnit test file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not read {file_path}: {e}")
        return []

    # Regex to find public functions starting with "test"
    # Caters to both test_method and testMethod conventions
    test_methods = re.findall(r"public\s+function\s+(test\w+)\s*\(", content)
    if not test_methods:
        return []

    entries = []
    component = file_path.stem.replace("_test", "").replace("Test", "")
    
    for i, method_name in enumerate(test_methods):
        test_id = abs(hash(f"{file_path}-{method_name}")) % 10**8
        selector = f"php_unit_{component}_{method_name}"
        
        entries.append(
            {
                "id": test_id,
                "name": method_name,
                "component": component,
                "ui_element": infer_ui_element(method_name),
                "selector": selector,
                "execution_time": round(random.uniform(0.5, 5.0), 2),
                "last_result": generate_last_result(),
                "flaky": random.random() < 0.05,
            }
        )
    return entries

def scan_php_tests(root: Path) -> List[Dict]:
    """Scans a directory for PHPUnit test files and extracts test cases."""
    collected: List[Dict] = []
    logger.info(f"Scanning for PHP tests in {root}...")
    
    # OpenCart tests might use *Test.php or *_test.php naming
    test_files = list(root.rglob("*Test.php")) + list(root.rglob("*_test.php"))
    logger.info(f"Found {len(test_files)} PHP test files.")

    for file_path in test_files:
        collected.extend(process_php_file(file_path))
        
    return collected

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Extract OpenCart PHPUnit test cases.")
    parser.add_argument("root", help="Path to the OpenCart project root directory.")
    parser.add_argument("--out", help="Output JSON file path.")
    args = parser.parse_args(argv)

    project_root = Path(args.root).resolve()
    
    # OpenCart's tests are typically within the 'upload' directory structure.
    test_root = project_root / 'tools' / 'daux.io' / 'tests'
    if not test_root.exists():
        test_root = project_root
        
    testcases = scan_php_tests(test_root)

    if not testcases:
        logger.error("No test cases were extracted. Check the path and file structure.")
        return 1

    out_path = Path(args.out) if args.out else Path(__file__).resolve().parent.parent / "data" / "medium_testcases.json"
    
    write_small_testcases(testcases, out_path)
    logger.info(f"{len(testcases)} OpenCart test cases written to {out_path}")
    
    return 0

if __name__ == "__main__":
    # Example usage from CLI:
    # python extraction/extract_opencart_phpunit_tests.py "d:\\PBL\\project\\apps\\opencart"
    exit(main())
