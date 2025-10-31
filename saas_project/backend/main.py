
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import List, Dict, Any

# --- Data Models ---
# These models define the structure of the data we expect from the agent.
class HostDetails(BaseModel):
    hostname: str
    os_type: str
    os_version: str

class Package(BaseModel):
    name: str
    version: str

class CISResult(BaseModel):
    check: str
    status: str
    evidence: str

class AgentPayload(BaseModel):
    host_details: HostDetails
    installed_packages: List[Package]
    cis_results: List[CISResult]

# --- Application Setup ---
app = FastAPI(
    title="SaaS Security Agent Backend",
    description="Receives and displays data from Linux security agents."
)

# In-memory database
# A simple dictionary to store data. In a real app, you'd use a proper database.
# The key is the hostname.
DB: Dict[str, AgentPayload] = {}

# Setup for HTML templates
templates = Jinja2Templates(directory="templates")

# --- API Endpoints ---

@app.post("/ingest")
def ingest_data(payload: AgentPayload):
    """Receives data from the agent and stores it in our in-memory DB."""
    hostname = payload.host_details.hostname
    print(f"Received data from host: {hostname}")
    DB[hostname] = payload
    return {"status": "success", "hostname": hostname}

@app.get("/api/hosts", response_model=List[str])
def get_hosts():
    """Returns a list of all hostnames that have reported data."""
    return list(DB.keys())

@app.get("/api/hosts/{hostname}", response_model=AgentPayload)
def get_host_data(hostname: str):
    """Returns all data for a specific host."""
    if hostname in DB:
        return DB[hostname]
    return {"error": "Host not found"}

# --- Frontend HTML Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def view_dashboard(request: Request):
    """Displays the main dashboard with a list of hosts."""
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "hosts": list(DB.keys())}
    )

@app.get("/hosts/{hostname}", response_class=HTMLResponse)
async def view_host_details(request: Request, hostname: str):
    """Displays the detailed information for a single host."""
    if hostname not in DB:
        return HTMLResponse("<h2>Host not found</h2>", status_code=404)
    
    host_data = DB[hostname]
    
    # Calculate summary
    total_checks = len(host_data.cis_results)
    passed_checks = sum(1 for r in host_data.cis_results if r.status == 'pass')
    
    return templates.TemplateResponse(
        "host_details.html", 
        {
            "request": request, 
            "host": host_data,
            "total_checks": total_checks,
            "passed_checks": passed_checks
        }
    )
