from enum import Enum
from typing import Optional, Annotated
from pydantic import BaseModel, Field
from pydantic.types import StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

class ReturnFormat(str, Enum):
    none = "none"
    saytxt = "saytxt"
    saywav = "saywav"
    both = "saytxt,saywav"

class ErrorResponse(BaseModel):
    detail: str

class SynthesizeRequest(BaseModel):
    text: NonEmptyStr = Field(..., description="Текст для TTS")

class SynthesizeResponse(BaseModel):
    wav_base64: Optional[str] = Field(None, description="WAV в base64")

class CommonRequest(BaseModel):
    text: NonEmptyStr
    format: ReturnFormat = ReturnFormat.none

class CommonResponse(BaseModel):
    text: Optional[str] = Field(None, description="Синтезированный текст")
    wav_base64: Optional[str] = Field(None, description="WAV в base64")
