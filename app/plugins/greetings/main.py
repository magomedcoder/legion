# app/plugins/common/main.py
import os
import time
import random
from datetime import datetime

from app.core.core import Core
from app.utils.num_to_text_ru import num2text

"""
    Голосовая команда: Приветствия, Дата/Время, Таймер, Рандом (монета/кубик)

    Команды:
        привет|доброе утро                                    -> приветствие
        дата                                                  -> озвучить дату
        время                                                 -> озвучить время
        поставь таймер|поставь тайгер|таймер|тайгер [на ...]  -> таймер
        подбрось|брось монету|монетку                         -> монетка
        подбрось|брось кубик|кость                            -> кубик

        Примеры:
            таймер -> 5 минут
            таймер на двадцать секунд
            таймер на 3 минуты
            таймер на двадцать пять

        Опции
            # время
            sayNoon: bool                 - говорить «полдень» / «полночь» для 12:00 / 00:00
            skipUnits: bool               - не произносить единицы («час», «минуты»)
            unitsSeparator: str           - разделитель между часами и минутами
            skipMinutesWhenZero: bool     - пропускать минуты, если 0
            # таймер
            wavRepeatTimes: int           - сколько раз проигрывать сигнал
            wavPath: str                  - путь к WAV сигналу таймера

"""

modname = (__package__ or "common").split(".")[-1]

def start(core: Core):
    manifest = {
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

            "подбрось|брось": {
                "монету|монетку": _play_coin,
                "кубик|кость": _play_dice,
            },
        }
    }
    return manifest

def start_with_options(core: Core, manifest: dict):
    return manifest

def _play_greetings(core: Core, phrase: str):
    greetings = ["И тебе привет!", "Рада тебя видеть!"]
    greet_str = random.choice(greetings)
    print(f"- Сейчас скажу: {greet_str}")
    core.play_voice_assistant_speech(greet_str)
    print(f"- Сказала: {greet_str}")

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
    opts = core.plugin_options(modname) or {}
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
        # таймер по умолчанию - 5 минут
        txt = num2text(5, female_units_min)
        _set_timer_real(core, 5 * 60, txt)
        return

    phrase += " "
    if phrase.startswith("на "):
        phrase = phrase[3:]

    # секунды
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

    # минуты
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

    # без единиц - считаем минутами
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

    # спецкейс на 1 минуту
    if phrase.startswith(("один ", "одна ", "одну ")):
        t1 = num2text(1, female_units_min)
        _set_timer_real(core, 60, t1)
        return

    # непонятно - сохраняем контекст и переспрашиваем
    core.say("Что после таймер ?")
    core.context_set(_set_timer)

def _set_timer_real(core: Core, seconds: int, txt: str):
    core.set_timer(seconds, (_after_timer, txt))
    core.play_voice_assistant_speech("Ставлю таймер на " + txt)

def _after_timer(core: Core, txt: str):
    opts = core.plugin_options(modname) or {}
    times = int(opts.get("wavRepeatTimes", 1))
    wav_path = opts.get("wavPath", "assets/audio/timer.wav")

    for _ in range(max(1, times)):
        core.play_wav(wav_path)
        time.sleep(0.2)

    core.play_voice_assistant_speech(txt + " прошло")

def _play_coin(core: Core, phrase: str):
    core.play_voice_assistant_speech(random.choice(["Выпал орел", "Выпала решка"]))

def _play_dice(core: Core, phrase: str):
    core.play_voice_assistant_speech(random.choice(["Выпала единица", "Выпало два", "Выпало три", "Выпало четыре", "Выпало пять", "Выпало шесть"]))
