import datetime
import logging
import os
import time

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

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info('Сообщение отправлено')
    except telegram.error.TelegramError:
        logging.error('Сбой при отправке сообщения')


def get_api_answer(current_timestamp):
    """Выполняет запрос к API Практикум.Домашка."""
    params = {'from_date': current_timestamp}
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    response = requests.get(ENDPOINT, headers=headers, params=params)
    status_code = response.status_code
    if status_code != 200:
        logging.error(f'Сбой в работе программы: {ENDPOINT}'
                      f' недоступен. Код ответа API: {status_code}')
        raise Exception('Неверный код ответа сервера.')
    else:
        return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ожидался словарь')
    if len(response) == 0:
        raise Exception('Ошибка в данных, пустой словарь')
    if 'homeworks' not in response.keys():
        message = 'Отсутствие ключа \'homeworks\' в словаре '
        logging.error(message)
        raise Exception(message)
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise Exception('Ошибка в данных')
    return homeworks


def parse_status(homework):
    """Извлекает статус работы из информации о конкретной домашней работе."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    env = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for var in env:
        if var is None:
            logging.critical(
                f'Отсутствует обязательная переменная окружения: {var}')
            return False
    return True


def main():
    """Основная логика работы бота."""
    homework_status = 'Unknown'
    last_error = None
    if check_tokens() is False:
        pass
    else:
        try:
            bot = telegram.Bot(token=TELEGRAM_TOKEN)
        except telegram.error.TelegramError as error:
            logging.critical(f'Произошла ошибка при создании бота: {error} '
                             f'программа остановлена')
        else:
            while True:
                try:
                    response = get_api_answer(PRACTICUM_BIRTHDAY)
                    homeworks = check_response(response)
                    if homeworks:
                        last_homework = homeworks.pop(0)
                        status = parse_status(last_homework)
                        if homework_status != status:
                            homework_status = status
                            send_message(bot, status)
                        else:
                            logging.info('Статус проверки задания'
                                         ' не обновился')
                    else:
                        raise Exception('С указанного момента времени'
                                        ' не было сданных домашних заданий')
                except Exception as error:
                    if error != last_error:
                        message = f'Сбой в работе программы: {error}'
                        print(message)
                        bot.send_message(message)
                        last_error = error
                    time.sleep(RETRY_TIME)
                else:
                    time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
