
import csv
import json
import os
import re
import statistics
import time
from pathlib import Path

from mininet.net import Mininet
from mininet.node import DefaultController, OVSSwitch
from mininet.topo import SingleSwitchTopo
from mininet.log import setLogLevel


# Experiment configuration
BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "raw_data" / "matrix"

LOSS_RATES = [0, 0.1, 0.5, 1, 2]
ALGORITHMS = ["cubic", "bbr"]
REPETITIONS = 3

DURATION = 30
DELAY = "100ms"
RATE = "20mbit"
QUEUE_LIMIT = 1000

RAW_DIR.mkdir(parents=True, exist_ok=True)


# Configure the bottleneck on the forward path.
# ACK traffic in the reverse direction remains unshaped.
def configure_network(switch, loss):

    command = (
        f"tc qdisc replace dev s1-eth2 root netem "
        f"delay {DELAY} loss {loss}% "
        f"rate {RATE} limit {QUEUE_LIMIT}"
    )

    output = switch.cmd(command)

    if output.strip():
        raise RuntimeError(output)

    verification = switch.cmd(
        "tc qdisc show dev s1-eth2"
    )

    if "netem" not in verification:
        raise RuntimeError("Netem configuration failed")

    print(verification.strip(), flush=True)


# Perform one independent TCP throughput measurement.
# Preserve the original JSON and live TCP statistics.
def run_test(h1, h2, switch, algorithm, loss, run):

    name = f"{algorithm}_loss{loss}_run{run}"

    print(
        f"\nRunning {name} ({DURATION} seconds)",
        flush=True
    )

    configure_network(switch, loss)

    setting = h1.cmd(
        f"sysctl -w "
        f"net.ipv4.tcp_congestion_control={algorithm}"
    )

    print(setting.strip(), flush=True)

    if f"= {algorithm}" not in setting:
        raise RuntimeError("Algorithm configuration failed")

    json_path = RAW_DIR / f"{name}.json"
    ss_path = RAW_DIR / f"{name}_ss.txt"
    tc_path = RAW_DIR / f"{name}_tc.txt"

    # Start iperf3 in the sending host's namespace.
    command = [
        "iperf3",
        "-c", h2.IP(),
        "-t", str(DURATION),
        "-J"
    ]

    with json_path.open("w") as output:

        process = h1.popen(
            command,
            stdout=output
        )

        # Capture a live connection snapshot.
        time.sleep(10)

        ss_output = h1.cmd("ss -ti")
        ss_path.write_text(ss_output)

        return_code = process.wait()

    if return_code != 0:
        raise RuntimeError(f"iperf3 failed: {name}")

    # Preserve queue counters after each run.
    tc_output = switch.cmd(
        "tc -s qdisc show dev s1-eth2"
    )

    tc_path.write_text(tc_output)

    # Extract measurements from the original JSON.
    with json_path.open() as file:
        data = json.load(file)

    if "error" in data:
        raise RuntimeError(data["error"])

    end = data["end"]

    if end["sender_tcp_congestion"] != algorithm:
        raise RuntimeError("Unexpected sender algorithm")

    sent = end["sum_sent"]
    received = end["sum_received"]
    stream = end["streams"][0]["sender"]

    # Select the data connection instead of the
    # smaller iperf3 control connection.
    blocks = ss_output.splitlines()
    candidates = []

    for line in blocks:
        if algorithm in line and "bytes_sent:" in line:
            byte_match = re.search(
                r"bytes_sent:(\d+)", line
            )
            rtt_match = re.search(
                r"rtt:([\d.]+)/", line
            )

            if byte_match and rtt_match:
                candidates.append((
                    int(byte_match.group(1)),
                    float(rtt_match.group(1))
                ))

    ss_rtt = (
        max(candidates)[1]
        if candidates else None
    )

    result = {
        "algorithm": algorithm,
        "loss_percent": loss,
        "run": run,
        "sender_mbps": sent["bits_per_second"] / 1e6,
        "receiver_mbps": received["bits_per_second"] / 1e6,
        "retransmits": sent["retransmits"],
        "mean_rtt_ms": stream["mean_rtt"] / 1000,
        "ss_rtt_ms": ss_rtt,
    }

    print(
        f"Sender: {result['sender_mbps']:.3f} Mbps | "
        f"Receiver: {result['receiver_mbps']:.3f} Mbps | "
        f"Retransmits: {result['retransmits']} | "
        f"Mean RTT: {result['mean_rtt_ms']:.3f} ms",
        flush=True
    )

    time.sleep(2)

    return result


