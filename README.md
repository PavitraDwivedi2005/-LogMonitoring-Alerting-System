# Log Monitoring & Alerting System

Hey there! 👋 Welcome to my log monitoring and alerting project. 

I built this system to learn more about observability, monitoring, and how to tie different tools together into a cohesive stack. It's not a crazy enterprise-grade system, but it's a solid, functional setup using Python (Flask), Prometheus, and Grafana that demonstrates the core concepts of monitoring logs and triggering alerts when things go wrong.

## What's under the hood?

I broke this down into a few main pieces:
- **The Flask App**: A lightweight web server that ingests logs. I wrote a custom `LogMonitor` class that tails these logs in the background, looks for `ERROR`, `WARNING`, and `CRITICAL` tags, and flags anomalies.
- **Prometheus**: I instrumented the Python code so it exposes metrics at `/metrics`. Prometheus scrapes this every 15 seconds to track request rates, error counts, and latency. I also set up some alert rules here.
- **Grafana**: For visualization, I hooked Grafana up to Prometheus. There's a pre-built dashboard that shows you exactly what's happening in the app in real-time.
- **Docker Compose**: To make life easier, the whole stack is containerized. One command brings everything up.

## Architecture Sketch

```text
┌─────────────────────────────────────────────────────┐
│                    Docker Compose                   │
│                                                     │
│  ┌─────────────┐  scrape   ┌──────────────────┐     │
│  │  Prometheus │◄───────── │  Python Flask App│     │
│  │  :9090      │  /metrics │  :5000           │     │
│  └──────┬──────┘           └──────────────────┘     │
│         │                         │                 │
│         │ datasource              │ monitors        │
│         ▼                         ▼                 │
│  ┌─────────────┐           ┌──────────────┐         │
│  │   Grafana   │           │  Log File    │         │
│  │   :3000     │           │ (sample.log) │         │
│  └─────────────┘           └──────────────┘         │
└─────────────────────────────────────────────────────┘
```

## How to run it locally

If you want to spin this up on your own machine, you just need Docker and Docker Compose installed.

1. Clone this repo and navigate into the folder.
2. Run the stack:
   ```bash
   docker-compose up -d --build
   ```
   *Note: It might take a minute or two the first time as it downloads the base images.*

3. Check out the services:
   - **The App**: [http://localhost:5000](http://localhost:5000) (Returns a quick JSON health check)
   - **Prometheus**: [http://localhost:9090](http://localhost:9090)
   - **Grafana**: [http://localhost:3000](http://localhost:3000)
     - Log in with `admin` / `admin`. 
     - Head over to the Dashboards section—you'll see the "Log Monitoring & Alerting System" dashboard already set up for you.

## Seeing it in action

An empty dashboard is pretty boring. I wrote a quick load testing script to generate some fake traffic and trigger the alerts so you can see the graphs move.

Make sure you have the `requests` library installed (`pip install requests`), and then run:

```bash
python load_test.py
```

This will run for about 60 seconds, firing off a mix of good and bad requests to the app. Keep an eye on the Grafana dashboard while this runs—you'll see the error rates spike and the active alerts counter go up.

## What triggers an alert?

I configured Prometheus to fire alerts based on a few different rules:
- **HighErrorRate**: If the app throws too many HTTP errors (more than 0.1/sec for 2 minutes).
- **HighLatency**: If requests start getting sluggish (p95 latency > 1.0s for 5 minutes).
- **AppDown**: If the Flask container dies or becomes unreachable.
- **LogMonitorTriggered**: If the internal Python monitor detects a burst of `ERROR` or `CRITICAL` lines in the raw log file.

---
Feel free to poke around the code or use this as a starting point for your own monitoring setup!
