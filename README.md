# CSC 6410 — Experiment 3: Network Configuration Validation and Drift Detection

## Project Overview

This experiment investigates whether Python automation can collect and validate a Windows computer's network configuration faster and more reliably than manual inspection.

The experiment uses Python, PowerShell, JSON, a YANG-like model, and JSON Schema to collect network settings, validate their structure, and identify differences between intended and observed configurations.

## Experimental Environment

- Operating System: Windows 11
- Python Version: 3.13.7
- PowerShell Version: 5.1
- Libraries: psutil and jsonschema
- Network: Wi-Fi

## Project Files

- `collect_config.py` — Collects network configuration and generates `observed.json`.
- `check_schema.py` — Validates the collected configuration against `host_schema.json`.
- `check_drift.py` — Compares observed configuration with `intended.json`.
- `host_model.yang` — Instructor-provided network configuration model.
- `host_schema.json` — Instructor-provided JSON Schema.
- `intended.json` — Defines the expected network configuration.
- `observed_redacted.json` — Sample collected configuration with MAC addresses partially hidden.

## How to Run

**Step 1: Install required libraries**

```powershell
python -m pip install psutil jsonschema
```

**Step 2: Collect network configuration**

```powershell
python collect_config.py
```

This generates `observed.json` on the local computer.

**Step 3: Validate the configuration**

```powershell
python check_schema.py
```

**Step 4: Check configuration drift**

```powershell
python check_drift.py
```

The drift checker compares the intended and observed network settings and reports any differences.

## Experimental Results

The automated collection completed in approximately 6.95 seconds, compared with approximately 5 minutes for the second manual collection trial.

The experiment detected five network interfaces and identified a missing IPv6 prefix during development. The issue was corrected using Windows PowerShell.

The JSON Schema validator successfully detected an intentionally invalid MTU value.

A deliberate Wi-Fi shutdown produced a configuration drift report showing the intended interface status as `up` and the observed status as `down`.

## Privacy and Security

The original `observed.json` contains actual network configuration information and is intentionally excluded from this public repository.

Instead, `observed_redacted.json` is provided as a sample with MAC addresses partially hidden. Users should review the sample for other identifying information before sharing it.

To reproduce the experiment, run `collect_config.py` locally to generate a new `observed.json` for your own computer.

## Conclusion

Python automation reduced the time required to collect network configuration information and identified network interfaces and configuration details that were missed during manual inspection.

JSON Schema validation detected structural errors, while configuration drift checking identified differences between the expected and actual network states.

The experiment demonstrates the benefits and limitations of automated network configuration validation.
