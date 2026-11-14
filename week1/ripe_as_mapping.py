"""
Purpose:
    Map responding traceroute IP addresses to Autonomous Systems (ASes)
    using the RIPEstat Network Info API.

Logic:
    1. Read all traceroute text files in this folder.
    2. Extract IPv4 and IPv6 addresses.
    3. Skip non-global addresses that are not suitable for public AS mapping.
    4. Query RIPEstat for each unique global IP address.
    5. Save the results to a CSV file.

Assumptions:
    Traceroute results are saved as .txt files in this folder.
    Internet access is available when running the script.

Testing:
    Check the CSV output and compare selected results with RIPEstat.

Limitations:
    An IP-to-AS mapping does not prove the complete packet route.
    Some addresses may not have a mapping or may belong to shared infrastructure.

Fallback:
    If an API request fails, record the error and continue with the next IP.
"""

import csv
import ipaddress
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Use the folder containing this Python script and traceroute files.
DATA_DIR = Path(r"C:\Users\Chetana\Desktop\AS_Routing_Lab")
OUTPUT_FILE = DATA_DIR / "ripe_as_results.csv"

# Find IPv4 and IPv6 addresses in traceroute output.
IP_PATTERN = re.compile(r'(?<![0-9A-Fa-f:.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9A-Fa-f:.])|(?<![0-9A-Fa-f:])[0-9A-Fa-f:]{2,}(?![0-9A-Fa-f:])')

def extract_global_ips(file_path):
    """Return unique globally routable IP addresses from one text file."""
    found = []
    text = file_path.read_text(encoding="utf-16", errors="ignore")

    for candidate in IP_PATTERN.findall(text):
        try:
            address = ipaddress.ip_address(candidate)
            if address.is_global and str(address) not in found:
                found.append(str(address))
        except ValueError:
            continue

    return found

def query_ripestat(ip):
    """Query RIPEstat for the network and origin AS information for an IP."""
    url = (
        "https://stat.ripe.net/data/network-info/data.json?"
        + urlencode({"resource": ip})
    )

    request = Request(
        url,
        headers={"User-Agent": "Networking-AS-Mapping-Student-Experiment"}
    )

    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))

        data = payload.get("data", {})
        asns = data.get("asns", [])

        return {
            "prefix": data.get("prefix", ""),
            "as_numbers": ", ".join(str(asn) for asn in asns),
            "network_name": data.get("holder", ""),
            "status": "OK" if asns else "No AS returned"
        }

    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        return {
            "prefix": "",
            "as_numbers": "",
            "network_name": "",
            "status": f"API error: {error}"
        }


def main():
    files = sorted(DATA_DIR.glob("*_run*.txt"))

    if not files:
        print(f"No traceroute text files found in: {DATA_DIR}")
        return

    # Store the file names associated with each unique IP.
    ip_sources = {}

    for file_path in files:
        print(f"Reading: {file_path.name}")

        for ip in extract_global_ips(file_path):
            ip_sources.setdefault(ip, set()).add(file_path.name)

    if not ip_sources:
        print("No globally routable IP addresses were found.")
        return

    print(f"\nFound {len(ip_sources)} unique global IP addresses.")
    print("Querying RIPEstat. This may take a few minutes...\n")

    rows = []

    for number, ip in enumerate(sorted(ip_sources), start=1):
        result = query_ripestat(ip)

        row = {
            "ip_address": ip,
            "source_files": "; ".join(sorted(ip_sources[ip])),
            "prefix": result["prefix"],
            "as_numbers": result["as_numbers"],
            "network_name": result["network_name"],
            "status": result["status"]
        }
        rows.append(row)

        print(
            f"[{number}/{len(ip_sources)}] {ip} | "
            f"AS: {result['as_numbers'] or 'Not available'} | "
            f"{result['network_name'] or result['status']}"
        )

        # Avoid sending requests too rapidly.
        time.sleep(0.5)

    columns = [
        "ip_address",
        "source_files",
        "prefix",
        "as_numbers",
        "network_name",
        "status"
    ]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nFinished. Results saved to:\n{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
