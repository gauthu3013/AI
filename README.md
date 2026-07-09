# TwinCheck

**AI agent-assisted digital twin platform for end-to-end data center & AI factory design validation.**

Engineers sign in with their LTTS credentials, upload the three discipline deliverables, and three
AI agents extract structured data from each document and check it for errors. The extracted data is
merged into a **digital twin** of the facility — the power chain and the cooling chain — and a
validation layer checks the design **end-to-end across disciplines**. Results appear on a live
dashboard: capacity meters, a reviewer summary, and a findings table with exact document locations.

## How it works

```
LTTS login (email + PS Number)
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  Upload deliverables                                  │
│   • Electrical  — Earthing Calculation + Power System │──▶ Electrical agent
│   • Mechanical  — Cooling Equipment Data Sheets       │──▶ Mechanical agent
│   • Process     — Equipment List (IT + mechanical)    │──▶ Process agent
└───────────────────────────────────────────────────────┘
        │  each agent: extract structured data + per-document checks
        ▼
   Digital twin builder  ──  merges the three extracts into one facility model
        │
        ▼
   End-to-end validator  ──  IT load ≤ UPS ≤ transformer ≤ utility feed
                             heat load ≤ cooling capacity (with N+1)
                             tag reconciliation across disciplines
        │
        ▼
   Dashboard  ──  capacity meters · verdict tiles · AI reviewer summary · findings table
```

### The agents

| Agent | Deliverable | Checks |
|---|---|---|
| **Electrical** | Earthing calculation + power system summary | Recomputes conductor sizing (IEEE 80 / IS 3043 simplified), grid resistance vs limit, step/touch potentials vs tolerable limits, missing inputs |
| **Mechanical** | Cooling equipment data sheets | Mandatory fields, tag format, design ≥ operating temperature/pressure |
| **Process** | Equipment list | Duplicate tags, missing loads, quantity × unit = total consistency |
| **Twin validator** | (all three) | IT load vs UPS vs transformer vs utility; cooling capacity & N+1 redundancy; every listed mechanical item has a data sheet |

### Optional Claude summary

If `ANTHROPIC_API_KEY` is set, a fourth agent asks Claude (`claude-opus-4-8`) to write the
executive reviewer summary from the twin state and findings. Without a key the platform falls back
to a rule-based summary, so the full demo works offline.

## Run it

```bash
pip install -r requirements.txt
python samples/generate_samples.py     # regenerate demo deliverables (already committed)
uvicorn app.main:app --port 8000
```

Open http://localhost:8000 and sign in with any `@ltts.com` email and a 5–8 digit PS Number
(the login is a demo mock — no real SSO).

## Demo script (2 minutes)

1. Sign in (e.g. `firstname.lastname@ltts.com` / `123456`).
2. On each upload card, click **Download sample deliverable**, then upload it and click **Analyze**.
3. Open the **validation dashboard**. The samples contain deliberately seeded errors, so the twin
   lights up:
   - **UPS meter red** — 2,400 kW IT load vs 2,000 kW UPS capacity (found by cross-referencing the
     process equipment list against the electrical power summary).
   - **N+1 cooling red** — losing one 1,200 kW chiller leaves less capacity than the heat load.
   - **CH-03 flagged** — in the equipment list but has no mechanical data sheet.
   - Document-level errors: undersized earthing conductor (recomputed vs stated), touch potential
     over limit, design pressure below operating pressure, missing capacity field, duplicate tag,
     missing unit load.
4. Every finding carries its file / sheet / row, so it is directly actionable.

## Project layout

```
app/main.py              FastAPI app: login, uploads, dashboard API, static hosting
app/auth.py              Mock LTTS login (email domain + PS Number format)
app/parsers.py           .xlsx parsing helpers (key/value sheets + table sheets)
app/agents/electrical.py    Electrical discipline agent
app/agents/mechanical.py    Mechanical discipline agent
app/agents/process_agent.py Process discipline agent
app/agents/twin.py          Digital twin builder + end-to-end validator
app/agents/summarizer.py    Claude summary agent (rule-based fallback)
static/                  Frontend (vanilla HTML/CSS/JS, dark theme)
samples/                 Demo deliverables with seeded errors + generator script
```

*Hackathon prototype — the login is mocked, documents are held in memory per session, and design
assumptions (30% auxiliary load, heat load = IT load) are simplified for the demo.*
