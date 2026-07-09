# Monsoon Twin

**AI agent-assisted digital twin for monsoon preparedness in a chemical plant — Electrical & Process disciplines.**

> We collect real-time Electrical and Process parameters, update the Digital Twin, and use AI to
> predict monsoon-related risks and recommend preventive actions before flooding or equipment
> failure occurs.

Moves the plant from a manual monsoon checklist to a predictive system: a live digital twin models
every critical Electrical and Process asset, two AI risk agents continuously analyze it, and a
single dashboard shows exactly five things per risk — **risk level, affected area/equipment,
predicted problem, estimated time to problem, and recommended action.**

## How it works

```
Simulated plant + weather data                 ("user inputs → plant operational data")
        │
        ▼
Digital twin state (app/twin_state.py)          live Electrical + Process asset parameters
        │
        ▼
Monsoon simulator (app/simulator.py)            advances the state every tick — rainfall drives
        │                                       water levels, sump/drain levels, humidity, etc.
        ▼
Local cloud storage (app/storage.py)            every tick persisted to SQLite (data/twin_history.db)
        │
        ▼
Risk agents (app/agents/)                       Electrical agent + Process agent read the twin,
        │                                       compare against configured limits, predict risk
        ▼
Dashboard (static/)                              risk level · affected equipment · predicted problem
                                                  · ETA · recommended action — refreshed live
```

### The agents

| Agent | Parameters checked | Predicts |
|---|---|---|
| **Electrical** (`app/agents/electrical_risk.py`) | Water level near substation/MCC, panel-room humidity, water-ingress status, leakage current / earth-fault alarm, breaker status, UPS/DG availability, insulation-resistance trend, outdoor motor current | Flooding risk, moisture/condensation risk, water-ingress alert, electrical safety risk, insulation deterioration, emergency-power readiness |
| **Process** (`app/agents/process_risk.py`) | Rainfall, sump/drain/dyke level and rate of rise, dewatering-pump status, discharge pressure, flow, critical-equipment availability | Overflow prediction with an estimated time-to-problem, drain blockage risk, pump availability/performance risk |

Each agent returns exactly the dashboard's five fields per asset. A third agent
(`app/agents/narrator.py`) optionally asks Claude (`claude-opus-4-8`) to write a 2–4 sentence
control-room shift-handover briefing from the risk table; without an API key it falls back to a
rule-based briefing, so the whole system works offline.

### Example output (matches the brief)

Triggering **Heavy rain** + injecting **"Flood / water ingress" on MCC-02** and **"Trip duty pump"
on Sump-01** reproduces the brief's two worked examples almost verbatim:

- **MCC-02 — HIGH RISK:** Water ingress risk near the MCC/substation; panel-room humidity above
  the configured limit. *Inspect water ingress and cable-entry sealing, check panel space-heater
  operation, test insulation resistance.*
- **Sump-01 — HIGH RISK:** Duty dewatering pump tripped; critical dewatering equipment
  unavailable, overflow predicted in **~34 min**. *Start the standby pump and check pump
  performance, restore duty pump availability immediately.*

## Run it

**Easiest — one click:**
- **Windows:** double-click **`run.bat`**
- **macOS / Linux:** run **`./run.sh`** (or `bash run.sh`)

It installs the dependencies on first run, starts the server, and opens
http://localhost:8000 in your browser. Keep the window open while you use the
app; press `Ctrl+C` (or close the window) to stop it.

**Or manually:**

```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Then open http://localhost:8000. No login — the dashboard loads straight into
the live twin.

> **First time on Windows?** Install Python 3.10+ from
> [python.org](https://www.python.org/downloads/) and **tick "Add python.exe to
> PATH"** during setup, then double-click `run.bat`.

### Open it on other devices (same Wi-Fi)

To let phones or other laptops on the same network open the dashboard, start the
server bound to all interfaces and browse to the host machine's IP:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Find the host's local IP (`ipconfig` on Windows, `hostname -I` on Linux,
`ipconfig getifaddr en0` on macOS) and open `http://<that-ip>:8000` on the other
device. All devices share the same live twin.

### Demo script (2 minutes)

1. Watch the baseline: calm rainfall, every asset LOW, control-room briefing says "no risks
   detected."
2. Click **Heavy** rainfall. Over the next ~1–2 minutes (10x playback), watch Storm Drain-01 and
   the tank-farm MCC drift toward MEDIUM on their own — the twin is predicting, not just alarming.
3. For the guaranteed payoff moment, use **"Inject a fault to demo instantly"**: pick `MCC-02` →
   `Flood / water ingress`, click Inject; then `Sump-01` → `Trip duty pump`, click Inject. Both
   flip to HIGH within a couple of seconds, with the ETA and recommended action shown live.
4. Point out the five dashboard columns, the control-room briefing banner, and that every reading
   underneath is being written to local SQLite storage in real time (`data/twin_history.db`).
5. Click **Reset scenario** to return to the calm baseline for a re-run.

### Controls

- **Rainfall** — Calm / Moderate / Heavy / Extreme presets drive the whole simulation.
- **Playback** — 1x / 10x / 40x / 120x simulated-time speed, plus Pause.
- **Inject a fault** — pick any Electrical or Process asset and force a specific failure
  (flood, earth fault, breaker trip, UPS/DG loss, IR decline / pump trip, blockage, high level)
  for an instant, repeatable demo of any risk scenario. "Clear all faults" returns every asset to
  healthy readings without resetting the rainfall or the clock.
- **Reset scenario** — returns the whole twin, rainfall, and playback speed to the calm baseline.

## Project layout

```
app/main.py                 FastAPI app: state/risk/history/control endpoints, static hosting
app/twin_state.py            Digital twin state: every Electrical & Process asset + limits
app/simulator.py              Background monsoon-scenario physics (rainfall -> levels/humidity/etc.)
app/control.py                 Manual override API: rainfall presets, fault injection, speed, reset
app/storage.py                  SQLite persistence — the "local cloud storage" leg of the pipeline
app/agents/electrical_risk.py    Electrical discipline risk agent
app/agents/process_risk.py        Process discipline risk agent
app/agents/risk.py                 Aggregates + sorts the risk table
app/agents/narrator.py              Claude control-room briefing (rule-based fallback)
static/                       Frontend (vanilla HTML/CSS/JS, dark theme, live-polling dashboard)
```

*Hackathon prototype — plant/weather data is simulated (no real sensors are wired up), and the
physics constants are simplified for a demo timescale rather than calibrated to a real site.*
