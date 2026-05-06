"""
load_test.py
------------
Simple script to generate synthetic traffic for the Log Monitor App.
Useful for triggering Prometheus alerts and populating Grafana dashboards.
"""

import sys
import time
import random
import threading
import requests
from concurrent.futures import ThreadPoolExecutor

# Configuration
BASE_URL = "http://localhost:5000"
DURATION_SECONDS = 60
CONCURRENCY = 5

LOG_MESSAGES = [
    ("INFO", "User logged in successfully"),
    ("INFO", "Data processing completed"),
    ("WARNING", "Slow response from external API"),
    ("ERROR", "Database connection failed"),
    ("CRITICAL", "Payment gateway unreachable"),
    ("INFO", "Session expired"),
    ("ERROR", "NullPointerException in user_service"),
]


def send_traffic(thread_id, stop_event):
    """Worker function to send continuous random traffic."""
    requests_sent = 0
    errors_encountered = 0

    while not stop_event.is_set():
        try:
            action = random.choices(
                ["GET_INDEX", "GET_LOGS", "POST_LOG", "GET_ALERTS", "BAD_ROUTE"],
                weights=[20, 30, 40, 5, 5],
            )[0]

            if action == "GET_INDEX":
                requests.get(f"{BASE_URL}/", timeout=2)
            elif action == "GET_LOGS":
                requests.get(f"{BASE_URL}/logs?limit=10", timeout=2)
            elif action == "POST_LOG":
                level, msg = random.choice(LOG_MESSAGES)
                requests.post(
                    f"{BASE_URL}/logs",
                    json={"level": level, "message": f"[LoadTest] {msg}"},
                    timeout=2,
                )
            elif action == "GET_ALERTS":
                requests.get(f"{BASE_URL}/alerts", timeout=2)
            elif action == "BAD_ROUTE":
                requests.get(f"{BASE_URL}/nonexistent", timeout=2)

            requests_sent += 1
            time.sleep(random.uniform(0.1, 0.5))

        except Exception:
            errors_encountered += 1
            time.sleep(1)

    return requests_sent, errors_encountered


def main():
    print(f"Starting load test against {BASE_URL}...")
    print(f"Duration: {DURATION_SECONDS} seconds")
    print(f"Concurrency: {CONCURRENCY} threads")
    print("-" * 50)

    stop_event = threading.Event()
    
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [
            executor.submit(send_traffic, i, stop_event) 
            for i in range(CONCURRENCY)
        ]
        
        try:
            # Wait for duration
            for remaining in range(DURATION_SECONDS, 0, -1):
                sys.stdout.write(f"\rTime remaining: {remaining:02d}s")
                sys.stdout.flush()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nLoad test interrupted.")
            
        print("\nStopping threads...")
        stop_event.set()
        
        results = [f.result() for f in futures]

    total_requests = sum(r[0] for r in results)
    total_errors = sum(r[1] for r in results)
    
    print("-" * 50)
    print("Load test complete.")
    print(f"Total successful operations: {total_requests}")
    print(f"Total local errors/timeouts: {total_errors}")
    print(f"Average operations/sec: {total_requests / max(1, DURATION_SECONDS):.2f}")


if __name__ == "__main__":
    main()
