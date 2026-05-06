import random
import time
from datetime import datetime, timedelta, timezone

log_levels = ["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"]
weights = [60, 20, 10, 8, 2]

messages = {
    "INFO": ["User logged in", "Data processed successfully", "Connection established", "Query executed", "Metrics flushed", "Heartbeat ok"],
    "DEBUG": ["Cache miss", "Retrying connection", "Thread spawned", "Memory usage at 45%"],
    "WARNING": ["High memory usage detected", "API rate limit approaching", "Deprecated endpoint accessed", "Connection timeout"],
    "ERROR": ["Failed to connect to database", "Invalid payload received", "Timeout waiting for response", "Authentication failed"],
    "CRITICAL": ["System out of memory", "Database corrupted", "Disk full", "Application crashed"]
}

with open("sample.log", "a", encoding="utf-8") as f:
    now = datetime.now(timezone.utc)
    for i in range(500):
        ts = (now - timedelta(seconds=500-i)).isoformat()
        level = random.choices(log_levels, weights=weights)[0]
        msg = random.choice(messages[level])
        ip = f"192.168.1.{random.randint(1, 255)}"
        req_id = f"req-{random.randint(1000, 9999)}"
        log_line = f"[{ts}] {level} [{req_id}] [client {ip}] {msg}\n"
        f.write(log_line)
        # Sleep slightly so if the monitor is tailing, it sees them flowing
        if i > 480:
            time.sleep(0.05)
