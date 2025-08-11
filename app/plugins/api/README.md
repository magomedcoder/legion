## HTTP API

### `GET /tts-wav`
Генерирует речь из текста (режим ответа - WAV в base64)

**Query:**
- `text` - произносимый текст (строка)

```json
{
  "wav_base64": "<base64-данные WAV>"
}
```

---

### `GET /send-txt-cmd`
Отправляет **команду** в текущий контекст (или глобально, если контекста нет)

**Query:**
- `cmd` - текст команды
- `format` - `none | saytxt | saywav | saytxt,saywav` (по умолчанию `"none"`)

---

### `GET /send-raw-txt`
Отправляет **сырую фразу**, как будто её сказал пользователь

**Query:**
- `txt` - распознанная фраза
- `format` - `none | saytxt | saywav | saytxt,saywav`

**Response:**
- `NO_VA_NAME`, если ассистент не распознан;
- иначе объект/строка согласно `format`

---

## WebSocket

### `/ws-raw-text`

```json
{
    "txt": "легион поставь таймер 5 минут",
    "format": "saytxt"
}
```

---

### `/ws-raw-text-cmd`

```json
{
    "txt": "таймер 5 минут",
    "format": "saytxt,saywav"
}
```

---

### `/ws-mic`
Стриминг **байтов аудио** для распознавания (при `enable_ws_asr=true`)
48000 Гц, format: `"saytxt,saywav"`

Формат аудио: raw PCM 16-bit, mono, Little-Endian

---

## Форматы ответов

- **`none`** - пустая
- **`saytxt`** - `{ "text": "..." }`
- **`saywav`** - `{ "wav_base64": "<base64 WAV>" }`
- **`saytxt,saywav`** - оба ключа
