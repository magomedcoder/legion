import re
import app.lib.lingua_franca
from app.lib.lingua_franca.format import pronounce_number

"""
    Загружает язык для библиотеки lingua_franca :param lang: код языка (например, 'ru' или 'en')
"""
def load_language(lang: str):
    app.lib.lingua_franca.load_language(lang)

"""
    Преобразует найденное число (целое или с плавающей точкой) в текст
    Использует pronounce_number из lingua_franca
"""
def convert_one_num_float(match_obj):
    if match_obj.group() is not None:
        return pronounce_number(float(match_obj.group()))

"""
    Преобразует диапазон чисел в текст
    Например: '120.1-120.8' -> 'сто двадцать целых одна десятая тире сто двадцать целых восемь десятых'
"""
def convert_diapazon(match_obj):
    if match_obj.group() is not None:
        text = str(match_obj.group())
        text = text.replace("-", " тире ")
        return all_num_to_text(text)

"""
    Находит и преобразует все числа в тексте в текстовую форму (пропись)

    Поддерживает
        числа с плавающей точкой
        отрицательные числа
        диапазоны
        проценты
"""
def all_num_to_text(text: str) -> str:
    # Диапазон с плавающей точкой
    text = re.sub(r'[\d]*[.][\d]+-[\d]*[.][\d]+', convert_diapazon, text)
    # Отрицательные числа с плавающей точкой
    text = re.sub(r'-[\d]*[.][\d]+', convert_one_num_float, text)
    # Положительные числа с плавающей точкой
    text = re.sub(r'[\d]*[.][\d]+', convert_one_num_float, text)
    # Диапазон целых чисел
    text = re.sub(r'[\d]-[\d]+', convert_diapazon, text)
    # Отрицательные целые числа
    text = re.sub(r'-[\d]+', convert_one_num_float, text)
    # Положительные целые числа
    text = re.sub(r'[\d]+', convert_one_num_float, text)
    # Заменяем знак процента на слово
    text = text.replace("%", " процентов")
    return text

if __name__ == "__main__":
    load_language("ru")
    print(all_num_to_text("Ба ва 120.1-120.8, Да -30.1, Ка 44.05, Га 225. Рынок -10%. Тест"))
