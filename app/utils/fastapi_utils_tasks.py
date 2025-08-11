import asyncio
import logging
from asyncio import ensure_future
from functools import wraps
from traceback import format_exception
from typing import Any, Callable, Coroutine, Optional, Union

from starlette.concurrency import run_in_threadpool

NoArgsNoReturnFuncT = Callable[[], None]
NoArgsNoReturnAsyncFuncT = Callable[[], Coroutine[Any, Any, None]]
NoArgsNoReturnDecorator = Callable[[Union[NoArgsNoReturnFuncT, NoArgsNoReturnAsyncFuncT]], NoArgsNoReturnAsyncFuncT]

"""
    Декоратор для периодического запуска функции
    Работает как с async, так и с обычными функциями

    seconds: float - интервал между вызовами в секундах
    wait_first: bool - если True, ждём первый интервал перед запуском
    logger: logging.Logger - логгер для вывода ошибок
    raise_exceptions: bool - если True, пробрасываем исключения (цикл останавливается)
    max_repetitions: int|None - максимум повторов (None = бесконечно)
"""

def repeat_every(*, seconds: float, wait_first: bool = False, logger: Optional[logging.Logger] = None, raise_exceptions: bool = False, max_repetitions: Optional[int] = None) -> NoArgsNoReturnDecorator:
    def decorator(func: Union[NoArgsNoReturnAsyncFuncT, NoArgsNoReturnFuncT]) -> NoArgsNoReturnAsyncFuncT:
        # Проверяем, является ли функция coroutine
        is_coroutine = asyncio.iscoroutinefunction(func)

        @wraps(func)
        async def wrapped() -> None:
            # Счётчик повторов
            repetitions = 0

            async def loop() -> None:
                nonlocal repetitions
                if wait_first:
                    # Задержка перед первым запуском
                    await asyncio.sleep(seconds)
                while max_repetitions is None or repetitions < max_repetitions:
                    try:
                        if is_coroutine:
                            await func()  # type: ignore
                        else:
                            # Синхронную функцию выполняем в threadpool
                            await run_in_threadpool(func)
                        repetitions += 1
                    except Exception as exc:
                        # Логируем ошибку
                        if logger is not None:
                            formatted_exception = "".join(format_exception(type(exc), exc, exc.__traceback__))
                            logger.error(formatted_exception)
                        if raise_exceptions:
                            raise exc
                    # Ждём перед следующим запуском
                    await asyncio.sleep(seconds)

            # Запускаем цикл в фоне
            ensure_future(loop())

        return wrapped

    return decorator
