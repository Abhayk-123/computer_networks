"""
Network Simulator - FastAPI Backend
Run: py -m uvicorn main:app --reload --port 8000
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine import SimulationEngine
from protocols import CRC, CSMACD, StopAndWait, GoBackN, SelectiveRepeat

app = FastAPI(
    title="Network Simulator API",
    description="OSI Protocol Stack Simulator — Physical & Data Link Layers",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = SimulationEngine()


# ── Request Models ──────────────────────────────────

class AddDeviceRequest(BaseModel):
    device_id: str
    device_type: str
    name: str = None

class ConnectRequest(BaseModel):
    source_id: str
    target_id: str
    bandwidth: int = 100

class P2PRequest(BaseModel):
    host1_id: str
    host2_id: str
    message: str

class HubBroadcastRequest(BaseModel):
    sender_id: str
    hub_id: str
    message: str

class SwitchRequest(BaseModel):
    sender_id: str
    receiver_id: str
    switch_id: str
    message: str

class DualStarRequest(BaseModel):
    sender_id: str
    receiver_id: str
    hub1_id: str
    hub2_id: str
    switch_id: str
    message: str

class CRCRequest(BaseModel):
    data: str
    simulate_error: bool = False

class ARQRequest(BaseModel):
    num_frames: int = 6
    window_size: int = 4
    error_rate: float = 0.2


# ── Basic Routes ────────────────────────────────────

@app.get("/")
def root():
    return {"message": "Network Simulator API v2.0", "status": "running"}

@app.get("/topology")
def get_topology():
    return engine.get_topology()

@app.get("/events")
def get_events():
    return {"events": engine.get_events()}

@app.post("/reset")
def reset():
    engine.clear()
    return {"message": "Simulator reset"}


# ── Device & Link Routes ────────────────────────────

@app.post("/device")
def add_device(req: AddDeviceRequest):
    result = engine.add_device(req.device_id, req.device_type, req.name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/connect")
def connect_devices(req: ConnectRequest):
    result = engine.connect(req.source_id, req.target_id, req.bandwidth)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Simulation Routes ───────────────────────────────

@app.post("/simulate/p2p")
def simulate_p2p(req: P2PRequest):
    return engine.test_p2p(req.host1_id, req.host2_id, req.message)

@app.post("/simulate/hub-broadcast")
def simulate_hub(req: HubBroadcastRequest):
    return engine.test_hub_broadcast(req.sender_id, req.hub_id, req.message)

@app.post("/simulate/switch")
def simulate_switch(req: SwitchRequest):
    return engine.test_switch_unicast(req.sender_id, req.receiver_id,
                                       req.switch_id, req.message)

@app.post("/simulate/dual-star")
def simulate_dual_star(req: DualStarRequest):
    return engine.test_dual_star(req.sender_id, req.receiver_id,
                                  req.hub1_id, req.hub2_id,
                                  req.switch_id, req.message)


# ── Protocol Routes ─────────────────────────────────

@app.post("/protocol/crc")
def run_crc(req: CRCRequest):
    return CRC.run(req.data, req.simulate_error)

@app.post("/protocol/csmacd")
def run_csmacd():
    csma = CSMACD("demo_device")
    return csma.transmit("test_frame", channel_busy=True)

@app.post("/protocol/stop-and-wait")
def run_stop_and_wait(req: ARQRequest):
    frames = [f"Frame_{i}" for i in range(req.num_frames)]
    return StopAndWait(req.error_rate).simulate(frames)

@app.post("/protocol/go-back-n")
def run_gbn(req: ARQRequest):
    frames = [f"Frame_{i}" for i in range(req.num_frames)]
    return GoBackN(req.window_size, req.error_rate).simulate(frames)

@app.post("/protocol/selective-repeat")
def run_selective_repeat(req: ARQRequest):
    frames = [f"Frame_{i}" for i in range(req.num_frames)]
    return SelectiveRepeat(req.window_size, req.error_rate).simulate(frames)

@app.post("/protocol/all-arq")
def run_all_arq(req: ARQRequest):
    """Run all three ARQ protocols and return a side-by-side comparison."""
    frames = [f"Frame_{i}" for i in range(req.num_frames)]
    return {
        "stop_and_wait":    StopAndWait(req.error_rate).simulate(frames),
        "go_back_n":        GoBackN(req.window_size, req.error_rate).simulate(frames),
        "selective_repeat": SelectiveRepeat(req.window_size, req.error_rate).simulate(frames),
    }


# ── Quick Setup Routes ──────────────────────────────

@app.post("/setup/star-topology")
def setup_star():
    engine.clear()
    engine.add_device("hub1", "hub", "Hub-1")
    for i in range(1, 6):
        engine.add_device(f"pc{i}", "host", f"PC-{i}")
        engine.connect(f"pc{i}", "hub1")
    return engine.get_topology()

@app.post("/setup/switch-topology")
def setup_switch():
    engine.clear()
    engine.add_device("sw1", "switch", "Switch-1")
    for i in range(1, 6):
        engine.add_device(f"pc{i}", "host", f"PC-{i}")
        engine.connect(f"pc{i}", "sw1")
    return engine.get_topology()

@app.post("/setup/dual-star")
def setup_dual_star():
    engine.clear()
    engine.add_device("sw1", "switch", "Switch-1")
    engine.add_device("hub1", "hub", "Hub-1")
    engine.add_device("hub2", "hub", "Hub-2")
    engine.connect("hub1", "sw1")
    engine.connect("hub2", "sw1")
    for i in range(1, 6):
        engine.add_device(f"pc{i}", "host", f"PC-{i}")
        engine.connect(f"pc{i}", "hub1")
    for i in range(6, 11):
        engine.add_device(f"pc{i}", "host", f"PC-{i}")
        engine.connect(f"pc{i}", "hub2")
    return engine.get_topology()
