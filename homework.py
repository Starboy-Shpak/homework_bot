from asyncio.log import logger
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


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
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
    timestamp = 0 or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.RequestException as error:
        logger.error('Ошибка при запросе к эндпоинту! {error}')
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
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if not homework_status:
        raise KeyError('В домашней работе отсутствует ключ `homework_status`!')
    if homework_status not in HOMEWORK_STATUSES:
        raise exceptions.UndocumentedHomeworkStatusError(
            f'Статуса {homework_status} нет в словаре HOMEWORK_STATUSES!'
        )

    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность необходимых переменных."""
    tokens_list = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }

    def check_tokens() -> bool:
        for token in tokens_list:
            if not token:
                return False
        return True
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        format=(
            '%(asctime)s - %(levelname)s - '
            '%(funcName)s: %(lineno)d - %(message)s'
        ),
        filename='main.log',
        level=logging.INFO,
        datefmt='%d-%m-%Y %H:%M:%S'
    )

    if not check_tokens():
        logger.critical(
            'Отсутствуют обязательные переменные окружения! '
            'Программа принудительно остановлена.')
        sys.exit(1)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    prev_error_report = {}

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logger.debug('Новых статусов по домашним работам нет.')
            for homework in homeworks:
                homework_status = parse_status(homework)
                homework_name = homework['homework_name']
                logger.info(
                    f'Статус домашней работы {homework_name} обновлён.')
                send_message(bot, homework_status)
            current_timestamp = int(time.time())

        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}')
            current_error_report = {
                error.__class__.__name__: str(error)
            }
            if current_error_report != prev_error_report:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
                prev_error_report = current_error_report.copy()
            time.sleep(RETRY_TIME)

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
