"""Job spec validation for film crew inbox specs.

Validates JSON structure before the Producer touches it.
Catches malformed jobs early so the crew doesn't crash mid-pipeline.
"""
import json
import os


REQUIRED_FIELDS = {
    "job_id": str,
    "requested_by": str,
    "type": str,
    "title": str,
    "subject": str,
    "description": str,
    "target_audience": str,
    "duration_seconds": int,
    "tone": str,
}

OPTIONAL_FIELDS = {
    "deliverables": (list, type(None)),
    "reference_materials": (list, type(None)),
    "source": str,
    "callback": (str, type(None)),
}

ALL_FIELDS = {**REQUIRED_FIELDS, **OPTIONAL_FIELDS}


def validate(path):
    """Validate a job JSON file.

    Returns: (errors list, warnings list, normalized dict)
    - errors: list of strings (fatal — do not run this job)
    - warnings: list of strings (non-fatal — crew can still try)
    - dict: the parsed JSON data
    """
    errors = []
    warnings = []

    if not os.path.isfile(path):
        errors.append(f"File does not exist: {path}")
        return errors, warnings, {}

    try:
        with open(path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
        return errors, warnings, {}
    except OSError as e:
        errors.append(f"Cannot read file: {e}")
        return errors, warnings, {}

    if not isinstance(data, dict):
        errors.append("Top-level must be a JSON object.")
        return errors, warnings, {}

    # Required fields
    for key, expected_type in REQUIRED_FIELDS.items():
        if key not in data:
            errors.append(f"Missing required field: '{key}'")
        elif not isinstance(data[key], expected_type):
            errors.append(
                f"Field '{key}' must be {expected_type.__name__}, "
                f"got {type(data[key]).__name__}"
            )

    # Duration must be positive
    dur = data.get("duration_seconds")
    if isinstance(dur, int):
        if dur <= 0:
            errors.append(f"duration_seconds must be > 0, got {dur}")
        elif dur > 3600:
            warnings.append(
                f"duration_seconds is {dur}s (> 1hr) — expect long render times."
            )
    elif dur is not None:
        # caught by type check above
        pass

    # Optional fields — type check only, no enforcement
    for key, expected_type in OPTIONAL_FIELDS.items():
        if key in data and data[key] is not None:
            if isinstance(expected_type, tuple):
                if not isinstance(data[key], expected_type):
                    warnings.append(
                        f"Field '{key}' has unexpected type "
                        f"{type(data[key]).__name__}"
                    )
            elif not isinstance(data[key], expected_type):
                warnings.append(
                    f"Field '{key}' has unexpected type {type(data[key]).__name__}"
                )

    # Warn about unknown fields — could be a typo
    for key in data:
        if key not in ALL_FIELDS:
            warnings.append(f"Unknown field '{key}' — possible typo?")

    # Suggest reasonable deliverables if missing or empty
    dels = data.get("deliverables")
    if dels is None or (isinstance(dels, list) and len(dels) == 0):
        warnings.append("No deliverables specified — defaulting to ['video']")
        data["deliverables"] = ["video"]

    return errors, warnings, data


def short_report(path):
    """Return a one-line status for logging."""
    errors, warnings, _ = validate(path)
    if errors:
        return f"INVALID ({len(errors)} error(s))"
    if warnings:
        return f"VALID ({len(warnings)} warning(s))"
    return "VALID"
