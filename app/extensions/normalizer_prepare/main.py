import logging
import re

from app.core.core import Core

"""
    Расширение для нормализации текста перед синтезом речи

    Функциональность:
        1. Замена неподдерживаемых или нестабильно обрабатываемых символов на словесные эквиваленты (например: "$" -> "доллар")
        2. Обработка чисел:
            - преобразование в числительное (прописью)
            - удаление
            - сохранение без изменений
        3. Обработка латинских символов:
            - транслитерация в русскую фонетическую запись через IPA
            - удаление
            - сохранение без изменений

        Опции:
            hangeNumbers         - ЧИСЛА: process | delete | no_process
            changeLatin          - ЛАТИНИЦА: process | delete | no_process
            changeSymbols        - символы, которые заменяем словами
            keepSymbols          - символы, которые оставляем как есть
            deleteUnknownSymbols - удалять ли всё остальное из прочих символов
        
"""

def manifest():
    return {
        "name": "Нормализатор: латиница и символы",

        "options": {
            "changeNumbers": "process",
            "changeLatin": "process",
            "changeSymbols": r"#$%&*+\-/<=>@~[\]_`{|}№\\^",
            "keepSymbols": r",.?!;:() «»\"' ",
            "deleteUnknownSymbols": True,
        },

        "normalizer": {
            "prepare": (init, normalize)
        },
    }

logger = logging.getLogger(__name__)

def start(core: Core, manifest: dict):
    pass

def init(core: Core):
    pass

def normalize(core: Core, text: str) -> str:
    opts = core.extension_options(__package__)
    logger.debug("Текст до преобразований: %s", text)

    # Если только кириллица + разрешённая пунктуация - возвращаем как есть
    if not re.search(r'[^,.?!;:"() «»\'ЁА-Яа-яё\d\s%-]', text):
        return _process_numbers(core, text, opts)

    # 1) Символы -> слова / сохранить / удалить
    text = _process_symbols(text, opts)

    # 2) Числа -> слова/удалить/оставить
    text = _process_numbers(core, text, opts)

    # 3) Латиница -> удалить/оставить/конвертировать в русскую «фонетику»
    text = _process_latin(text, opts)

    # Финальная чистка пробелов
    text = re.sub(r"\s+", " ", text).strip()
    logger.info("Текст после всех преобразований: %s", text)
    return text

def _process_symbols(text: str, opts: dict) -> str:
    change = opts.get("changeSymbols", "")
    keep = opts.get("keepSymbols", "")
    delete_unknown = bool(opts.get("deleteUnknownSymbols", True))

    symbol_dict = {
        '!': ' восклицательный знак ', '"': ' двойная кавычка ', '#': ' решётка ', '$': ' доллар ',
        '%': ' процент ', '&': ' амперсанд ', "'": ' кавычка ', '(': ' левая скобка ', ')': ' правая скобка ',
        '*': ' звёздочка ', '+': ' плюс ', ',': ',', '-': ' минус ', '.': '.', '/': ' косая черта ',
        ':': ':', ';': ';', '<': ' меньше ', '=': ' равно ', '>': ' больше ', '?': '?', '@': ' собака ',
        '~': ' тильда ', '[': ' левая квадратная скобка ', '\\': ' обратная косая черта ',
        ']': ' правая квадратная скобка ', '^': ' циркумфлекс ', '_': ' нижнее подчеркивание ',
        '`': ' обратная кавычка ', '{': ' левая фигурная скобка ', '|': ' вертикальная черта ',
        '}': ' правая фигурная скобка ', '№': ' номер ',
        '«': ' « ', '»': ' » ',
    }

    # Оставляем только разрешённые к замене
    repl = {k: v for k, v in symbol_dict.items() if k in change}
    # Символы, которые просто сохраняем
    repl.update({k: k for k in keep})

    if repl:
        text = text.translate(str.maketrans(repl))

    if delete_unknown:
        # Всё, что не кириллица/латиница/цифра/пробел и не входит в набор keep/change - удаляем
        safe = re.escape(change + keep)
        text = re.sub(fr"[^{safe}A-Za-zЁА-Яа-яё0-9\s%-]", "", text)

    return text

def _process_numbers(core: Core, text: str, opts: dict) -> str:
    mode = (opts.get("changeNumbers") or "process").lower()
    if not re.search(r"\d", text):
        return text
    if mode == "process":
        text = core.all_num_to_text(text)
    elif mode == "delete":
        text = re.sub(r"\d", "", text)
    # no_process - оставляем
    # Проценты: заменяем знак на слово
    return text.replace("%", " процентов")

def _process_latin(text: str, opts: dict) -> str:
    mode = (opts.get("changeLatin") or "process").lower()
    if not re.search(r"[A-Za-z]", text) or mode == "no_process":
        return text
    if mode == "delete":
        return re.sub(r"[A-Za-z]", "", text)

    # mode == process -> конвертируем через IPA в русскую «фонетику»
    ipa2ru_map = {
        "p": "п", "b": "б", "t": "т", "d": "д", "k": "к", "g": "г", "m": "м", "n": "н",
        "ŋ": "нг", "ʧ": "ч", "ʤ": "дж", "f": "ф", "v": "в", "θ": "т", "ð": "з", "s": "с", "z": "з",
        "ʃ": "ш", "ʒ": "ж", "h": "х", "w": "в", "j": "й", "r": "р", "l": "л",
        "i": "и", "ɪ": "и", "e": "э", "ɛ": "э", "æ": "э", "ʌ": "а", "ə": "е", "u": "у", "ʊ": "у",
        "oʊ": "оу", "ɔ": "о", "ɑ": "а", "aɪ": "ай", "aʊ": "ау", "ɔɪ": "ой", "ɛr": "ё", "ər": "ё",
        "ɚ": "а", "ju": "ю", "əv": "ов", "o": "о", "ˈ": "", "ˌ": "", "*": "",
    }

    try:
        import app.lib.eng_to_ipa as ipa
    except Exception as e:
        logger.warning("Нет eng_to_ipa, латиница останется как есть: %s", e)
        return text

    ipa_text = ipa.convert(text)
    logger.debug("IPA: %s", ipa_text)

    def ipa2ru_at_pos(s: str, pos: int) -> tuple[str, int]:
        ch2 = s[pos:pos+2]
        if ch2 in ipa2ru_map: return ipa2ru_map[ch2], pos+2
        ch1 = s[pos]
        if ch1 in ipa2ru_map: return ipa2ru_map[ch1], pos+1
        if ord(ch1) < 128:    return ch1, pos+1
        return ch1, pos+1

    out, i = [], 0
    while i < len(ipa_text):
        chunk, i = ipa2ru_at_pos(ipa_text, i)
        out.append(chunk)
    return "".join(out)
