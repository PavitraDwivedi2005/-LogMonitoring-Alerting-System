"""
app.py
------
Flask web server for the Log Monitoring & Alerting System.

Exposes:
  GET  /           — health check and landing info
  GET  /logs       — recent log entries
  POST /logs       — add a new log entry
  GET  /alerts     — triggered alerts
  GET  /stats      — monitoring statistics
  GET  /metrics    — Prometheus metrics endpoint
"""

import os
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, request, jsonify, Response
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    REGISTRY,
)

from log_monitor import LogMonitor
from logger import setup_logger

# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════

LOG_FILE = os.getenv("LOG_FILE", "sample.log")
APP_PORT = int(os.getenv("APP_PORT", "5000"))
ERROR_THRESHOLD = int(os.getenv("ERROR_THRESHOLD", "5"))
WINDOW_SECONDS = int(os.getenv("WINDOW_SECONDS", "60"))

# ═══════════════════════════════════════════════════════════════════
# Structured Logger
# ═══════════════════════════════════════════════════════════════════

logger = setup_logger(name="app", log_file="app.log")

# ═══════════════════════════════════════════════════════════════════
# Prometheus Metrics
# ═══════════════════════════════════════════════════════════════════

REQUEST_COUNT = Counter(
    "request_count_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status"],
)

ERROR_COUNT = Counter(
    "error_count_total",
    "Total application errors",
    ["type"],
)

REQUEST_LATENCY = Histogram(
    "request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

ALERTS_TRIGGERED = Counter(
    "alerts_triggered_total",
    "Total number of alerts triggered by the log monitor",
    ["severity"],
)

LOGS_PROCESSED = Counter(
    "logs_processed_total",
    "Total log lines processed",
    ["severity"],
)

ACTIVE_ALERTS = Gauge(
    "active_alerts",
    "Number of currently active (unresolved) alerts",
)

# ═══════════════════════════════════════════════════════════════════
# Flask Application
# ═══════════════════════════════════════════════════════════════════

app = Flask(__name__)

# Initialize the log monitor
monitor = LogMonitor(
    log_file=LOG_FILE,
    error_threshold=ERROR_THRESHOLD,
    window_seconds=WINDOW_SECONDS,
)

# In-memory store for recently posted log lines
recent_logs = []
MAX_RECENT_LOGS = 200


# ── Request middleware ───────────────────────────────────────────
@app.before_request
def before_request():
    """Attach timing and request-id to each request."""
    request._start_time = time.time()
    request._request_id = str(uuid.uuid4())[:8]


@app.after_request
def after_request(response):
    """Record metrics and log the request."""
    latency = time.time() - getattr(request, "_start_time", time.time())
    endpoint = request.path
    method = request.method
    status = str(response.status_code)

    # Prometheus metrics
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(latency)

    if response.status_code >= 400:
        ERROR_COUNT.labels(type=f"http_{status}").inc()

    # Structured log
    logger.info(
        "request_completed",
        extra={
            "request_id": getattr(request, "_request_id", ""),
            "method": method,
            "path": endpoint,
            "status": int(status),
            "latency_ms": round(latency * 1000, 2),
        },
    )
    return response


# ── Routes ───────────────────────────────────────────────────────

@app.route("/")
def index():
    """Health check and application info."""
    return jsonify({
        "service": "Log Monitoring & Alerting System",
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoints": {
            "GET /": "This health check",
            "GET /logs": "Recent log entries",
            "POST /logs": "Submit a new log entry",
            "GET /alerts": "Triggered alerts",
            "GET /stats": "Monitoring statistics",
            "GET /metrics": "Prometheus metrics",
        },
    })


@app.route("/logs", methods=["GET"])
def get_logs():
    """Return recent log entries."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify({
        "count": min(limit, len(recent_logs)),
        "logs": recent_logs[-limit:],
    })


@app.route("/logs", methods=["POST"])
def post_log():
    """
    Accept a new log entry.

    Body (JSON):
      { "message": "..." }
    or
      { "message": "...", "level": "ERROR" }
    """
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    level = data.get("level", "INFO").upper()

    if not message:
        ERROR_COUNT.labels(type="bad_request").inc()
        return jsonify({"error": "message is required"}), 400

    # Build log line
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"{timestamp} {level}  {message}"

    # Store in memory
    entry = {
        "timestamp": timestamp,
        "level": level,
        "message": message,
    }
    recent_logs.append(entry)
    if len(recent_logs) > MAX_RECENT_LOGS:
        recent_logs.pop(0)

    # Append to log file
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except OSError as exc:
        logger.error("Failed to write to log file", extra={"error": str(exc)})

    # Process through the monitor
    severity = monitor.process_line(log_line)
    if severity:
        LOGS_PROCESSED.labels(severity=severity).inc()
        if severity in ("ERROR", "CRITICAL"):
            ALERTS_TRIGGERED.labels(severity=severity).inc()

    logger.info(
        "log_entry_received",
        extra={"level": level, "message": message},
    )

    return jsonify({"status": "accepted", "entry": entry}), 201


@app.route("/alerts")
def get_alerts():
    """Return triggered alerts."""
    limit = request.args.get("limit", 50, type=int)
    alerts = monitor.get_alerts(limit=limit)

    # Update active alert gauge
    unresolved = sum(1 for a in alerts if not a.get("resolved"))
    ACTIVE_ALERTS.set(unresolved)

    return jsonify({
        "count": len(alerts),
        "alerts": alerts,
    })


@app.route("/stats")
def get_stats():
    """Return current monitoring statistics."""
    return jsonify(monitor.get_stats())


@app.route("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        generate_latest(REGISTRY),
        mimetype=CONTENT_TYPE_LATEST,
    )


# ═══════════════════════════════════════════════════════════════════
# Startup
# ═══════════════════════════════════════════════════════════════════

def create_app():
    """Factory function for the Flask app."""
    # Pre-load existing log lines into the monitor
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                severity = monitor.process_line(line)
                if severity:
                    LOGS_PROCESSED.labels(severity=severity).inc()
                entry_parts = line.strip().split(None, 3)
                if len(entry_parts) >= 4:
                    recent_logs.append({
                        "timestamp": f"{entry_parts[0]} {entry_parts[1]}",
                        "level": entry_parts[2],
                        "message": entry_parts[3],
                    })
        logger.info(
            "loaded_existing_logs",
            extra={"file": LOG_FILE, "lines": len(recent_logs)},
        )
    except FileNotFoundError:
        logger.info("log_file_not_found", extra={"file": LOG_FILE})

    # Start the background file monitor
    monitor.start()
    logger.info("log_monitor_started", extra={"file": LOG_FILE})

    return app


if __name__ == "__main__":
    application = create_app()
    logger.info("server_starting", extra={"port": APP_PORT})
    application.run(
        host="0.0.0.0",
        port=APP_PORT,
        debug=False,
    )
