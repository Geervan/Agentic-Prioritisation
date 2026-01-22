import json
import re
import os
import random
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def _clean_test_name(name: str) -> str:
    name = re.sub(r'[_\-]', ' ', name).strip()
    return re.sub(r'\s+', ' ', name).title()

def _infer_ui_element(action_list: List[str]) -> str:
    """
    Infers the UI element type from actions.
    REQUIRED to prevent KeyError in scoring.py.
    """
    full_text = " ".join(action_list).lower()
    if "click" in full_text or "btn" in full_text: return "button"
    if "type" in full_text or "input" in full_text or "fill" in full_text: return "textbox"
    if "select" in full_text: return "dropdown"
    return "generic_element"

def generate_augmented_tests(current_count: int, target: int = 30) -> List[Dict[str, Any]]:
    """
    Generates realistic additional tests to reach the 'Small' dataset size target.
    """
    needed = target - current_count
    if needed <= 0: return []
    
    logger.info(f"⚡ Augmenting dataset with {needed} synthetic tests to reach Small scale...")
    
    scenarios = [
        ("SwagItemsListPage", ["Sort Name A to Z", "Sort Name Z to A", "Sort Price Low to High", "Sort Price High to Low"]),
        ("CartSummaryPage", ["Remove Item", "Continue Shopping", "Checkout"]),
        ("CheckoutPersonalInfoPage", ["Fill Information", "Cancel Checkout", "Finish Checkout"]),
        ("SwagItemDetailsPage", ["Add to Cart", "Remove from Cart", "Back to Products"]),
        ("MenuPage", ["Logout", "About", "Reset App State"]),
        ("LoginPage", ["Login Standard User", "Login Locked User", "Login Problem User"]),
    ]
    
    augmented = []
    tid = current_count + 1 # Offset IDs
    
    while len(augmented) < needed:
        comp, cases = random.choice(scenarios)
        t_name = random.choice(cases)
        
        # Create realistic actions based on component
        actions = ["visit.page"]
        if "Sort" in t_name: actions += ["click.sort", "select.option", "assert.sorted"]
        elif "Checkout" in t_name: actions += ["fill.firstName", "fill.lastName", "fill.postalCode", "click.continue"]
        elif "Cart" in t_name: actions += ["click.cartItem", "assert.itemPresent"]
        elif "Login" in t_name: actions += ["fill.username", "fill.password", "click.loginButton"]
        else: actions += ["click.element", "assert.text"]
        
        # Fault Injection: Deterministic (hash-based) regression simulation
        is_regression_target = "Login" in t_name or "Checkout" in t_name
        
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
            "execution_time": round(random.uniform(1.0, 4.0), 2),
            "last_result": result,
            "flaky": random.random() < 0.1,
        })
        tid += 1
        
    return augmented

def extract_saucedemo_tests(app_root: Path) -> List[Dict[str, Any]]:
    extracted_tests = []
    test_id = 1

    # Your original code pointed to this specific subfolder
    target_path = app_root / "test/e2e/test/specs"

    if not target_path.exists():
        logger.error(f"❌ Path missing: {target_path}")
        # Try falling back to the root just in case
        target_path = app_root

    logger.info(f"📌 Scanning: {target_path}")

    for root, _, files in os.walk(target_path):
        for file_name in files:
            if not file_name.endswith(".spec.ts"):
                continue

            file_path = Path(root) / file_name
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                describe_match = re.search(r"describe\(['\"](.*?)['\"],", content)
                component_name = _clean_test_name(describe_match.group(1)) + "Page" if describe_match else "UnknownPage"

                # YOUR ORIGINAL REGEX (The one that works)
                test_blocks = re.findall(
                    r"it\s*\(\s*['\"](.*?)['\"]\s*,\s*async\s*\(\)\s*=>\s*{([\s\S]*?)\n\s*}\s*\)",
                    content
                )

                for test_name, block in test_blocks:
                    # Extract UI action method calls (PageObject.function())
                    actions = re.findall(r"(\w+)\.(\w+)\(", block)
                    action_list = [f"{obj}.{method}" for obj, method in actions]

                    # Fallback if regex missed actions
                    if not action_list:
                        action_list = ["browser.open", "element.interact"]

                    # Fault Injection: Deterministic (hash-based) regression simulation
                    is_regression_target = "login" in test_name.lower() or "checkout" in test_name.lower()
                    
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
                        "component": component_name,
                        "actions": action_list,
                        # ADDED: This field is required by scoring.py
                        "ui_element": _infer_ui_element(action_list), 
                        "execution_time": round(random.uniform(1.0, 4.0), 2),
                        "last_result": result,
                        "flaky": False,
                    })
                    test_id += 1

            except Exception as e:
                logger.warning(f"Error parsing {file_name}: {e}")

    # Augment to reach Small Dataset size (Target: 30 tests)
    total_target = 30
    if len(extracted_tests) < total_target:
        synthetic = generate_augmented_tests(len(extracted_tests), target=total_target)
        extracted_tests.extend(synthetic)

    return extracted_tests

# --- ENTRY POINT FOR main.py ---
def main(app_path: str, output_path: str):
    # Pass the APP ROOT (D:/PBL/.../saucelabs-sample-app-web)
    # The function above appends /test/e2e/test/specs automatically
    tests = extract_saucedemo_tests(Path(app_path))
    
    logger.info(f"✨ Extracted {len(tests)} SauceDemo tests!")
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tests, f, indent=2)

if __name__ == "__main__":
    # Test run
    main("D:/PBL/saucelabs-sample-app-web", "saucedemo_tests.json")
