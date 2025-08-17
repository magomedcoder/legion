import time
import random
import re
from datetime import datetime
from typing import Any, Dict

from app.core.core import Core
from app.utils.num_to_text_ru import num2text

"""
    Голосовая команда: Приветствия, Дата/Время, Таймер (+список/удаление), Рандом (монета/кубик).

    Команды:
        привет|доброе утро                                      -> приветствие
        дата                                                    -> озвучить дату
        время                                                   -> озвучить время
        поставь таймер|поставь тайгер|таймер|тайгер [на ...]    -> таймер (по умолчанию 5 минут)
        таймеры|список таймеров                                 -> озвучить активные таймеры
        удали таймер|сбрось таймер|отмени таймер [N]            -> удалить конкретный таймер
        удали все таймеры|сбрось все таймеры|отмени все таймеры -> удалить все таймеры
        подбрось|брось монету|монетку                           -> монетка
        подбрось|брось кубик|кость                              -> кубик
        команды                                                 -> перечислить все доступные голосовые команды
        
    Опции:
        # время
        sayNoon: bool             - говорить «полдень» / «полночь» для 12:00 / 00:00
        skipUnits: bool           - не произносить единицы («час», «минуты»)
        unitsSeparator: str       - разделитель между часами и минутами
        skipMinutesWhenZero: bool - пропускать минуты, если 0
        # таймер
        wavRepeatTimes: int       - сколько раз проигрывать сигнал
        wavPath: str              - путь к WAV сигналу таймера
"""

def manifest() -> Dict[str, Any]:
    return {
        "name": "привет/дата/время/таймер/рандом",

        "options": {
            "sayNoon": False,
            "skipUnits": False,
            "unitsSeparator": ", ",
            "skipMinutesWhenZero": True,
            "wavRepeatTimes": 1,
            "wavPath": "assets/audio/timer.wav",
        },

        "commands": {
            "привет|доброе утро": _play_greetings,

            "дата": _play_date,
            "время": _play_time,

            "поставь таймер|поставь тайгер|таймер|тайгер": _set_timer,
            "таймеры|список таймеров": _list_timers,
            "удали таймер|сбрось таймер|отмени таймер": _cancel_timer,
            "удали все таймеры|сбрось все таймеры|отмени все таймеры": _cancel_all_timers,

            "подбрось|брось": {
                "монету|монетку": _play_coin,
                "кубик|кость": _play_dice,
            },

            "команды": _list_all_commands,
        }
    }

_last_list_ids: list[int] = []

def start(core: Core, manifest: Dict[str, Any]) -> None:
    pass

def _play_greetings(core: Core, phrase: str):
    greet_str = random.choice(["И тебе привет!", "Рада тебя видеть!"])
    core.play_voice_assistant_speech(greet_str)
    print(f"Сказала: {greet_str}")

def _play_date(core: Core, phrase: str):
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    weekday = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"][datetime.weekday(now)]
    core.play_voice_assistant_speech("сегодня " + weekday + ", " + _fmt_date_ru(date))

def _fmt_date_ru(date: str) -> str:
    day_list = ['первое', 'второе', 'третье', 'четвёртое', 'пятое', 'шестое', 'седьмое', 'восьмое', 'девятое', 'десятое', 'одиннадцатое', 'двенадцатое', 'тринадцатое', 'четырнадцатое', 'пятнадцатое', 'шестнадцатое', 'семнадцатое', 'восемнадцатое', 'девятнадцатое', 'двадцатое', 'двадцать первое', 'двадцать второе', 'двадцать третье', 'двадцать четвёртое', 'двадцать пятое', 'двадцать шестое', 'двадцать седьмое', 'двадцать восьмое', 'двадцать девятое', 'тридцатое', 'тридцать первое']
    month_list = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
    yyyy, mm, dd = date.split('-')
    return f"{day_list[int(dd)-1]} {month_list[int(mm)-1]}"

