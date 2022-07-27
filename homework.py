from loguru import logger
import logging
import os
import sys
import time

import requests
import telegram
import exceptions
from http import HTTPStatus

from dotenv import load_dotenv

load_dotenv()

logger.add(
    sys.stderr,
    format="{time} {level} {funcName} {message}",
    filter="main.log", level="INFO"
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_RETRY_TIME = 600

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Бот отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'{send_message.__name__} работает правильно')
    except telegram.TelegramError:
        logger.info(f'{send_message.__name__} не работает')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.RequestException as error:
        raise ConnectionError(
            'Ошибка при запросе к эндпоинту! {error}'
        ) from error
    if response.status_code != HTTPStatus.OK:
        raise exceptions.HTTPStatusError(
            f'{ENDPOINT} недоступен! Код: {response.status_code}.'
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if 'homeworks' not in response:
        raise exceptions.NoHomeworksKeyInResponseError(
            'В ответе API отсутствует ключ homeworks!'
        )
    if 'current_date' not in response:
        raise exceptions.NoCurrentDateKeyInResponseError(
            'В ответе API отсутствует ключ current_date!'
        )
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарём!')
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            'В ответе API по ключу homeworks значение не является списком!'
        )
    if not isinstance(response['current_date'], int):
        raise TypeError(
            'В ответе API по ключу current_date значение не является целым!'
        )
    return response['homeworks']


def parse_status(homework):
    """Достает статус из полученной домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status is None:
        raise KeyError('В домашней работе отсутствует ключ {homework_status}!')
    if homework_name is None:
        raise KeyError('В домашней работе отсутствует ключ {homework_name}!')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(
            f'Статуса {homework_status} нет в словаре HOMEWORK_VERDICTS!'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность необходимых токенов."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = ''
    for token in tokens:
        if not globals()[token]:
            missing_tokens += token
            logger.critical(f'Отсутствует {missing_tokens}!')
    if missing_tokens == '':
        return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(
            'Отсутствуют обязательные переменные окружения! '
            'Программа принудительно остановлена.')
        sys.exit(1)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    prev_error_report = {}
    prev_report = {}
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            for homework in homeworks:
                homework_status = parse_status(homework)
                if not homeworks:
                    logger.debug('Новых домашних работ нет.')
                current_report = {'name_homework': homework_status}
                if current_report != prev_report:
                    send_message(bot, homework_status)
                    prev_report = current_report.copy()
                else:
                    logger.debug('Отсутствие в ответе новых статусов')
                current_timestamp = response['current_date']
        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}')
            current_error_report = {
                error.__class__.__name__: str(error)
            }
            if current_error_report != prev_error_report:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
                prev_error_report = current_error_report.copy()

        finally:
            time.sleep(TELEGRAM_RETRY_TIME)


if __name__ == '__main__':
    main()
