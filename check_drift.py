
import json
from pathlib import Path

# Locate the project files.
folder = Path(__file__).parent

# Load the expected and actual network configurations.
with open(folder / "intended.json", encoding="utf-8") as file:
    intended = json.load(file)["student-host:host"]

with open(folder / "observed.json", encoding="utf-8") as file:
    observed = json.load(file)["student-host:host"]


differences = []


# Compare a field and record any differences.
def compare(field, expected, actual):
    if expected != actual:
        differences.append(
            f"{field}: intended={expected!r}, observed={actual!r}"
        )


# Check the expected host-level configuration fields.
for field in ["os", "hostname", "default-gateway", "dns-server"]:
    if field in intended:
        compare(field, intended[field], observed.get(field))


# Match interfaces by their names, not by their list positions.
observed_interfaces = {
    item["name"]: item
    for item in observed.get("interface", [])
}

for expected_interface in intended.get("interface", []):
    name = expected_interface["name"]
    actual_interface = observed_interfaces.get(name)

    if actual_interface is None:
        differences.append(
            f"interface/{name}: intended=present, observed=missing"
        )
        continue

    # Only compare fields explicitly included in intended.json.
    for field, expected_value in expected_interface.items():
        if field == "name":
            continue

        compare(
            f"interface/{name}/{field}",
            expected_value,
            actual_interface.get(field)
        )


# Print the configuration drift report.
print("Experiment 3: Configuration Drift Report")
print("----------------------------------------")

if differences:
    print(f"DRIFT DETECTED: {len(differences)} difference(s)")
    for number, difference in enumerate(differences, start=1):
        print(f"{number}. {difference}")
else:
    print("NO DRIFT: All intended values match observed values.")