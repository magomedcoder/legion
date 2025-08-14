import base64
import datetime
import hashlib
import logging
import os
import time
import traceback

from collections.abc import Callable
from threading import Timer
from typing import Dict
from pathlib import Path
from app.core.load import Load
from app.utils.all_num_to_text import all_num_to_text
from app.lib.mpcapi.core import MpcAPI
import app.lib.lingua_franca

"""
    Ядро ассистента

    Наследует Load и добавляет
        Регистрацию и инициализацию TTS/проигрывателей/нормализаторов/фаззи-процессоров
        Поиск и выполнение команд, включая нечеткое сравнение
        Управление контекстом (диалоговыми режимами)
        Таймеры (простые, с колбэками на обновление/завершение)
        Утилиты для файлов, кэша TTS и логирования
"""

logger = logging.getLogger(__name__)

class Core(Load):
    def __init__(self):
        # Инициализируем базовый загрузчик расширений
        Load.__init__(self)

        # Настройки API 
        self.api_host = "0.0.0.0"
        self.api_port = 8000
        self.api_log_level = "error"

        # Текущий синтезатор (инстанс), таймеры и их колбэки
        self.tts_synth = None

        # Отметки времени завершения таймеров
        self.timers = [-1, -1, -1, -1, -1, -1, -1, -1]

        # Колбэк на обновление (не используется)
        self.timers_func_upd = [None, None, None, None, None, None, None, None]

        # Колбэк при завершении  
        self.timers_func_end = [None, None, None, None, None, None, None, None]

        # Продолжительности таймеров (пока не заполняются)
        self.timers_duration = [0, 0, 0, 0, 0, 0, 0, 0]

        # Словарь всех доступных команд
        self.commands = {}

        # Список расширений
        self.extensions = {}

        # Зарегистрированные TTS-расширения: id -> (init_fn, say_fn, save_to_wav_fn?)
        self.ttss = {}

        # Зарегистрированные проигрыватели WAV: id -> (init_fn, play_fn)
        self.play_wavs = {}

        # Зарегистрированные нормализаторы текста: id -> (init_fn, normalize_fn)
        self.normalizers = {}

        # Зарегистрированные нечеткие процессоры: id -> (init_fn, compare_fn)
        self.fuzzy_processors: Dict[str, tuple[Callable, Callable]] = {}

        # Имена для обращения к ассистенту
        self.voice_names = ["легион"]

        # Доп. команда, которую нужно подставить при обращении по конкретному имени
        self.voice_name_run_cmd = {}

        # Использовать ли кэш TTS (wav-файлы по хэшу фраз)
        self.use_tts_cache = False

        # Рабочая директория рантайма
        self.runtime_dir = "runtime"

        # Папка кэша TTS
        self.tts_cache_dir = "cache/tts"

        # Идентификаторы движков TTS, а также проигрывателя
        self.tts_engine_id = "rhvoice"
        self.tts_engine_id_2 = ""
        self.play_wav_engine_id = "audioplayer"

        # Политика логирования all, cmd
        self.log_policy = "cmd"

        # Временная папка
        self.tmp_dir = "temp"

        # Счётчик временных файлов
        self.tmp_cnt = 0  

        # Последняя озвученная фраза и режим удалённого TTS
        self.last_say = ""

        # Варианты: "none", "saytxt", "saywav" или комбинированно через запятую
        self.remote_tts = "none"  

        # Сюда складывается результат для удалённого клиента
        self.remote_tts_result = None  

        # Текущий контекст диалога и таймер его очистки
        self.context = None
        self.context_timer = None
        self.context_timer_last_duration = 0

        # Настройки длительности контекста и ожидания старта таймера (для удалённого TTS)
        self.context_default_duration = 10
        self.context_remote_wait_for_call = False

        # Клиент для управления плеером
        self.mpchc = MpcAPI()

        # Текущее имя обращения (которое распознали)
        self.cur_callname: str = ""

        # Полная входная команда (оригинал)
        self.input_cmd_full: str = ""

        # Ссылка на экземпляр FastAPI
        self.fastapi_app = None

        # Параметры логирования
        self.log_console = True
        self.log_console_level = "WARNING"
        self.log_file = True
        self.log_file_level = "WARNING"

        # Идентификатор движка нормализации (для русских TTS)
        # "none" - без нормализации
        # отвечает за нормализацию текста для русских TTS
        self.normalization_engine: str = "default"

        # Язык для библиотеки lingua-franca (преобразование чисел в текст)
        self.lingua_franca_lang: str = "ru"

        # Ответ, если команда не распознана
        self.reply_no_command_found: str = "Извини, я не поняла"

        # Ответ, если команда не распознана в контексте диалога
        self.reply_no_command_found_context: str = "Не поняла..."

        # Порог уверенности для нечеткого распознавания команд
        self.fuzzy_threshold = 0.5,
 
        self.runtime_path = Path(self.runtime_dir)
        self.tmp_path = self.runtime_path / self.tmp_dir
        self.tts_cache_path = self.runtime_path / self.tts_cache_dir
        self.tts_cache_engine_path = self.tts_cache_path / self.tts_engine_id

        for p in (self.runtime_path, self.tmp_path, self.tts_cache_engine_path):
            p.mkdir(parents=True, exist_ok=True)

        # Язык для чисел
        app.lib.lingua_franca.load_language(self.lingua_franca_lang)

        # Нормализация
        if self.normalization_engine == "default":
            self.normalization_engine = "prepare"

        if self.log_console or self.log_file:
            # Сбрасываем старые обработчики, чтобы избежать дублирования логов
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)

            # Общий уровень - минимальный из двух
            root_logger.setLevel(min(self.log_console_level, self.log_file_level))

            logger = logging.getLogger(__name__)

            if self.log_console:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(self.log_console_level)
                console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                root_logger.addHandler(console_handler)
                logger.info("Вывод логов в консоль включён")

            if self.log_file:
                file_handler = logging.FileHandler(self.runtime_dir + "/legion.log")
                file_handler.setLevel(self.log_file_level)
                file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                root_logger.addHandler(file_handler)
                logger.info("Вывод логов в файл включён")


    """
        Инициализирует расширения и выводит информацию, затем настраивает голосовой движок
    """
    def init_with_extensions(self):
        self.init_extensions(["resource_downloader"])
        self.setup_assistant_voice()

    """
        Подмешивает сущности из манифеста расширения в ядро:
            commands - словарь "варианты фраз" -> "следующий контекст/функция"
            tts/play wav/normalizer - регистрация соответствующих движков
            fuzzy_processor - регистрация обработчиков нечеткого сравнения
    """
    def process_extension_manifest(self, modname, manifest):
        # Команды
        if "commands" in manifest:
            for cmd in manifest["commands"].keys():
                self.commands[cmd] = manifest["commands"][cmd]
                # Сохраняем, к какому расширению относятся эти команды
                if modname in self.extensions:
                    self.extensions[modname].append(cmd)
                else:
                    self.extensions[modname] = [cmd]

        # Движки TTS
        if "tts" in manifest:
            for cmd in manifest["tts"].keys():
                self.ttss[cmd] = manifest["tts"][cmd]

        # Движки воспроизведения WAV
        if "play_wav" in manifest:
            for cmd in manifest["play_wav"].keys():
                self.play_wavs[cmd] = manifest["play_wav"][cmd]

        # Нормализаторы
        if "normalizer" in manifest:
            for cmd in manifest["normalizer"].keys():
                self.normalizers[cmd] = manifest["normalizer"][cmd]

        # Нечеткие процессоры
        if "fuzzy_processor" in manifest:
            for cmd in manifest["fuzzy_processor"].keys():
                self.fuzzy_processors[cmd] = manifest["fuzzy_processor"][cmd]

    """
        Вывод ошибки красным и трассировки исключения
    """
    def print_error(self, err_txt, e: Exception = None):
        print(err_txt)
        traceback.print_exc()

    """
        Простой вывод строки красным цветом
    """
    def print_red(self, txt):
        print(txt)

    """
        Инициализация движков: проигрывателя WAV, нормализатора, TTS и дополнительных расширений
    """
    def setup_assistant_voice(self):
        # Инициализация модуля для воспроизведения WAV-файлов
        try:
            self.play_wavs[self.play_wav_engine_id][0](self)
        except Exception as e:
            self.print_error("Ошибка инициализации расширения воспроизведения WAV (play_wav_engine_id)", e)
            self.tts_engine_id = "console"

        # Инициализация модуля нормализации текста (приведение текста к удобному для TTS виду: замена сокращений, преобразование чисел в слова и т.д.)
        if self.normalization_engine != "none":
            try:
                self.normalizers[self.normalization_engine][0](self)
            except Exception as e:
                self.print_error(f"Ошибка инициализации расширения нормализатора {self.normalization_engine}", e)
                self.normalization_engine = "none"

        # Инициализация основного TTS-движка для озвучивания ответов ассистента
        try:
            self.ttss[self.tts_engine_id][0](self)
        except Exception as e:
            self.print_error("Ошибка инициализации расширения TTS (tts_engine_id)", e)
            self.tts_engine_id = "console"

        # Инициализация второго TTS-движка, если он задан в настройках и отличается от основного
        if self.tts_engine_id_2 == "":
            self.tts_engine_id_2 = self.tts_engine_id
        if self.tts_engine_id_2 != self.tts_engine_id:
            try:
                self.ttss[self.tts_engine_id_2][0](self)
            except Exception as e:
                self.print_error("Ошибка инициализации расширения TTS2 (tts_engine_id_2)", e)

        # Инициализация всех нечетких процессоров
        for k in self.fuzzy_processors.keys():
            try:
                self.fuzzy_processors[k][0](self)
            except Exception as e:
                self.print_error(f"Ошибка инициализации fuzzy_processor {k}", e)

    """
        Нормализует текст, если выбран нормализатор; иначе возвращает исходный текст
    """
    def normalize(self, text: str):
        if self.normalization_engine == "none":
            return text
        else:
            return self.normalizers[self.normalization_engine][1](self, text)

    """
        Озвучивание фразы разными путями: локально или подготовка данных для удалённого клиента
        Режимы remote_tts:
            none - озвучиваем локально (через say_fn или через tts->wav->play)
            saytxt - только возвращаем текст (полезно для внешних клиентов)
            saywav - генерируем wav в файл (с кэшем при необходимости), кодируем в base64 в ответ
        Можно комбинировать через запятую
    """
    def play_voice_assistant_speech(self, text_to_speech: str):
        self.last_say = text_to_speech
        remote_tts_list = self.remote_tts.split(",")

        self.remote_tts_result = {}
        is_processed = False

        # Локальное озвучивание
        if "none" in remote_tts_list:
            if self.ttss[self.tts_engine_id][1] is not None:
                # Если TTS-расширение поддерживает прямое озвучивание
                self.ttss[self.tts_engine_id][1](self, text_to_speech)
            else:
                # Иначе генерируем WAV во временный файл (или используем кэш)
                if self.use_tts_cache:
                    tts_file = self.get_tts_cache_file(text_to_speech)
                else:
                    tts_file = self.get_temp_filename() + ".wav"

                if not self.use_tts_cache or self.use_tts_cache and not os.path.exists(tts_file):
                    self.tts_to_filewav(text_to_speech, tts_file)

                self.play_wav(tts_file)
                if not self.use_tts_cache and os.path.exists(tts_file):
                    os.unlink(tts_file)

            is_processed = True

        # Возврат только текста
        if "saytxt" in remote_tts_list:
            self.remote_tts_result["txt"] = text_to_speech
            is_processed = True

        # Возврат WAV как base64
        if "saywav" in remote_tts_list:
            if self.use_tts_cache:
                tts_file = self.get_tts_cache_file(text_to_speech)
            else:
                tts_file = self.get_temp_filename() + ".wav"

            if not self.use_tts_cache or self.use_tts_cache and not os.path.exists(tts_file):
                self.tts_to_filewav(text_to_speech, tts_file)

            with open(tts_file, "rb") as wav_file:
                encoded_string = base64.b64encode(wav_file.read())

            if not self.use_tts_cache and os.path.exists(tts_file):
                os.unlink(tts_file)

            self.remote_tts_result["wav_base64"] = encoded_string
            is_processed = True

        if not is_processed:
            print("Ошибка при выводе TTS - remote_tts не был обработан.")
            print("Текущий remote_tts: {}".format(self.remote_tts))
            print("Текущий remote_tts_list: {}".format(remote_tts_list))

    """
        Псевдоним для play_voice_assistant_speech
    """
    def say(self, text_to_speech: str):  
        self.play_voice_assistant_speech(text_to_speech)

    """
        Озвучивает через второй TTS-движок
    """
    def say2(self, text_to_speech: str):  
        if self.ttss[self.tts_engine_id_2][1] is not None:
            self.ttss[self.tts_engine_id_2][1](self, text_to_speech)
        else:
            tempfilename = self.get_temp_filename() + ".wav"
            self.tts_to_filewav2(text_to_speech, tempfilename)
            self.play_wav(tempfilename)
            if os.path.exists(tempfilename):
                os.unlink(tempfilename)

    """
        Сохранение синтеза в WAV-файл основным TTS
    """
    def tts_to_filewav(self, text_to_speech: str, filename: str):
        if len(self.ttss[self.tts_engine_id]) > 2:
            self.ttss[self.tts_engine_id][2](self, text_to_speech, filename)
        else:
            print("Сохранение в файл не поддерживается этим TTS-движком")

    """
        Сохранение синтеза в WAV-файл вторым TTS
        Через второй движок
    """
    def tts_to_filewav2(self, text_to_speech: str, filename: str):
        if len(self.ttss[self.tts_engine_id_2]) > 2:
            self.ttss[self.tts_engine_id_2][2](self, text_to_speech, filename)
        else:
            print("Сохранение в файл не поддерживается этим TTS-движком")

    """
        Создаёт уникальное имя временного файла в runtime/temp
    """
    def get_temp_filename(self):
        self.tmp_cnt += 1
        return str(self.tmp_path / f"core_{self.tmp_cnt}")

    """
        Возвращает путь к кэш-файлу WAV для заданного текста, учитывая id TTS
    """
    def get_tts_cache_file(self, text_to_speech: str):
        _hash = hashlib.md5(text_to_speech.encode('utf-8')).hexdigest()
        # Префикс из первых 40 символов + md5
        filename = ".".join([text_to_speech[:40], _hash, "wav"])
        return str(self.tts_cache_engine_path / filename)

    """
        Преобразует все цифры в тексте в слова (для лучшего озвучивания)
    """
    def all_num_to_text(self, text: str):
        return all_num_to_text(text)

    """
        Поиск оптимальной команды с учётом обработчиков нечеткого сравнения

        Параметры:
            command (str) - исходная команда пользователя
            context (dict) - текущий контекст команд (словарь "фразы|синонимы" -> {следующий контекст или функция})
            allow_rest_phrase (bool) - разрешать ли остаток фразы ("привет как дела" -> ключ "привет", остаток "как дела")
            threshold (float|None) - порог схожести для fuzzy (0..1). Если None - берётся из опций core

        Возврат: tuple(key_in_context, probability, rest_phrase) либо None, если не найдено
    """
    def find_best_cmd_with_fuzzy(self, command, context, allow_rest_phrase=True, threshold: float = None):
        # 1) Пробуем точное совпадение
        for keyall in context.keys():
            keys = keyall.split("|")
            for key in keys:
                if command == key:
                    return keyall, 1.0, ""

        # 2) Если разрешён остаток фразы - проверяем startswith
        if allow_rest_phrase:
            for keyall in context.keys():
                keys = keyall.split("|")
                for key in keys:
                    if command.startswith(key):
                        rest_phrase = command[(len(key) + 1):]
                        return (keyall, 1.0, rest_phrase)

        # 3) Fuzzy-поиск
        if threshold is None:
            threshold = self.fuzzy_threshold

        for fuzzy_processor_k in self.fuzzy_processors.keys():
            res = None
            try:
                # Новый интерфейс: (core, command, context, allow_rest_phrase)
                res = self.fuzzy_processors[fuzzy_processor_k][1](self, command, context, allow_rest_phrase)
            except TypeError as e:
                # Обратная совместимость со старым интерфейсом
                logger.exception(e)
                res = self.fuzzy_processors[fuzzy_processor_k][1](self, command, context)

            # Ожидается: None или (context_key:str, probability:float[0..1], rest_phrase:str)
            print("Fuzzy processor {0}, result for '{1}': {2}".format(fuzzy_processor_k, command, res))

            if res is not None:
                keyall, probability, rest_phrase = res
                if threshold < probability:
                    return res

        return None

    """
        Переходит к следующему шагу исполнения в рамках контекста или вызывает конечную функцию

        Логика:
            Если context == None, это первый вход: ищем команду в self.commands
            Если context - это dict, ищем подходящий ключ (в т.ч. через fuzzy) и рекурсивно спускаемся
            Если context - вызываемый объект (функция), вызываем её и очищаем контекст
    """
    def execute_next(self, command, context):
        is_first_call = False
        # первый вход
        if context is None:  
            is_first_call = True
            context = self.commands
            # сохраняем полноценную фразу
            self.input_cmd_full = command  

        if isinstance(context, dict):
            # продолжаем разбор
            pass  
        else:
            # context -  это уже функция, выполняем её
            self.context_clear()
            self.call_ext_func_phrase(command, context)
            return

        try:
            res = self.find_best_cmd_with_fuzzy(command, context, True)
            if res is not None:
                keyall, probability, rest_phrase = res
                next_context = context[keyall]
                self.execute_next(rest_phrase, next_context)
                return

            # Если команда не найдена
            if self.context is None:
                # вне контекста
                self.say(self.reply_no_command_found)
            else:
                # внутри контекста
                self.say(self.reply_no_command_found_context)
                # перезапускаем таймер контекста
                if self.context_timer is not None:
                    self.context_set(self.context, self.context_timer_last_duration)
        except Exception as err:
            logger.exception(err)

    """
        Возвращает ключ в context по одной из внутренних фраз
        Полезно для fuzzy-процессоров: нужен именно ключ ("привет|здравствуй"), а не отдельный синоним
    """
    def fuzzy_get_command_key_from_context(self, predicted_command: str, context: dict):
        for keyall in context.keys():
            for key in keyall.split("|"):
                if key == predicted_command:
                    return keyall
        return None

    """
        Форматирует timestamp в строку локального времени
    """
    def util_time_to_readable(self, curtime):
        human_readable_date_local = datetime.datetime.fromtimestamp(curtime)
        return human_readable_date_local.strftime('%Y-%m-%d %H:%M:%S')

    """
        Запускает таймер на duration секунд

        Возвращает ID таймера или -1, если нет свободной ячейки
        timerFuncEnd - колбэк при завершении; timerFuncUpd - колбэк обновления (здесь не используется)
    """
    def set_timer(self, duration, timerFuncEnd, timerFuncUpd=None):
        curtime = time.time()
        for i in range(len(self.timers)):
            if self.timers[i] <= 0:
                self.timers[i] = curtime + duration
                self.timers_func_end[i] = timerFuncEnd
                print(
                    f"Новый таймер #{i} | "
                    f"Текущее время: {self.util_time_to_readable(curtime)} | "
                    f"Длительность: {duration} сек | "
                    f"Время окончания: {self.util_time_to_readable(self.timers[i])}"
                )

                return i
        # нет свободных таймеров
        return -1  

    """
        Очищает таймер по индексу. При runEndFunc=True дополнительно вызовет его end-колбэк
    """
    def clear_timer(self, index, runEndFunc=False):
        if runEndFunc and self.timers_func_end[index] is not None:
            self.call_ext_func(self.timers_func_end[index])
        self.timers[index] = -1
        self.timers_duration[index] = 0
        self.timers_func_end[index] = None

    """
        Останавливает все активные таймеры без вызова их колбэков
    """
    def clear_timers(self):
        for i in range(len(self.timers)):
            if self.timers[i] >= 0:
                self.timers[i] = -1
                self.timers_func_end[i] = None

    """
        Проверяет таймеры и завершает те, чьё время истекло (с вызовом end-колбэков)
    """
    def update_timers(self):
        curtime = time.time()
        for i in range(len(self.timers)):
            if self.timers[i] > 0:
                if curtime >= self.timers[i]:
                    print(
                        "End Timer ID =",
                        str(i),
                        ' curtime=', self.util_time_to_readable(curtime),
                        'endtime=', self.util_time_to_readable(self.timers[i])
                    )
                    self.clear_timer(i, True)

    """
        Вызывает функцию расширения

        Поддерживаются варианты:
            funcparam = (func, param) - вызовет func(self, param)
            funcparam = func - вызовет func(self)
    """
    def call_ext_func(self, funcparam):
        if isinstance(funcparam, tuple):  # funcparam =(func, param)
            funcparam[0](self, funcparam[1])
        else:  # funcparam = func
            funcparam(self)

    """
        Вызывает функцию расширения, передавая ещё и исходную фразу

        Поддерживаются варианты:
            funcparam = (func, param) - вызовет func(self, phrase, param)
            funcparam = func - вызовет func(self, phrase)
    """
    def call_ext_func_phrase(self, phrase, funcparam):
        if isinstance(funcparam, tuple):  # funcparam =(func, param)
            funcparam[0](self, phrase, funcparam[1])
        else: 
            # funcparam = func
            funcparam(self, phrase)

    """
        Воспроизводит WAV-файл через зарегистрированный движок play_wav
    """
    def play_wav(self, wavfile):
        self.play_wavs[self.play_wav_engine_id][1](self, wavfile)

    """
        Разбирает входную строку распознанной речи и запускает команду

        Пример: "легион таймер пять". Сначала ищется имя ассистента в начале строки, затем остаток передаётся в execute_next().
        Если уже есть активный контекст, обрабатываем всю строку как продолжение диалога
    """
    def run_input_str(self, voice_input_str, func_before_run_cmd=None):
        haveRun = False
        if voice_input_str is None:
            return False

        if self.log_policy == "all":
            if self.context is None:
                print("Ввод (команда): ", voice_input_str)
            else:
                print("Ввод (команда в контексте): ", voice_input_str)

        try:
            voice_input = voice_input_str.split(" ")
            if self.context is None:
                # Ищем обращение по имени ("тест", "легион" и т.п.)
                for ind in range(len(voice_input)):
                    callname = voice_input[ind]

                    if callname in self.voice_names:
                        self.cur_callname = callname
                        if self.log_policy == "cmd":
                            print("Ввод (команда): ", voice_input_str)

                        # Остаток после имени ассистента
                        command_options = " ".join([
                            str(input_part) for input_part in voice_input[(ind + 1):len(voice_input)]
                        ])

                        # Доп. подстановка команды для конкретного имени
                        if callname in self.voice_name_run_cmd:
                            command_options = self.voice_name_run_cmd.get(callname) + " " + command_options
                            print("Модифицированный ввод, добавлено ", self.voice_name_run_cmd.get(callname))

                        # Хук: выполнить что-то до запуска команды
                        if func_before_run_cmd is not None:
                            func_before_run_cmd()

                        self.execute_next(command_options, None)
                        haveRun = True
                        break
            else:
                if self.log_policy == "cmd":
                    print("Ввод (команда в контексте): ", voice_input_str)

                if func_before_run_cmd is not None:
                    func_before_run_cmd()

                # Внутри контекста вся строка уходит на дальнейший разбор
                self.execute_next(voice_input_str, self.context)
                haveRun = True

        except Exception as err:
            print(traceback.format_exc())

        return haveRun

    """
        Устанавливает новый контекст и запускает таймер его очистки

        Если context_remote_wait_for_call=True и используется удалённый TTS (saytxt/saywav), таймер может стартовать позже (после фактического вывода)
    """
    def context_set(self, context, duration=None):
        if duration is None:
            duration = self.context_default_duration

        self.context_clear()

        self.context = context
        self.context_timer_last_duration = duration
        self.context_timer = Timer(duration, self._context_clear_timer)

        remote_tts_list = self.remote_tts.split(",")
        if self.context_remote_wait_for_call and ("saytxt" in remote_tts_list or "saywav" in remote_tts_list):
            # Ждём явного старта
            # например, после отправки ответа клиенту
            pass
        else:
            self.context_timer.start()

    """
        Колбэк таймера контекста: очищает активный контекст
    """
    def _context_clear_timer(self):
        print("Context cleared after timeout")
        self.context_timer = None
        self.context_clear()

    """
        Сбрасывает текущий контекст и отменяет таймер, если он активен
    """
    def context_clear(self):
        self.context = None
        if self.context_timer is not None:
            self.context_timer.cancel()
            self.context_timer = None
