import os
import sys
import json
import asyncio
import threading
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from mido import get_input_names, get_output_names, open_input, open_output, Message
from git import Repo

from responses import RootResponse, MidiDevicesResponse, MessageResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_midi_thread()
    yield
    # Shutdown (optional cleanup)
    # stop_midi_thread() if needed


app = FastAPI(
    lifespan=lifespan,
    swagger_ui_parameters={
        "syntaxHighlight.theme": "monokai",
        "persistAuthorization": True,
        "tryItOutEnabled": True,
    },
    title="MIDI Server",
    description="REST API for sending MIDI commands",
)

DEFAULT_MIDI_DEVICE = "X18/XR18:X18/XR18 MIDI 1 24:0"
DEFAULT_CHANNELS = [0, 15]
DEFAULT_CONTROL = 0
DEFAULT_STEPS = 20
DEFAULT_STEP_DELAY = 0.03  # in seconds (30 ms)
MAX_VALUE = 127
MIN_VALUE = 0

try:
    origins = json.loads(os.getenv("CORS_ORIGINS"))
except:  # noqa: E722
    print(
        'Missing defined ENV variable CORS_ORIGINS, using default value ["*"].',
        file=sys.stderr,
    )
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_clients: set[WebSocket] = set()


def get_git_commit_hash() -> str:
    try:
        repo = Repo(search_parent_directories=True)
        commit_hash = repo.head.commit.hexsha
        return commit_hash
    except Exception as e:
        return f"Git hash not available: {e}"


@app.get("/", response_model=RootResponse)
async def root():
    return {
        "git_commit": get_git_commit_hash(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

prefix = "/api/v1"

@app.get(f"{prefix}/midi_devices", response_model=MidiDevicesResponse)
async def list_midi_devices():
    return {
        "input": get_input_names(),
        "output": get_output_names()
    }


@app.post(f"{prefix}/start", response_model=MessageResponse)
async def racers_to_start(
    midi_device_name: str = DEFAULT_MIDI_DEVICE,
    channels: list[int] = DEFAULT_CHANNELS,
    steps: int = DEFAULT_STEPS,
    step_delay: float = DEFAULT_STEP_DELAY,
    control: int = DEFAULT_CONTROL
):
    try:
        with open_output(midi_device_name) as outport:
            for val in reversed(range(MIN_VALUE, MAX_VALUE + 1, MAX_VALUE // steps)):
                for ch in channels:
                    msg = Message("control_change", channel=ch, control=control, value=val)
                    outport.send(msg)
                await asyncio.sleep(step_delay)
        return JSONResponse(content={"message": f"MIDI fade-out sent ({steps} steps)"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Failed to send MIDI: {e}"})


@app.post(f"{prefix}/go", response_model=MessageResponse)
async def racers_go():
    print("Racers are running!")
    return JSONResponse(content={"message": "Racers are running!"})



@app.websocket("/ws/midi")
async def websocket_midi_handler(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    print("WebSocket client connected.")

    try:
        await websocket.send_json({
            "input_devices": get_input_names(),
            "output_devices": get_output_names()
        })

        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        print("WebSocket client disconnected.")


def midi_listener(device_name: str):
    print(f"Listening to MIDI input: {device_name}")
    try:
        with open_input(device_name) as port:
            for msg in port:
                print(f"Received MIDI: {msg}")
                asyncio.run(broadcast_midi(device_name=device_name, midi_msg=msg))
    except Exception as e:
        print(f"Error in MIDI listener: {e}")


async def broadcast_midi(midi_msg: Message, device_name: str = "unknown"):
    midi_data = midi_msg.dict()
    disconnected = []
    for client in connected_clients:
        try:
            await client.send_json({
                "device": device_name,
                "data": json.dumps(midi_data)
            })
        except Exception as e:
            print(f"Client disconnected or error: {e}")
            disconnected.append(client)
    for client in disconnected:
        connected_clients.remove(client)

def start_midi_thread():
    devices = get_input_names()
    if not devices:
        print(
            "No MIDI input devices found.", 
            file=sys.stderr
        )
        return

    for device_name in devices:
        print(f"Starting MIDI listener for: {device_name}")
        thread = threading.Thread(
            target=midi_listener, args=(device_name,), daemon=True
        )
        thread.start()