def _play_time(core: Core, phrase: str):
    opts = core.extension_options(__package__)
    sayNoon = bool(opts.get("sayNoon", False))
    skipUnits = bool(opts.get("skipUnits", False))
    unitsSeparator = opts.get("unitsSeparator", ", ")
    skipMinutesWhenZero = bool(opts.get("skipMinutesWhenZero", True))

    if skipUnits:
        units_minutes = (('', '', ''), 'f')
        units_hours = (('', '', ''), 'm')
    else:
        units_minutes = (('минута', 'минуты', 'минут'), 'f')
        units_hours = (('час', 'часа', 'часов'), 'm')

    now = datetime.now()
    hours = int(now.strftime("%H"))
    minutes = int(now.strftime("%M"))

    if sayNoon:
        if hours == 0 and minutes == 0:
            core.say("Сейчас ровно полночь")
            return
        elif hours == 12 and minutes == 0:
            core.say("Сейчас ровно полдень")
            return

    txt_hours = num2text(hours, units_hours)
    if minutes > 0 or not skipMinutesWhenZero:
        txt = "Сейчас " + txt_hours
        if not skipUnits:
            txt += unitsSeparator
        txt += num2text(minutes, units_minutes)
    else:
        txt = "Сейчас ровно " + txt_hours

    core.say(txt)

female_units_min2 = (('минуту', 'минуты', 'минут'), 'f')
female_units_min  = (('минута', 'минуты', 'минут'), 'f')
female_units_sec2 = (('секунду', 'секунды', 'секунд'), 'f')
female_units_sec  = (('секунда', 'секунды', 'секунд'), 'f')

def _set_timer(core: Core, phrase: str):
    phrase = (phrase or "").strip()
    if phrase == "":
        # Таймер по умолчанию - 5 минут
        txt = num2text(5, female_units_min)
        _set_timer_real(core, 5 * 60, txt)
        return

    phrase += " "
    if phrase.startswith("на "):
        phrase = phrase[3:]

    # Секунды
    for i in range(100, 1, -1):
        t1 = num2text(i, female_units_sec) + " "
        if phrase.startswith(t1):
            _set_timer_real(core, i, t1)
            return
        t2 = num2text(i, female_units_sec2) + " "
        if phrase.startswith(t2):
            _set_timer_real(core, i, t1)
            return
        t3 = f"{i} секунд "
        if phrase.startswith(t3):
            _set_timer_real(core, i, t1)
            return

    # Минуты
    for i in range(100, 1, -1):
        t1 = num2text(i, female_units_min) + " "
        if phrase.startswith(t1):
            _set_timer_real(core, i * 60, t1)
            return
        t2 = num2text(i, female_units_min2) + " "
        if phrase.startswith(t2):
            _set_timer_real(core, i * 60, t1)
            return
        t3 = f"{i} минут "
        if phrase.startswith(t3):
            _set_timer_real(core, i * 60, t1)
            return

    # Без единиц - считаем минутами
    for i in range(100, 1, -1):
        t1 = num2text(i, female_units_min) + " "
        t2 = num2text(i) + " "
        if phrase.startswith(t2):
            _set_timer_real(core, i * 60, t1)
            return
        t3 = f"{i} "
        if phrase.startswith(t3):
            _set_timer_real(core, i * 60, t1)
            return

    # Спецкейс на 1 минуту
    if phrase.startswith(("один ", "одна ", "одну ")):
        t1 = num2text(1, female_units_min)
        _set_timer_real(core, 60, t1)
        return

    # Непонятно - сохраняем контекст и переспрашиваем
    core.say("Что после таймера ?")
    core.context_set(_set_timer)

def _set_timer_real(core: Core, seconds: int, txt: str):
    core.set_timer(seconds, (_after_timer, txt))
    core.play_voice_assistant_speech("Ставлю таймер на " + txt)

def _after_timer(core: Core, txt: str):
    opts = core.extension_options(__package__)
    times = int(opts.get("wavRepeatTimes", 1))
    wav_path = opts.get("wavPath", "assets/audio/timer.wav")

    for _ in range(max(1, times)):
        core.play_wav(wav_path)
        time.sleep(0.2)

    core.play_voice_assistant_speech(txt + " прошло")

"""
    Озвучить активные таймеры и запомнить их порядок для последующей отмены по номеру
"""
def _list_timers(core: Core, phrase: str):
    global _last_list_ids
    _last_list_ids = []

    now = time.time()
    active = [(i, t) for i, t in enumerate(core.timers) if t > 0]
    if not active:
        core.say("Активных таймеров нет")
        return

    # По времени окончания
    active.sort(key=lambda x: x[1])

    lines_voice = []
    for idx, (internal_id, end_ts) in enumerate(active, start=1):
        left = max(0, int(round(end_ts - now)))
        _last_list_ids.append(internal_id)
        txt_left = _format_left_ru(left)
        lines_voice.append(f"{idx} - осталось {txt_left}")
        print(f"[ТАЙМЕР] №{idx} (ID={internal_id}) заканчивается в {core.util_time_to_readable(end_ts)} | осталось: {left} с")

    core.say("Активные таймеры: " + "; ".join(lines_voice))

