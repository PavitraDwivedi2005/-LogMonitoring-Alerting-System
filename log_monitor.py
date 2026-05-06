"""
log_monitor.py
--------------
Monitors a log file for error patterns and triggers alerts
when anomaly thresholds are exceeded.
"""

import re
import time
import threading
from datetime import datetime, timezone
from collections import deque


# Patterns to detect in log lines
LOG_PATTERNS = {
    "CRITICAL": re.compile(r"\bCRITICAL\b", re.IGNORECASE),
    "ERROR": re.compile(r"\bERROR\b", re.IGNORECASE),
    "WARNING": re.compile(r"\bWARNING\b", re.IGNORECASE),
}

# Severity weights for scoring
SEVERITY_WEIGHTS = {
    "CRITICAL": 5,
    "ERROR": 3,
    "WARNING": 1,
}


class Alert:
    """Represents a single triggered alert."""

    def __init__(self, severity, message, source_line=""):
        self.id = int(time.time() * 1000)
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.severity = severity
        self.message = message
        self.source_line = source_line
        self.resolved = False

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "message": self.message,
            "source_line": self.source_line,
            "resolved": self.resolved,
        }


class LogMonitor:
    """
    Watches a log file and detects anomalies.

    Triggers an alert when the number of errors in a rolling
    time window exceeds a configurable threshold.
    """

    def __init__(
        self,
        log_file="sample.log",
        error_threshold=5,
        window_seconds=60,
    ):
        self.log_file = log_file
        self.error_threshold = error_threshold
        self.window_seconds = window_seconds

        # Rolling window of (timestamp, severity) tuples
        self._events = deque()
        # Stored alerts
        self._alerts = []
        self._alerts_lock = threading.Lock()

        # For tailing the file
        self._stop_event = threading.Event()
        self._monitor_thread = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Start monitoring the log file in a background thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._tail_file, daemon=True
        )
        self._monitor_thread.start()

    def stop(self):
        """Stop the background monitor thread."""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

    def process_line(self, line):
        """
        Analyse a single log line.
        Returns the detected severity or None.
        """
        line = line.strip()
        if not line:
            return None

        detected_severity = None
        for severity, pattern in LOG_PATTERNS.items():
            if pattern.search(line):
                detected_severity = severity
                break  # highest severity first (dict is ordered)

        if detected_severity:
            now = time.time()
            self._events.append((now, detected_severity))
            self._prune_window(now)
            self._check_threshold(line, detected_severity)

        return detected_severity

    def get_alerts(self, limit=50):
        """Return the most recent alerts."""
        with self._alerts_lock:
            return [a.to_dict() for a in self._alerts[-limit:]]

    def get_stats(self):
        """Return current monitoring statistics."""
        now = time.time()
        self._prune_window(now)
        counts = {"CRITICAL": 0, "ERROR": 0, "WARNING": 0}
        for _, severity in self._events:
            counts[severity] = counts.get(severity, 0) + 1

        with self._alerts_lock:
            total_alerts = len(self._alerts)

        return {
            "window_seconds": self.window_seconds,
            "error_threshold": self.error_threshold,
            "events_in_window": dict(counts),
            "total_alerts": total_alerts,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prune_window(self, now):
        """Remove events older than the rolling window."""
        cutoff = now - self.window_seconds
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

    def _check_threshold(self, line, severity):
        """Fire an alert if the error threshold is exceeded."""
        error_count = sum(
            1
            for _, sev in self._events
            if sev in ("ERROR", "CRITICAL")
        )
        if error_count >= self.error_threshold:
            alert = Alert(
                severity=severity,
                message=(
                    f"High error rate detected: {error_count} errors "
                    f"in the last {self.window_seconds}s "
                    f"(threshold: {self.error_threshold})"
                ),
                source_line=line,
            )
            with self._alerts_lock:
                self._alerts.append(alert)

    def _tail_file(self):
        """Tail the log file and process new lines."""
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                # Jump to end of file
                f.seek(0, 2)
                while not self._stop_event.is_set():
                    line = f.readline()
                    if line:
                        self.process_line(line)
                    else:
                        time.sleep(0.5)
        except FileNotFoundError:
            # File doesn't exist yet — wait and retry
            while not self._stop_event.is_set():
                try:
                    open(self.log_file, "a", encoding="utf-8").close()
                    break
                except OSError:
                    time.sleep(2)