# Save individual run measurements to a CSV file.
def save_results(results):

    path = BASE_DIR / "raw_data" / "individual_results.csv"

    with path.open("w", newline="") as file:

        writer = csv.DictWriter(
            file,
            fieldnames=list(results[0].keys())
        )

        writer.writeheader()
        writer.writerows(results)


# Calculate mean throughput and sample standard deviation.
def summarize_results(results):

    summary = []

    for loss in LOSS_RATES:
        for algorithm in ALGORITHMS:

            group = [
                row for row in results
                if row["algorithm"] == algorithm
                and row["loss_percent"] == loss
            ]

            if len(group) != REPETITIONS:
                raise RuntimeError("Incomplete test group")

            sender = [r["sender_mbps"] for r in group]
            receiver = [r["receiver_mbps"] for r in group]
            retrans = [r["retransmits"] for r in group]
            rtt = [r["mean_rtt_ms"] for r in group]

            live_rtt = [
                r["ss_rtt_ms"] for r in group
                if r["ss_rtt_ms"] is not None
            ]

            summary.append({
                "algorithm": algorithm,
                "loss_percent": loss,
                "runs": len(group),
                "mean_sender_mbps": statistics.mean(sender),
                "stdev_sender_mbps": statistics.stdev(sender),
                "mean_receiver_mbps": statistics.mean(receiver),
                "mean_retransmits": statistics.mean(retrans),
                "mean_rtt_ms": statistics.mean(rtt),
                "mean_ss_rtt_ms": (
                    statistics.mean(live_rtt)
                    if live_rtt else None
                )
            })

    path = BASE_DIR / "raw_data" / "summary_results.csv"

    with path.open("w", newline="") as file:

        writer = csv.DictWriter(
            file,
            fieldnames=list(summary[0].keys())
        )

        writer.writeheader()
        writer.writerows(summary)

    # Display a readable summary for terminal evidence.
    print("\n" + "=" * 91)
    print("EXPERIMENT 5: CUBIC VS BBR SUMMARY")
    print("=" * 91)

    print(
        f"{'Algorithm':<10}"
        f"{'Loss %':>8}"
        f"{'Mean Mbps':>13}"
        f"{'SD Mbps':>11}"
        f"{'Retrans':>11}"
        f"{'RTT ms':>11}"
        f"{'SS RTT ms':>13}"
    )

    print("-" * 91)

    for row in summary:

        ss_rtt = row["mean_ss_rtt_ms"]

        ss_text = (
            f"{ss_rtt:.3f}"
            if ss_rtt is not None else "N/A"
        )

        print(
            f"{row['algorithm'].upper():<10}"
            f"{row['loss_percent']:>8.1f}"
            f"{row['mean_sender_mbps']:>13.3f}"
            f"{row['stdev_sender_mbps']:>11.3f}"
            f"{row['mean_retransmits']:>11.2f}"
            f"{row['mean_rtt_ms']:>11.3f}"
            f"{ss_text:>13}"
        )

    print("=" * 91)
    print("Summary saved:", path)


# Main experimental workflow.
def main():

    setLogLevel("info")

    topology = SingleSwitchTopo(k=2)

    net = Mininet(
        topo=topology,
        controller=DefaultController,
        switch=OVSSwitch,
        autoSetMacs=True
    )

    results = []

    try:

        net.start()

        h1 = net.get("h1")
        h2 = net.get("h2")
        switch = net.get("s1")

        print("\nChecking network connectivity...")

        packet_loss = net.pingAll()

        if packet_loss != 0:
            raise RuntimeError("Initial connectivity failed")

        h2.cmd("iperf3 -s -D")

        time.sleep(1)

        if ":5201" not in h2.cmd("ss -ltn"):
            raise RuntimeError("iperf3 server failed to start")

        print("\nStarting 30 experimental runs...")

        completed = 0

        for loss in LOSS_RATES:
            for algorithm in ALGORITHMS:
                for run in range(1, REPETITIONS + 1):

                    result = run_test(
                        h1, h2, switch,
                        algorithm, loss, run
                    )

                    results.append(result)

                    save_results(results)

                    completed += 1

                    print(
                        f"Progress: {completed}/30 completed",
                        flush=True
                    )

        summarize_results(results)

    finally:

        net.stop()


if __name__ == "__main__":
    main()