"""
    Остановить все таймеры без вызова их end-колбэков
"""
def _cancel_all_timers(core: Core, phrase: str):
    if not any(t > 0 for t in core.timers):
        core.say("Активных таймеров нет")
        return
    core.clear_timers()
    core.say("Все таймеры остановлены")

"""
    Остановить конкретный таймер: по номеру из последнего списка, по внутреннему ID, либо единственный активный
"""
def _cancel_timer(core: Core, phrase: str):
    phrase = (phrase or "").strip()

    # Активные таймеры
    active_ids = [i for i, t in enumerate(core.timers) if t > 0]
    if not active_ids:
        core.say("Активных таймеров нет")
        return

    # Если всего один - гасим его
    if len(active_ids) == 1 and not phrase:
        core.clear_timer(active_ids[0], runEndFunc=False)
        core.say("Таймер остановлен")
        return

    # Попытка извлечь число из фразы
    # Номер из списка (1..N) или внутренний ID
    num = _extract_number(phrase)
    target_id: int | None = None

    if num is not None:
        # Сначала трактуем как «номер из списка»
        if 1 <= num <= len(_last_list_ids):
            target_id = _last_list_ids[num - 1]
        # Иначе - как внутренний ID
        elif num in active_ids:
            target_id = num

    if target_id is None:
        # Нет валидного указания - озвучиваем список и просим повторить (устанавливаем контекст)
        _list_timers(core, "")
        core.say("Скажите, какой таймер удалить. Например: удали таймер один.")
        core.context_set(_cancel_timer)
        return

    core.clear_timer(target_id, runEndFunc=False)
    core.say("Таймер удалён")

"""
    Извлекает число из текста: сначала цифры, затем простые русские слова 0..10
"""
def _extract_number(text: str) -> int | None:
    m = re.search(r"\d+", text)
    if m:
        try:
            return int(m.group(0))
        except ValueError:
            pass
    words = {"ноль": 0, "один": 1, "одна": 1, "первый": 1, "первая": 1, "два": 2, "две": 2, "второй": 2, "вторая": 2, "три": 3, "третий": 3, "третья": 3, "четыре": 4, "четвёртый": 4, "четвертый": 4, "четвёртая": 4, "четвертая": 4, "пять": 5, "пятый": 5, "пятая": 5, "шесть": 6, "шестой": 6, "шестая": 6, "семь": 7, "седьмой": 7, "седьмая": 7, "восемь": 8, "восьмой": 8, "восьмая": 8, "девять": 9, "девятый": 9, "девятая": 9, "десять": 10, "десятый": 10, "десятая": 10}
    low = text.lower()
    for w, n in words.items():
        if w in low:
            return n
    return None

"""
    Человекочитаемое 'осталось N минут M секунд' c правильными формами
"""
def _format_left_ru(seconds: int) -> str:
    mins = seconds // 60
    secs = seconds % 60
    if mins > 0 and secs > 0:
        return f"{num2text(mins, (('минута','минуты','минут'),'f'))} {num2text(secs, (('секунда','секунды','секунд'),'f'))}"
    if mins > 0:
        return f"{num2text(mins, (('минута','минуты','минут'),'f'))}"
    return f"{num2text(secs, (('секунда','секунды','секунд'),'f'))}"

def _play_coin(core: Core, phrase: str):
    core.play_voice_assistant_speech(random.choice(["Выпал орел", "Выпала решка"]))

def _play_dice(core: Core, phrase: str):
    core.play_voice_assistant_speech(random.choice(["Выпала единица", "Выпало два", "Выпало три", "Выпало четыре", "Выпало пять", "Выпало шесть"]))

def _list_all_commands(core: Core, phrase: str):
    manifest = start(core)
    commands_list = []

    def _extract_cmds(cmds, prefix=""):
        for key, value in cmds.items():
            if isinstance(value, dict):
                for sub_key in value.keys():
                    commands_list.append((prefix + key + " " + sub_key).strip())
            else:
                commands_list.append((prefix + key).strip())

    _extract_cmds(manifest["commands"])

    commands_list = sorted(set(commands_list))

    print("[СПИСОК КОМАНД]:")
    for cmd in commands_list:
        print(f" - {cmd}")

    # core.say("Доступные команды: " + "; ".join(commands_list))
