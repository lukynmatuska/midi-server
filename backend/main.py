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

from mido import get_input_names, get_output_names, open_input, Message
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
async def racers_to_start():
    print("Racers to the starting line!")
    return JSONResponse(content={"message": "Racers to the starting line!"})


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
                asyncio.run(broadcast_midi(msg))
    except Exception as e:
        print(f"Error in MIDI listener: {e}")


async def broadcast_midi(msg: Message):
    data = msg.dict()
    disconnected = []
    for client in connected_clients:
        try:
            await client.send_text(json.dumps(data))
        except Exception as e:
            print(f"Client disconnected or error: {e}")
            disconnected.append(client)
    for client in disconnected:
        connected_clients.remove(client)

def start_midi_thread():
    devices = get_input_names()
    if not devices:
        print("No MIDI input devices found.")
        return

    for device_name in devices:
        print(f"Starting MIDI listener for: {device_name}")
        thread = threading.Thread(
            target=midi_listener, args=(device_name,), daemon=True
        )
        thread.start()
