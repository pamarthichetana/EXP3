
import json
import socket
import subprocess
import platform
import ipaddress
from datetime import datetime, timezone

import psutil


# Run a Windows PowerShell command and return its JSON output.
def run_powershell(command):
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=True
    )
    return json.loads(result.stdout)


# Convert a subnet mask into a prefix length.
# Example: 255.255.255.0 becomes 24.
def get_prefix(netmask):
    if not netmask:
        return None

    try:
        return ipaddress.IPv4Network(
            f"0.0.0.0/{netmask}"
        ).prefixlen
    except ValueError:
        return None


# Identify the network interface type.
def get_interface_type(name, description):
    value = (name + " " + description).lower()

    if "virtual" in value or "tap-" in value or "hotspotshield" in value:
        return "virtual"
    if "wi-fi" in value or "wireless" in value:
        return "wifi"
    if "loopback" in value:
        return "loopback"
    if "bluetooth" in value:
        return "other"
    if "ethernet" in value or "realtek" in value:
        return "ethernet"

    return "other"


# Collect network adapter details from Windows.
adapters = run_powershell(
    "Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, "
    "MacAddress, MtuSize | ConvertTo-Json -Depth 5"
)

if isinstance(adapters, dict):
    adapters = [adapters]

# Collect interface addresses using psutil.
addresses = psutil.net_if_addrs()

# Collect IPv6 prefix lengths directly from Windows.
# This is necessary because psutil may return None for IPv6 netmasks.
ipv6_details = run_powershell(
    "Get-NetIPAddress -AddressFamily IPv6 | "
    "Select-Object InterfaceAlias, IPAddress, PrefixLength | "
    "ConvertTo-Json -Depth 5"
)

if isinstance(ipv6_details, dict):
    ipv6_details = [ipv6_details]

if ipv6_details is None:
    ipv6_details = []

interfaces = []

for adapter in adapters:
    name = adapter["Name"]
    description = adapter["InterfaceDescription"]

    interface = {
        "name": name,
        "type": get_interface_type(name, description),
        "oper-status": "up" if adapter["Status"] == "Up" else "down",
        "mtu": int(adapter["MtuSize"]),
        "ipv4": [],
        "ipv6": []
    }

    # Convert Windows MAC addresses into the format required
    # by the JSON Schema: lowercase letters separated by colons.
    mac = adapter.get("MacAddress")

    if mac:
        interface["mac"] = mac.replace("-", ":").lower()

    for address in addresses.get(name, []):
        if address.family == socket.AF_INET:
            prefix = get_prefix(address.netmask)

            if prefix is not None:
                interface["ipv4"].append(
                    f"{address.address}/{prefix}"
                )

        
        
        elif address.family == socket.AF_INET6:
            # Remove the Windows zone identifier for comparison.
            ipv6_address = address.address.split("%")[0]

            # Match the interface name and IPv6 address with
            # the prefix information collected from PowerShell.
            prefix = None

            for detail in ipv6_details:
                windows_address = detail["IPAddress"].split("%")[0]

                if (
                    detail["InterfaceAlias"] == name
                    and windows_address.lower() == ipv6_address.lower()
                ):
                    prefix = detail["PrefixLength"]
                    break

            # Include the prefix when Windows provides it.
            if prefix is not None:
                interface["ipv6"].append(
                    f"{ipv6_address}/{prefix}"
                )
            else:
                interface["ipv6"].append(ipv6_address)



    interfaces.append(interface)


# Collect the active IPv4 default gateway.
routes = run_powershell(
    "Get-NetRoute -DestinationPrefix '0.0.0.0/0' "
    "-ErrorAction SilentlyContinue | "
    "Sort-Object RouteMetric | "
    "Select-Object -First 1 -Property NextHop | "
    "ConvertTo-Json"
)

# Collect DNS servers.
dns_data = run_powershell(
    "Get-DnsClientServerAddress -AddressFamily IPv4 | "
    "Select-Object -ExpandProperty ServerAddresses | "
    "ConvertTo-Json"
)

if isinstance(dns_data, str):
    dns_servers = [dns_data]
elif isinstance(dns_data, list):
    dns_servers = list(dict.fromkeys(dns_data))
else:
    dns_servers = []


# Build the observed configuration using the course model.
host = {
    "hostname": socket.gethostname(),
    "os": platform.system().lower(),
    "collected-at": datetime.now(timezone.utc).isoformat(),
    "dns-server": dns_servers,
    "interface": interfaces
}

if isinstance(routes, dict) and routes.get("NextHop"):
    host["default-gateway"] = routes["NextHop"]

observed = {
    "student-host:host": host
}


# Save the collected configuration as JSON.
with open("observed.json", "w", encoding="utf-8") as file:
    json.dump(observed, file, indent=4)

print("Network configuration collected successfully.")
print(f"Hostname: {host['hostname']}")
print(f"Operating system: {host['os']}")
print(f"Interfaces collected: {len(interfaces)}")
print("Output saved to observed.json")