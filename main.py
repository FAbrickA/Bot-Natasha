import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
from time import sleep
from threading import Thread
import random
import datetime as dt
import os

TOKEN = os.environ.get("BOT_TOKEN")
UTC = 3
GROUP_ID = 198636539
PEER_TO_SEND = 2000000003  # 2000000001
utc_timedelta = dt.timedelta(hours=UTC)
ege = {
    "ege_russian": {
        "date": dt.datetime(2021, 6, 4, 10, 0, 0),
        "name": "ЕГЭ по Русскому",
    },
    "ege_math": {
        "date": dt.datetime(2021, 6, 7, 10, 0, 0),
        "name": "ЕГЭ по Математике",
    },
    "ege_info": {
        "date": dt.datetime(2021, 6, 25, 10, 0, 0),
        "name": "ЕГЭ по Информатике",
    },
}


class MyVkBotLongPoll(VkBotLongPoll):
    def listen(self):
        while True:
            try:
                for event in self.check():
                    yield event
            except Exception as e:
                print("listen_error", e)
                sleep(5)


class EverydaySend(Thread):
    def __init__(self, hours=0, minutes=0, seconds=0):
        super().__init__()
        self.seconds = (hours - UTC) * 60 * 60 + minutes * 60 + seconds
        self.day_to_seconds = 24 * 60 * 60

    def run(self):
        pass

    def sleep_to_next_call(self, debug=False):
        now = dt.datetime.utcnow()
        weekday = now.weekday()
        today_time = now - dt.datetime(year=now.year, month=now.month, day=now.day)
        seconds = today_time / dt.timedelta(seconds=1)
        time_to_next_call = self.seconds - seconds  # Время в секундах до первого вызова
        if time_to_next_call < 0:
            time_to_next_call += self.day_to_seconds
            weekday = (weekday + 1) % 7
        print(time_to_next_call)
        if not debug:
            sleep(time_to_next_call)


class SendTodayEge(EverydaySend):
    def __init__(self, vk, hours=0, minutes=0, seconds=0):
        super().__init__(hours, minutes, seconds)
        self.vk = vk

    def run(self):
        self.sleep_to_next_call(debug=False)

        while True:
            send_ege_poll(self.vk, PEER_TO_SEND)
            self.sleep_to_next_call(debug=False)


def timedelta_to_humanity(delta: dt.timedelta):
    def get_numbers_form(number, forms):
        number %= 100
        if number // 10 == 1:
            return forms[0]
        number %= 10
        if number == 1:
            return forms[1]
        elif number in (2, 3, 4):
            return forms[2]
        return forms[0]

    days_forms = ["дней", "день", "дня"]
    hours_forms = ["часов", "час", "часа"]
    minutes_forms = ["минут", "минута", "минуты"]
    seconds_forms = ["секунд", "секунда", "секунды"]
    days = int(delta.days)
    day_seconds = round(delta.seconds)
    hours = day_seconds // 3600
    minutes = day_seconds // 60 % 60
    seconds = day_seconds % 60
    days_str = f"{days} {get_numbers_form(days, days_forms)}"
    hours_str = f"{hours} {get_numbers_form(hours, hours_forms)}"
    minutes_str = f"{minutes} {get_numbers_form(minutes, minutes_forms)}"
    seconds_str = f"{seconds} {get_numbers_form(seconds, seconds_forms)}"
    if days >= 10:
        return f"{days_str} {hours_str} 😀"
    elif days >= 5:
        return f"{days_str} {hours_str} 😳"
    elif days >= 2:
        return f"{days_str} {hours_str} {minutes_str} 😱"
    else:
        return f"{hours_str} {minutes_str} {seconds_str} 😈"


def send_ege_poll(vk, peer_id=None):
    if peer_id is None:
        peer_id = PEER_TO_SEND
    nl = "\n"  # new line char
    nl2 = nl * 2
    now_utc = dt.datetime.utcnow()
    now = now_utc + utc_timedelta
    lines = []
    for value in sorted(ege.values(), key=lambda x: x['date']):
        if now < value['date']:
            lines.append(f"До {value['name']} осталось: \n"
                         f"{timedelta_to_humanity(value['date'] - now)}")
    if not lines:
        return
    text = f"😛 ЕГЭ скоро, даааа. Не забывайте! 😛 {nl2}" \
           f"{nl2.join(lines)}\n" \
           f"=============="
    vk.messages.send(
        peer_id=peer_id,
        message=text,
        random_id=get_random_id()
    )


def main():
    vk_session = vk_api.VkApi(token=TOKEN)
    longpool = MyVkBotLongPoll(vk_session, GROUP_ID)
    vk = vk_session.get_api()
    print("Bot started!")

    poll_10 = SendTodayEge(vk, hours=10, minutes=0, seconds=0)
    poll_18 = SendTodayEge(vk, hours=18, minutes=0, seconds=0)
    poll_10.start()
    poll_18.start()

    for event in longpool.listen():
        try:
            if event.type == VkBotEventType.MESSAGE_NEW:
                print(event.object.message)
                text = event.object.message['text'].strip()
                if not text:
                    continue
                if event.from_user:  # Если написали в ЛС
                    if "ты тут" in text.lower():
                        vk.messages.send(
                            peer_id=event.message['from_id'],
                            message="Да!",
                            random_id=get_random_id()
                        )
                else:
                    peer_id = event.message['peer_id']
                    if peer_id != PEER_TO_SEND:
                        print(f"Unknown peer_id: {peer_id}")
                        continue
                    lower_text = text.lower()
                    if any(lower_text.startswith(value) for value in (
                        '.апдейт',
                        '.update',
                        '.список'
                    )):
                        send_ege_poll(vk, peer_id)
        except Exception as e:
            print(e)

    print("End work!")


if __name__ == '__main__':
    main()
