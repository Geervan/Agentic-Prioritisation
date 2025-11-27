import json
import re
import os
import random
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Fallback path if provided path is empty
DEFAULT_PATH = Path("D:/PBL/project/apps/the-internet/spec")

def _clean_test_name(name: str) -> str:
    name = re.sub(r'[_\-]', ' ', name).strip()
    return re.sub(r'\s+', ' ', name).title()

def _infer_ui_element(action_list: List[str]) -> str:
    """Infers the UI element type from actions (Critical for scoring.py)."""
    full_text = " ".join(action_list).lower()
    if "click" in full_text: return "button"
    if "fill" in full_text or "type" in full_text: return "textbox"
    if "check" in full_text: return "checkbox"
    if "select" in full_text: return "dropdown"
    return "div"

def generate_augmented_tests(current_count: int, target: int = 60) -> List[Dict[str, Any]]:
    """
    Generates realistic additional tests to reach the 'Medium' dataset size target.
    This ensures we have enough data for the Agent to rank (~60 tests).
    """
    needed = target - current_count
    if needed <= 0: return []
    
    logger.info(f"⚡ Augmenting dataset with {needed} synthetic tests to reach Medium scale...")
    
    scenarios = [
        ("LoginPage", ["Login Empty Username", "Login Empty Password", "Login SQL Injection", "Login Bruteforce"]),
        ("DynamicLoadingPage", ["Wait For Element", "Assert Element Hidden", "Assert Element Visible"]),
        ("CheckboxesPage", ["Check Box 1 Toggle", "Check Box 2 Toggle", "Check All", "Uncheck All"]),
        ("DropdownPage", ["Select Option 1", "Select Option 2", "Select Default"]),
        ("FileUploadPage", ["Upload JPG", "Upload PNG", "Upload Large File", "Upload Empty File"]),
        ("HoversPage", ["Hover User 1", "Hover User 2", "Hover User 3", "Verify Profile Link"]),
        ("JavaScriptAlertsPage", ["Accept Alert", "Dismiss Alert", "Type In Prompt"]),
        ("KeyPressesPage", ["Press Enter", "Press Tab", "Press Escape", "Press Backspace"]),
        ("WindowsPage", ["Open New Tab", "Close New Tab", "Switch Window Context"]),
    ]
    
    augmented = []
    tid = current_count + 100 # Offset IDs
    
    while len(augmented) < needed:
        comp, cases = random.choice(scenarios)
        t_name = random.choice(cases)
        
        # Create realistic actions
        actions = ["visit.page", "find.element"]
        if "Login" in t_name: actions += ["fill.username", "fill.password", "click.login"]
        elif "Check" in t_name: actions += ["click.checkbox", "assert.checked"]
        elif "Upload" in t_name: actions += ["file.select", "click.upload"]
        else: actions += ["click.element", "assert.text"]
        
        # Fault Injection: Deterministic (hash-based) regression simulation
        is_regression_target = "Login" in t_name
        
        # Use hash of test name as seed for deterministic results
        seed = int(hashlib.md5(t_name.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        
        if is_regression_target:
            result = "fail" if rng.random() < 0.8 else "pass"
        else:
            result = "fail" if rng.random() < 0.05 else "pass"
        
        augmented.append({
            "id": tid,
            "name": f"{t_name} (Mock)", 
            "component": comp,
            "actions": actions,
            "ui_element": _infer_ui_element(actions),
            "execution_time": round(random.uniform(1.0, 6.0), 2),
            "last_result": result,
            "flaky": random.random() < 0.15
        })
        tid += 1
        
    return augmented

def extract_theinternet_tests(repo_path: Path) -> List[Dict[str, Any]]:
    extracted_tests = []
    test_id = 100

    # 1. Try Real Extraction
    if repo_path.exists():
        logger.info(f"📌 Scanning Ruby Specs in: {repo_path}")
        for root, _, files in os.walk(repo_path):
            for file_name in files:
                if not file_name.endswith(".rb"):
                    continue

                try:
                    with open(Path(root) / file_name, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Regex catches 'it', 'scenario', 'example' common in Ruby tests
                    test_blocks = re.findall(
                        r"(?:it|scenario|example)\s+['\"](.*?)['\"]\s+do([\s\S]*?)end", 
                        content
                    )

                    for test_name, block_content in test_blocks:
                        raw_actions = re.findall(r"(visit|click|fill_in|find|expect|select)\s+(.*)", block_content)
                        action_list = [f"{cmd}.{args.split(',')[0].strip()}" for cmd, args in raw_actions]
                        if not action_list: action_list = ["visit.page", "check.element"]

                        # Fault Injection: Deterministic (hash-based) regression simulation
                        is_regression_target = "login" in test_name.lower() or "login" in file_name.lower()
                        
                        # Use hash of test name as seed for deterministic results
                        seed = int(hashlib.md5(test_name.encode()).hexdigest()[:8], 16)
                        rng = random.Random(seed)
                        
                        if is_regression_target:
                            result = "fail" if rng.random() < 0.4 else "pass"
                        else:
                            result = "fail" if rng.random() < 0.05 else "pass"

                        extracted_tests.append({
                            "id": test_id,
                            "name": _clean_test_name(test_name),
                            "component": _clean_test_name(file_name.replace(".rb","")) + "Page",
                            "actions": action_list,
                            "ui_element": _infer_ui_element(action_list),
                            "execution_time": round(random.uniform(1.0, 5.0), 2),
                            "last_result": result,
                            "flaky": False
                        })
                        test_id += 1
                except Exception:
                    continue
    else:
        logger.warning(f"❌ Path not found: {repo_path}")

    # 2. Augment to reach Medium Dataset size (Target: 60 tests)
    # Even if extraction found 4 or 40, this ensures we get to 60.
    total_target = 60
    if len(extracted_tests) < total_target:
        synthetic = generate_augmented_tests(len(extracted_tests), target=total_target)
        extracted_tests.extend(synthetic)

    return extracted_tests

def main(app_path: str, output_path: str):
    # Allow calling with or without /spec, tries to be smart
    path_obj = Path(app_path)
    if not path_obj.exists() and (path_obj / "spec").exists():
        path_obj = path_obj / "spec"
        
    tests = extract_theinternet_tests(path_obj)
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tests, f, indent=2)
    logger.info(f"✨ Saved {len(tests)} 'The Internet' tests (Medium Dataset) to {output_path}")

if __name__ == "__main__":
    main("D:/PBL/project/apps/the-internet/spec", "the_internet_tests.json")
