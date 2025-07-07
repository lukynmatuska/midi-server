from pydantic import BaseModel
from datetime import datetime


class RootResponse(BaseModel):
    git: str
    time: datetime

    class Config:
        from_attributes = True

class MidiDevicesResponse(BaseModel):
    input: list[str]
    output: list[str]

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    message: str

    class Config:
        from_attributes = True
