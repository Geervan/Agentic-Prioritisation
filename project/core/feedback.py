import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _memory_path(dataset_name: Optional[str] = None) -> Path:
	"""Get memory file path for a dataset.
	
	Args:
		dataset_name: Name of dataset (small, medium, large). If None, uses generic 'memory.json'
		
	Returns:
		Path to the memory file
	"""
	base = Path(__file__).resolve().parent.parent
	if dataset_name:
		return base / f"{dataset_name}_memory.json"
	return base / "memory.json"


def load_feedback(dataset_name: Optional[str] = None) -> List[Dict[str, Any]]:
	"""Load a list of feedback entries from dataset-specific memory file.

	If the file is missing, it will be created with an empty list and an empty
	list will be returned. If the file contains a dict with a top-level
	"feedback" list, that list will be returned. On parse errors an empty
	list is returned.
	
	Args:
		dataset_name: Name of dataset (small, medium, large) to load feedback for
	"""
	path = _memory_path(dataset_name)
	if not path.exists():
		try:
			path.write_text("[]", encoding="utf-8")
		except Exception:
			pass
		return []

	try:
		with path.open("r", encoding="utf-8") as f:
			data = json.load(f)
	except Exception:
		return []

	if isinstance(data, list):
		return data
	if isinstance(data, dict) and isinstance(data.get("feedback"), list):
		return data.get("feedback")
	return []


def save_feedback(test_id: str, result: Any, dataset_name: Optional[str] = None) -> None:
	"""Save feedback entry to dataset-specific memory file.
	
	Args:
		test_id: The test ID
		result: The result data (typically {"status": "pass" or "fail"})
		dataset_name: Name of dataset (small, medium, large) to save feedback for
	"""
	
	path = _memory_path(dataset_name)
	if not path.exists():
		try:
			path.write_text("[]", encoding="utf-8")
		except Exception:
			pass

	try:
		with path.open("r", encoding="utf-8") as f:
			data = json.load(f)
	except Exception:
		data = []

	entry = {"test_id": test_id, "result": result}

	# Preserve dict-with-feedback structure if present
	if isinstance(data, dict) and isinstance(data.get("feedback"), list):
		data["feedback"].append(entry)
		out = data
	elif isinstance(data, list):
		data.append(entry)
		out = data
	else:
		out = [entry]

	with path.open("w", encoding="utf-8") as f:
		json.dump(out, f, indent=2)

