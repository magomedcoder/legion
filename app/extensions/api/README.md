## HTTP API

### `GET /api/v1/health`

Проверка состояния сервиса

**Response 200**

```json
{
  "status": "ok"
}
```

---

| Значение        | Ответ                                          |
| --------------- | ---------------------------------------------- |
| `none`          | `{"text": null, "wav_base64": null}`           |
| `saytxt`        | `{"text": "...", "wav_base64": null}`          |
| `saywav`        | `{"text": null, "wav_base64": "<base64 WAV>"}` |
| `saytxt,saywav` | `{"text": "...", "wav_base64": "<...>"}`       |

---

### `POST /api/v1/synthesize`

Синтезирует речь из текста, возвращает WAV в base64

**Request (JSON)**

```json
{
  "text": "привет"
}
```

**Response 200**

```json
{
  "wav_base64": "<base64-данные WAV>"
}
```

---

### `POST /api/v1/commands`

Отправляет **команду** ассистенту (в текущем контексте)

**Request (JSON)**

```json
{
  "text": "включи таймер на 5 минут",
  "format": "none | saytxt | saywav | saytxt,saywav"
}
```

**Response 202 (пример)**

```json
{
  "text": "ставлю таймер на 5 минут",
  "wav_base64": "<...>"
}
```

---

### `POST /api/v1/utterances`

Передаёт **сырую фразу** (распознанный текст) для обработки ассистентом

**Request (JSON)**

```json
{
  "text": "легион поставь таймер 5 минут",
  "format": "saytxt"
}
```

**Response 200**

```json
{
  "text": "ставлю таймер на 5 минут"
}
```

**Response 404**

```json
{
  "detail": "Ассистент не распознан в фразе"
}
```

---

## WebSocket API

### `/ws/asr/stream`

Потоковая передача **аудио** для распознавания речи (ASR) и одновременного получения ответа

- Частота дискретизации: **48000 Гц**
- Формат входных данных: **raw PCM 16-bit, mono, Little-Endian**
- Формат выхода: JSON с полями:

```json
{
  "heard": "<что распознано (partial или final)>",
  "text": "<ответ или null>",
  "wav_base64": "<озвучка в base64 или null>"
}
```

---

### `/ws/commands`

Передача команд в режиме WebSocket

**Вход**

```json
{
  "text": "таймер 5 минут",
  "format": "saytxt,saywav"
}
```

**Выход**

```json
{
  "text": "ставлю таймер на 5 минут",
  "wav_base64": "<...>"
}
```

---

### `/ws/utterances`

Передача «сырых» фраз в режиме WebSocket

**Входящее сообщение (JSON)**

```json
{
  "text": "легион поставь таймер 5 минут",
  "format": "saytxt"
}
```

**Исходящее сообщение (JSON)**

```json
{
  "text": "ставлю таймер на 5 минут"
}
```
