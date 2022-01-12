import datetime
import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

# Яндекс.Практикум открылся для студентов 12 февраля 2019 года в 9:00 UTC
PRACTICUM_BIRTHDAY = int(datetime.datetime(2019, 2, 12, 9, 0).timestamp())

VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(funcName)s, %(message)s, %(name)s'
)
logger = logging.getLogger(__name__)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение отправлено')
    except telegram.error.TelegramError:
        logger.error('Сбой при отправке сообщения')


def get_api_answer(current_timestamp):
    """Выполняет запрос к API Практикум.Домашка."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        logger.error(error)
        raise error
    if response.status_code != HTTPStatus.OK:
        logger.error(f'Сбой в работе программы: Эндпоинт {ENDPOINT} '
                     f'недоступен. Код ответа API: {response.status_code}')
        raise requests.HTTPError('Неверный код ответа сервера. '
                                 f'{response.status_code}')
    try:
        return response.json()
    except ValueError as error:
        logger.error(error)
        raise ValueError('Ответ не содержит валидный JSON')


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ожидался словарь')
    if len(response) == 0:
        raise Exception('Ошибка в данных, пустой словарь')
    if 'homeworks' not in response.keys():
        message = 'Отсутствие ключа \'homeworks\' в словаре '
        logger.error(message)
        raise Exception(message)
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise Exception('Ошибка в данных')
    return homeworks


def parse_status(homework):
    """Извлекает статус работы из информации о конкретной домашней работе."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None:
        raise KeyError('Ошибка в данных: homework_name is None')
    if homework_status in VERDICTS.keys():
        verdict = VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        raise KeyError('Неожиданный статус домашней работы')


def check_tokens():
    """Проверяет доступность переменных окружения."""
    env = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for var in env:
        if var is None:
            logger.critical(
                f'Отсутствует обязательная переменная окружения: {var}')
            return False
    return True


def main():
    """Основная логика работы бота."""
    homework_status = 'Unknown'
    last_error = None
    if check_tokens() is False:
        return
    else:
        try:
            bot = telegram.Bot(token=TELEGRAM_TOKEN)
        except telegram.error.TelegramError as error:
            logger.critical(f'Произошла ошибка при создании бота: {error} '
                            'программа остановлена')
            return
        while True:
            try:
                response = get_api_answer(PRACTICUM_BIRTHDAY)
                homeworks = check_response(response)
                if homeworks:
                    last_homework = homeworks[0]
                    status = parse_status(last_homework)
                    if homework_status != status:
                        homework_status = status
                        send_message(bot, status)
                    else:
                        logger.info('Статус проверки задания'
                                    ' не обновился')
                else:
                    raise Exception('С указанного момента времени'
                                    ' не было сданных домашних заданий')
            except Exception as error:
                if error != last_error:
                    message = f'Сбой в работе программы: {error}'
                    logger.error(message)
                    send_message(bot, message)
                    last_error = error
                time.sleep(RETRY_TIME)
            else:
                time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
