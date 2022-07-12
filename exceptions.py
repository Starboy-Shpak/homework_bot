class HTTPStatusError(Exception):
    """API вернул статус не равный 200."""
    pass


class UndocumentedHomeworkStatusError(Exception):
    """API передало неизвестный статус домашней работы."""
    pass


class NoHomeworksKeyInResponseError(TypeError):
    """
    В ответе API отсутствует ключ homeworks.
    Если наследоваться от Exception - пайтесты не проходят.
    """
    pass


class NoCurrentDateKeyInResponseError(Exception):
    """В ответе API отсутствует ключ current_date."""
    pass
