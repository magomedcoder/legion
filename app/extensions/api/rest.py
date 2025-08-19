import os
from fastapi import APIRouter, FastAPI, HTTPException, status, UploadFile, File, Form
from app.core.core import Core
from .models import SynthesizeRequest, SynthesizeResponse, CommonResponse, CommonRequest, ErrorResponse
from .utils import run_cmd, send_raw_txt, normalize_speech_response
import shutil
from app.extensions.stt_speaker_vosk_speechbrain.main import process_audio_file

def attach_rest(core: Core, app: FastAPI) -> None:
    router = APIRouter(prefix="/api/v1", tags=["API"])

    @router.get("/health", response_model=dict, summary="Проверка состояния сервиса")
    async def health():
        return {"status": "ok"}

    @router.post("/synthesize",
        response_model=SynthesizeResponse,
        responses={
            200: {"model": SynthesizeResponse},
            400: {"model": ErrorResponse}
        },
        summary="Синтез речи (WAV base64)",
    )
    async def synthesize(req: SynthesizeRequest):
        try:
            core.remote_tts = "saywav"
            core.remote_tts_result = ""
            core.play_voice_assistant_speech(req.text)
            result = core.remote_tts_result

            if not isinstance(result, dict) or "wav_base64" not in result:
                raise HTTPException(status_code=400, detail="TTS вернул неожиданный формат")

            wav_b64 = result["wav_base64"]
            if isinstance(wav_b64, (bytes, bytearray)):
                wav_b64 = wav_b64.decode("utf-8")

            return SynthesizeResponse(wav_base64=wav_b64)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"TTS ошибка: {e}")

    @router.post("/commands",
        response_model=CommonResponse,
        responses={
            200: {"model": CommonResponse},
            400: {"model": ErrorResponse}
        },
        status_code=status.HTTP_202_ACCEPTED,
        summary="Отправить команду ассистенту",
    )
    async def send_command(req: CommonRequest):
        try:
            result = run_cmd(core, req.text, req.format.value)
            return normalize_speech_response(result)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка выполнения команды: {e}")

    @router.post("/utterances",
        response_model=CommonResponse,
        responses={
            200: {"model": CommonResponse},
            400: {"model": ErrorResponse},
            404: {"model": ErrorResponse}
        },
        summary="Передать распознанную фразу (raw)",
    )
    async def send_utterance(req: CommonRequest):
        try:
            result = send_raw_txt(core, req.text, req.format.value)
            if result == "NO_VA_NAME":
                raise HTTPException(status_code=404, detail="Ассистент не распознан в фразе")
            return normalize_speech_response(result)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка обработки фразы: {e}")

    @router.post("/stt-speaker/upload",
        response_model=dict,
        summary="Загрузка аудио и получение STT+спикеров"
    )
    async def stt_upload(
        file: UploadFile = File(..., description="Аудио"),
        diarize: bool = Form(True),
        return_srt: bool = Form(True),
    ):
        temp_path = None
        try:
            suffix = os.path.splitext(file.filename or "")[-1] or ".bin"
            basename = f"upload_{os.getpid()}_{os.urandom(4).hex()}{suffix}"
            temp_path = os.path.join(os.path.join(os.getcwd(), "runtime", "tmp"), basename)

            with open(temp_path, "wb") as out:
                shutil.copyfileobj(file.file, out)

            result = process_audio_file(core, temp_path, diarize=diarize)
            if not return_srt and isinstance(result, dict):
                result.pop("srt", None)

            return {"result": result}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка обработки: {e}")
        finally:
            try:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception:
                pass

    app.include_router(router)