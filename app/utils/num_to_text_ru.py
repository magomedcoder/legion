import decimal
import sys

units = (
    u'ноль',

    (u'один', u'одна'),
    (u'два', u'две'),

    u'три', u'четыре', u'пять',
    u'шесть', u'семь', u'восемь', u'девять'
)

teens = (
    u'десять', u'одиннадцать',
    u'двенадцать', u'тринадцать',
    u'четырнадцать', u'пятнадцать',
    u'шестнадцать', u'семнадцать',
    u'восемнадцать', u'девятнадцать'
)

tens = (
    teens,
    u'двадцать', u'тридцать',
    u'сорок', u'пятьдесят',
    u'шестьдесят', u'семьдесят',
    u'восемьдесят', u'девяносто'
)

hundreds = (
    u'сто', u'двести',
    u'триста', u'четыреста',
    u'пятьсот', u'шестьсот',
    u'семьсот', u'восемьсот',
    u'девятьсот'
)

orders = (
    ((u'тысяча', u'тысячи', u'тысяч'), 'f'),
    ((u'миллион', u'миллиона', u'миллионов'), 'm'),
    ((u'миллиард', u'миллиарда', u'миллиардов'), 'm'),
)

minus = u'минус'

"""
    Преобразует число от 1 до 999 в список слов
    rest - остаток числа, sex - род ('m' или 'f')
    Возвращает
        plural - форма слова (0 - ед.ч., 1 - род.ед., 2 - род.множ.)
        name   - список слов (например, ['двадцать', 'три'])
"""
def thousand(rest, sex):
    prev = 0
    plural = 2
    name = []
    # Проверка, входят ли последние две цифры в диапазон 10–19
    use_teens = 10 <= rest % 100 <= 19

    # Если не "подростковое" число - используем единицы, десятки, сотни
    if not use_teens:
        data = ((units, 10), (tens, 100), (hundreds, 1000))
    else:
        data = ((teens, 10), (hundreds, 1000))

    for names, x in data:
        # Извлекаем нужную цифру
        cur = int(((rest - prev) % x) * 10 / x)
        prev = rest % x
        if x == 10 and use_teens:
            plural = 2
            name.append(teens[cur])
        elif cur == 0:
            continue
        elif x == 10:
            name_ = names[cur]
            if isinstance(name_, tuple):
                # Выбираем род
                name_ = name_[0 if sex == 'm' else 1]
            name.append(name_)
            if 2 <= cur <= 4:
                plural = 1
            elif cur == 1:
                plural = 0
            else:
                plural = 2
        else:
            name.append(names[cur - 1])
    return plural, name

"""
    Преобразует целое число в текст (на русском)
    main_units - ((ед.ч., род.ед., род.множ.), род)
"""
def num2text(num, main_units=((u'', u'', u''), 'm')):
    _orders = (main_units,) + orders
    if num == 0:
        return ' '.join((units[0], _orders[0][0][2])).strip()

    rest = abs(num)
    ord = 0
    name = []
    while rest > 0:
        plural, nme = thousand(rest % 1000, _orders[ord][1])
        if nme or ord == 0:
            # Добавляем название разряда
            name.append(_orders[ord][0][plural])
        name += nme
        rest = int(rest / 1000)
        ord += 1
    if num < 0:
        name.append(minus)
    name.reverse()
    return ' '.join(name).strip()

"""
    Преобразует десятичное число в текст с учётом дробной части
    places - сколько знаков после запятой озвучивать
    int_units - единицы для целой части
    exp_units - единицы для дробной части
"""
def decimal2text(value, places=2, int_units=(('', '', ''), 'm'), exp_units=(('', '', ''), 'm')):
    value = decimal.Decimal(value)
    q = decimal.Decimal(10) ** -places

    integral, exp = str(value.quantize(q)).split('.')
    return u'{} {}'.format(
        num2text(int(integral), int_units),
        num2text(int(exp), exp_units)
    )

if __name__ == '__main__':
    if len(sys.argv) > 1:
        try:
            num = sys.argv[1]
            if '.' in num:
                print(decimal2text(
                    decimal.Decimal(num),
                    int_units=((u'штука', u'штуки', u'штук'), 'f'),
                    exp_units=((u'кусок', u'куска', u'кусков'), 'm')))
            else:
                print(num2text(
                    int(num),
                    main_units=((u'штука', u'штуки', u'штук'), 'f')))
        except ValueError:
            print(sys.stderr, "Неверный аргумент {}".format(sys.argv[1]))
        sys.exit()
