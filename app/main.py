"""TwinCheck — AI agent-assisted digital twin platform for end-to-end
data center / AI factory design validation.

Flow: LTTS login -> upload the three discipline deliverables -> discipline
agents extract + validate -> twin builder merges and runs end-to-end checks
-> dashboard shows the live twin and all findings.
"""

from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth
from .agents import electrical, mechanical, process_agent, summarizer, twin
from .parsers import ParseError

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
SAMPLES_DIR = ROOT / "samples"

DISCIPLINES = {
    "electrical": {"agent": electrical, "label": "Electrical — Earthing Calculation & Power System"},
    "mechanical": {"agent": mechanical, "label": "Mechanical — Cooling Equipment Data Sheets"},
    "process": {"agent": process_agent, "label": "Process — Equipment List (IT & Mechanical)"},
}

app = FastAPI(title="TwinCheck", version="1.0")

# token -> {discipline: {"filename", "extracted", "findings"}}
_uploads: dict[str, dict] = {}


class LoginRequest(BaseModel):
    email: str
    ps_number: str


def _require_session(token: str | None) -> dict:
    session = auth.get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Not logged in")
    return session


@app.post("/api/login")
def login(body: LoginRequest):
    token = auth.login(body.email, body.ps_number)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Use your LTTS email (name@ltts.com) and numeric PS Number (5-8 digits).")
    _uploads[token] = {}
    return {"token": token, "email": body.email.strip().lower()}


@app.post("/api/upload/{discipline}")
async def upload(discipline: str, file: UploadFile = File(...),
                 x_auth_token: str | None = Header(default=None)):
    _require_session(x_auth_token)
    if discipline not in DISCIPLINES:
        raise HTTPException(status_code=404, detail=f"Unknown discipline '{discipline}'")
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Please upload an .xlsx deliverable")

    data = await file.read()
    try:
        result = DISCIPLINES[discipline]["agent"].analyze(file.filename, data)
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _uploads.setdefault(x_auth_token, {})[discipline] = {
        "filename": file.filename,
        "extracted": result["extracted"],
        "findings": result["findings"],
    }
    return {
        "discipline": discipline,
        "filename": file.filename,
        "findings": result["findings"],
        "errors": sum(1 for f in result["findings"] if f["severity"] == "error"),
        "warnings": sum(1 for f in result["findings"] if f["severity"] == "warning"),
    }


@app.get("/api/dashboard")
def dashboard(x_auth_token: str | None = Header(default=None)):
    _require_session(x_auth_token)
    uploads = _uploads.get(x_auth_token, {})

    result = twin.build(
        uploads.get("electrical", {}).get("extracted"),
        uploads.get("mechanical", {}).get("extracted"),
        uploads.get("process", {}).get("extracted"),
    )

    all_findings = []
    per_discipline = {}
    for name, meta in DISCIPLINES.items():
        entry = uploads.get(name)
        per_discipline[name] = {
            "label": meta["label"],
            "uploaded": entry is not None,
            "filename": entry["filename"] if entry else None,
            "errors": sum(1 for f in (entry["findings"] if entry else []) if f["severity"] == "error"),
            "warnings": sum(1 for f in (entry["findings"] if entry else []) if f["severity"] == "warning"),
        }
        if entry:
            all_findings.extend(entry["findings"])
    all_findings.extend(result["findings"])

    severity_order = {"error": 0, "warning": 1, "info": 2}
    all_findings.sort(key=lambda f: severity_order.get(f["severity"], 3))

    summary = None
    if uploads:
        summary = summarizer.summarize(result["twin"], all_findings)

    return {
        "disciplines": per_discipline,
        "twin": result["twin"],
        "findings": all_findings,
        "summary": summary,
    }


@app.get("/api/samples")
def list_samples():
    files = sorted(p.name for p in SAMPLES_DIR.glob("*.xlsx")) if SAMPLES_DIR.exists() else []
    return {"files": files}


@app.get("/api/samples/{name}")
def get_sample(name: str):
    path = (SAMPLES_DIR / name).resolve()
    if path.parent != SAMPLES_DIR.resolve() or not path.exists() or path.suffix != ".xlsx":
        raise HTTPException(status_code=404, detail="Sample not found")
    return FileResponse(path, filename=name,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
