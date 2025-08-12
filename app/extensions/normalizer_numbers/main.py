import os

from app.core.core import Core

"""
    Регистрирует нормализатор текста, который преобразует числа в словесную форму
"""

modname = os.path.basename(__package__)[12:]

def start(core: Core):
    manifest = {
        "name": "Нормализатор чисел",

        "normalizer": {
            # ключ "numbers" - идентификатор движка нормализации
            # первый элемент кортежа: функция инициализации
            # второй элемент: функция, которая выполняет нормализацию текста
            "numbers": (init, normalize)
        }
    }
    return manifest

def start_with_options(core: Core, manifest: dict):
    pass

"""
    Инициализация нормализатора
"""
def init(core: Core):
    pass

"""
    Преобразует все числа в тексте в слова
    Например: 'Сегодня 12 градусов' -> 'Сегодня двенадцать градусов'
"""
def normalize(core: Core, text: str):
    return core.all_num_to_text(text)
