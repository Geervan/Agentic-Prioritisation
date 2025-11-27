"""
extract_selenium_tests.py

Scan Selenium-based Java test suites (JUnit/TestNG) and extract lightweight
testcase metadata suitable for prioritisation. The script finds methods
annotated with `@Test`, extracts selectors used with `By.id`,
`By.cssSelector`, `By.xpath`, etc., and emits a JSON file with synthetic
execution metadata.

The script reuses UI inference and small JSON writer helpers from the
existing Cypress extractor (`tools/extract_cypress_tests.py`). It does not
execute automatically; run it explicitly when needed.

Output files (by `--flavor`):
 - opencart -> `data/medium_testcases.json`
 - moodle   -> `data/large_testcases.json`

Fields per testcase (exact schema required):
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

"""
from __future__ import annotations

import argparse
import json
import logging
import random
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# Reuse helpers from the Cypress extractor
import sys
from pathlib import Path as PathlibPath
sys.path.insert(0, str(PathlibPath(__file__).parent.parent / "tools"))
from extract_cypress_tests import (
    infer_ui_element,
    generate_last_result,
    write_small_testcases,
)


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ----------------------- Java selector extraction -------------------------


def extract_selectors_from_java(java_text: str) -> List[str]:
    """Extract literal selector strings from Java Selenium code.

    Captures common patterns like:
      By.id("...")
      By.cssSelector("...")
      By.xpath("...")
      By.className('...')
      By.name('...')

    Returns selectors in the order found. Only literal string arguments are
    captured (single- or double-quoted).
    """
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
    """Infer UI element type for Java selectors.

    Delegates to `infer_ui_element` for CSS-like selectors and performs
    lightweight heuristics for XPath expressions.
    """
    s = selector.strip()
    # XPath heuristic
    if s.startswith("//") or s.startswith(".//") or s.startswith("/"):
        low = s.lower()
        # check for element names or attributes inside xpath
        if re.search(r"//?\w*button\b", low) or "@type='submit'" in low or "@type=\"submit\"" in low:
            return "button"
        if re.search(r"//?\w*(input|textarea|select)\b", low) or "@type='text'" in low:
            return "input"
        if re.search(r"//?\w*a\b", low) or "@href" in low:
            return "link"
        return "unknown"

    # Delegate to CSS/ID heuristic
    return infer_ui_element(selector)


def generate_synthetic_results_java() -> Tuple[float, str, bool]:
    """Generate synthetic execution_time (1-6s), last_result and flaky flag."""
    execution_time = round(random.uniform(1.0, 6.0), 2)
    last_result = generate_last_result()
    flaky = random.random() < 0.10
    return execution_time, last_result, flaky


# ----------------------- Java method parsing helpers ----------------------


def _find_test_methods(java_text: str) -> Iterable[Tuple[str, str]]:
    """Yield tuples (method_name, method_body) for methods annotated with
    `@Test` (JUnit/TestNG).

    This uses a regex to find `@Test` annotations and then scans forward to
    capture the full method body using brace matching, making it robust to
    nested blocks and comments.
    """
    for m in re.finditer(r"@Test\b", java_text):
        # start searching for method signature after annotation
        idx = m.end()
        # find the opening brace of the method body
        # search for the first '{' after the next ')' that closes the signature
        paren_idx = java_text.find(')', idx)
        if paren_idx == -1:
            continue
        brace_idx = java_text.find('{', paren_idx)
        if brace_idx == -1:
            continue

        # find matching closing brace
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

        # extract method name from the signature preceding the '('
        # look backwards from paren_idx to find method name token
        sig_portion = java_text[idx:paren_idx]
        name_match = re.search(r"(\w+)\s*$", sig_portion)
        method_name = name_match.group(1) if name_match else "unknown"

        yield method_name, method_block


def process_java_file(java_path: Path) -> List[Dict]:
    """Process a single Java test file and extract testcase dicts.

    Component is inferred from the parent folder name or the Java class name.
    """
    try:
        text = java_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not read %s: %s", java_path, exc)
        return []

    # attempt to find class name as fallback component
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
        execution_time, last_result, flaky = generate_synthetic_results_java()

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


def scan_java_tests(root: Path, pattern: str = "**/*.java") -> List[Dict]:
    """Scan for Java test files under `root` and return collected entries.

    `pattern` can be used to restrict search to particular test trees.
    """
    collected: List[Dict] = []
    for p in root.rglob("*.java"):
        # optional pattern filtering: user may pass subfolder path like opencart/tests
        if pattern and not str(p).lower().endswith(".java"):
            continue
        # Heuristic: only process files that look like test files (contain @Test)
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if "@Test" not in txt:
            continue
        logger.debug("Processing Java test: %s", p)
        collected.extend(process_java_file(p))

    return collected


def write_testcases_for_flavor(testcases: List[Dict], project_root: Path, flavor: str) -> Path:
    """Write testcases JSON for a specific flavor (opencart/moodle)."""
    if flavor.lower() == "opencart":
        out = project_root / "data" / "medium_testcases.json"
    elif flavor.lower() == "moodle":
        out = project_root / "data" / "large_testcases.json"
    else:
        out = project_root / "data" / f"{flavor}_testcases.json"

    # reuse writer which assigns incremental IDs
    write_small_testcases(testcases, out)
    return out


# ----------------------------- CLI and API --------------------------------


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Extract Selenium Java test selectors")
    p.add_argument("root", nargs="?", default=".", help="Project root to scan")
    p.add_argument(
        "--flavor",
        choices=["opencart", "moodle"],
        default="opencart",
        help="Which output file to create (opencart -> medium, moodle -> large)",
    )
    p.add_argument("--out", default=None, help="Optional override output path")
    return p


def generate_selenium_testcases(project_root: Path, flavor: str = "opencart", out_path: Optional[Path] = None) -> Path:
    if out_path is None:
        out_path = None
    tests = scan_java_tests(project_root)
    if not tests:
        logger.info("No Java Selenium tests with selectors were found under %s", project_root)
    # write to correct flavor file
    return write_testcases_for_flavor(tests, project_root, flavor)


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_cli()
    args = parser.parse_args(argv)
    project_root = Path(args.root).resolve()
    logger.info("Scanning Java tests under: %s", project_root)
    out = generate_selenium_testcases(project_root, args.flavor, None)
    logger.info("Wrote testcases to: %s", out)
    return 0


# To run: python tools/extract_selenium_tests.py /path/to/project --flavor opencart
