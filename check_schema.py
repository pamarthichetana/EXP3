
import json
from pathlib import Path
from jsonschema import Draft202012Validator

# Locate the files in the current project folder.
folder = Path(__file__).parent

# Load the professor's schema and our observed configuration.
with open(folder / "host_schema.json", encoding="utf-8") as file:
    schema = json.load(file)

with open(folder / "observed.json", encoding="utf-8") as file:
    observed = json.load(file)

# Check the collected data against the JSON Schema.
validator = Draft202012Validator(schema)
errors = sorted(
    validator.iter_errors(observed),
    key=lambda error: str(error.absolute_path)
)

print("Experiment 3: JSON Schema Validation")
print("------------------------------------")

if not errors:
    print("VALID: observed.json follows host_schema.json")
else:
    print(f"INVALID: {len(errors)} validation error(s) found.")

    for number, error in enumerate(errors, start=1):
        path = "/" + "/".join(
            str(part) for part in error.absolute_path
        )
        print(f"{number}. Path: {path}")
        print(f"   Error: {error.message}")