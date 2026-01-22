"""
Adapter script to extract REAL testcases from Cypress Realworld App (Cypress/Mocha syntax).
Targets: describe('Component') -> it('Test Case')

Output JSON format:
[
  {
    "id": 1,
    "name": "should allow a user to pay",
    "component": "Transaction",
    "actions": ["visit", "fill", "click"],
    "last_result": "fail" (injected),
    ...
  }
]
"""

import sys
import os
import json
import re
import glob
import logging
import random
import hashlib
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_file_tests(file_path: str, start_id: int, keywords: List[str] = []) -> List[Dict[str, Any]]:
    """Reads a Cypress spec file and extracts test metadata."""
    tests = []
    current_component = "Unknown Component"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex to find describe block (Component)
    # describe('Transaction View', () => { ...
    describe_match = re.search(r"describe\(['\"](.+?)['\"]", content)
    if describe_match:
        current_component = describe_match.group(1)

    # Regex to find it/test blocks
    # it('searches for a user by phone', () => { ...
    # Match generic it('name') pattern
    test_matches = re.finditer(r"it\(['\"](.+?)['\"]", content)

    for match in test_matches:
        test_name = match.group(1)
        
        # Determine likely actions based on content snippet (very basic heuristic)
        # In a real tool, we'd parse the AST, but regex is fine for this demo
        actions = ["visit.page"]
        if "pay" in test_name.lower() or "transaction" in test_name.lower():
            actions += ["fill.amount", "fill.note", "click.pay"]
        elif "login" in test_name.lower():
            actions += ["fill.username", "fill.password", "click.login"]
        elif "comment" in test_name.lower():
            actions += ["fill.comment", "click.post"]
        else:
            actions += ["click.element", "assert.visible"]

        # Fault Injection: Deterministic (hash-based) simulation
        # WE STILL NEED THIS: Real repos have passing tests. We need failures for APFD.
        seed = int(hashlib.md5(test_name.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        
        # MONTE CARLO LOGIC:
        # If the test matches the current scenario keywords, vastly increase failure probability
        is_relevant = False
        if keywords:
            for kw in keywords:
                if kw in test_name.lower() or kw in current_component.lower():
                    is_relevant = True
                    break
        
        if keywords:
            # If we are in a specific scenario, relevant tests fail 90% of the time, others 2% (noise)
            fail_prob = 0.9 if is_relevant else 0.02
        else:
            # Default/legacy behavior if no scenario active (e.g. static run)
            # High-risk components fail more often (simulation)
            is_risk = "transaction" in test_name.lower() or "payment" in test_name.lower()
            fail_prob = 0.4 if is_risk else 0.05
        
        last_result = "fail" if rng.random() < fail_prob else "pass"
        flaky = rng.random() < 0.2  # 20% of tests are marked flaky

        tests.append({
            "id": start_id,
            "name": test_name,
            "component": current_component,
            "actions": actions,
            "ui_element": "button",  # simplified
            "execution_time": round(rng.uniform(1.0, 5.0), 2),
            "last_result": last_result,
            "flaky": flaky
        })
        start_id += 1
        
    return tests

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    
    if len(argv) < 2:
        print("Usage: python extract_cypress_tests.py <repo_root> --out <output_json>")
        return

    repo_root = argv[0]
    output_file = "cypress_tests.json"
    
    if "--out" in argv:
        try:
            output_file = argv[argv.index("--out") + 1]
        except IndexError:
            pass
            
    limit = None
    if "--limit" in argv:
        try:
            limit = int(argv[argv.index("--limit") + 1])
        except (IndexError, ValueError):
            pass

    keywords = []
    if "--keywords" in argv:
        try:
            # Keywords are passed as a comma-separated string
            kw_str = argv[argv.index("--keywords") + 1]
            keywords = [k.strip().lower() for k in kw_str.split(",") if k.strip()]
        except IndexError:
            pass

    logger.info(f"🔍 Scanning {repo_root} for Cypress tests...")
    
    # Cypress Realworld App specific path
    # Tests are usually in cypress/tests
    search_pattern = os.path.join(repo_root, "**", "*.spec.ts")
    files = sorted(glob.glob(search_pattern, recursive=True))
    
    # Fallback for JS files if TS not found
    if not files:
        search_pattern = os.path.join(repo_root, "**", "*.spec.js")
        files = sorted(glob.glob(search_pattern, recursive=True))

    logger.info(f"📂 Found {len(files)} spec files.")
    
    all_tests = []
    current_id = 100 if "small" in output_file else (1000 if "medium" in output_file else 2000)
    
    for f in files:
        if limit and len(all_tests) >= limit:
            break
            
        file_tests = extract_file_tests(f, current_id, keywords)
        
        # Check if adding these would exceed limit
        if limit and len(all_tests) + len(file_tests) > limit:
            remaining = limit - len(all_tests)
            all_tests.extend(file_tests[:remaining])
            break
        
        all_tests.extend(file_tests)
        current_id += len(file_tests)

        
    logger.info(f"✅ Extracted {len(all_tests)} GENUINE tests.")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(all_tests, f, indent=2)
        
    logger.info(f"💾 Saved to {output_file}")

if __name__ == "__main__":
    main()
