import vk_api
from vk_api.utils import get_random_id
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import sqlite3
import os
import datetime as dt
from time import sleep
from threading import Thread
from random import choice
import os
# import json

TOKEN = os.environ.get("BOT_TOKEN")
DB_PATH = "db"
EVERYDAY_EATING_DB = "everyday_eat"
RESTORE_DB = 'restore_inf'
PROFIT_DB = 'profit'
EAT_TYPES = ["Завтрак", "Обед, карта", "Обед, наличка"]
GROUP_ID = 198636539
INF = 999999999999999
MY_ID = 222737315
watch_eaters = False
all_eaters = {}  # key: peer_id, value: {'breakfast': [], 'dinner_card': [] ...},
all_minimal_messages = {}  # Для хранения id сообщения с записью о столовке
message_after_list = {}  # Хранит conv.id сообщений после команды .список


if not os.path.exists(DB_PATH):
    os.mkdir(DB_PATH)


# def init_restore():
#     global all_eaters, all_minimal_messages
#
#     db = db_connect(RESTORE_DB)
#     c = db.cursor()
#
#     c.execute(f"""
#                 CREATE TABLE IF NOT EXISTS "all_eaters" (
#                 "peer_id"       INTEGER,
#                 "eaters"        TEXT
#                 );
#             """)
#     c.execute(f"""
#         SELECT * FROM "all_eaters"
#         """)
#     arr = c.fetchall()
#     print(arr)
#     for key, value in arr:
#         all_eaters[key] = json.loads(value)
#     print(all_eaters)
#
#     c.execute(f"""
#                 CREATE TABLE IF NOT EXISTS "all_minimal_messages" (
#                 "peer_id"           INTEGER,
#                 "conv_message_id"   INTEGER
#                 );
#             """)
#     c.execute(f"""
#             SELECT * FROM "all_minimal_messages"
#         """)
#     arr = c.fetchall()
#     print(arr)
#     for key, value in arr:
#         all_minimal_messages[key] = value
#     print(all_minimal_messages)
#
#     db.commit()
#     db.close()


# def clear_all_eaters_db():
#     db = db_connect(RESTORE_DB)
#     c = db.cursor()
#
#     c.execute(f"""
#         DROP TABLE IF EXISTS "all_eaters"
#         """)
#
#     db.commit()
#     db.close()


# def clear_all_minimal_messages_db():
#     db = db_connect(RESTORE_DB)
#     c = db.cursor()
#
#     c.execute(f"""
#         DROP TABLE IF EXISTS "all_minimal_messages"
#         """)
#
#     db.commit()
#     db.close()


# def store_all_eaters_db():
#     global all_eaters
#
#     db = db_connect(RESTORE_DB)
#     c = db.cursor()
#
#     for key, value in all_eaters.items():
#         c.execute(f"""
#             INSERT
#             """)


class EverydaySend(Thread):
    def __init__(self, hours=0, minutes=0, seconds=0):
        super().__init__()
        self.seconds = hours * 60 * 60 + minutes * 60 + seconds
        self.day_to_seconds = 24 * 60 * 60

    def sleep_to_next_call(self, debug=False, finish=False):
        now = dt.datetime.now()
        weekday = now.weekday()
        today_time = now - dt.datetime(year=now.year, month=now.month, day=now.day)
        seconds = today_time / dt.timedelta(seconds=1)
        time_to_next_call = self.seconds - seconds  # Время в секундах до первого вызова
        if time_to_next_call < 0:
            time_to_next_call += self.day_to_seconds
            weekday = (weekday + 1) % 7
        if finish:
            if weekday == 5:
                time_to_next_call += 2 * self.day_to_seconds
                weekday += 2
            elif weekday == 6:
                time_to_next_call += self.day_to_seconds
                weekday += 1
        else:
            if weekday == 4:
                time_to_next_call += 2 * self.day_to_seconds
                weekday += 2
            elif weekday == 5:
                time_to_next_call += self.day_to_seconds
                weekday += 1
        print(time_to_next_call)
        if not debug:
            sleep(time_to_next_call)


class SendTodayPoll(EverydaySend):
    def __init__(self, hours=0, minutes=0, seconds=0):
        super().__init__(hours, minutes, seconds)

    def run(self):
        global watch_eaters

        self.sleep_to_next_call(debug=True)  # !!!
        weekdays = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
        # conservations = vk_session.method(method='messages.getConversations',
        #                                   values={'count': 200, 'group_id': GROUP_ID, 'random_id': get_random_id()})
        # pprint(conservations['items'])
        while True:
            watch_eaters = True
            count_peers = 200
            for i in range(1, count_peers + 1):
                peer_id = 2000000000 + i
                try:
                    # send_message_chat(id=peer_id, text="Привет")
                    eaters = get_saved_eaters(peer_id)
                    # print(eaters)
                    new_eaters = {'breakfast': [], 'dinner_card': [], 'dinner_nal': []}
                    for eater in eaters:
                        user_id, eat_types = eater
                        eat_types = str(eat_types)
                        name = get_username(user_id=user_id)
                        if "1" in eat_types:
                            new_eaters['breakfast'].append((user_id, name))
                        if "2" in eat_types:
                            new_eaters['dinner_card'].append((user_id, name))
                        if "3" in eat_types:
                            new_eaters['dinner_nal'].append((user_id, name))
                    all_eaters[peer_id] = new_eaters
                    # print(all_eaters)
                    send_message_chat(text=make_notification(all_eaters[peer_id]), id=peer_id)
                    all_minimal_messages[peer_id] = None
                    break
                except vk_api.ApiError as e:
                    print(e)
                    break
                    print2me(e)
                    if e.code == 917:
                        break
            self.sleep_to_next_call()


class FinishTodayPoll(EverydaySend):
    def __init__(self, hours=0, minutes=0, seconds=0):
        super().__init__(hours, minutes, seconds)

    def run(self):
        global watch_eaters

        sleep(30)
        self.sleep_to_next_call(finish=True, debug=True)  # !!!
        while True:
            watch_eaters = False
            count_peers = 200
            for i in range(1, count_peers + 1):
                peer_id = 2000000000 + i
                try:
                    if peer_id in all_minimal_messages and all_minimal_messages[peer_id] is not None:
                        delete_message_from_chat(peer_id=peer_id)
                    elif peer_id in message_after_list:
                        try:
                            delete_message_from_chat(peer_id=peer_id,
                                                     conversation_message_id=message_after_list[peer_id])
                        except vk_api.ApiError as e:
                            print("Can't delete message((", e)
                    send_message_chat(text=make_finish_notification(all_eaters[peer_id]), id=peer_id)
                    all_minimal_messages[peer_id] = None
                    break
                except vk_api.ApiError as e:
                    break
                    print(e)
                    if e.code == 917:
                        break
            self.sleep_to_next_call(finish=True)


def get_username(user_id):  # Фамилия + имя
    response = vk_session.method(method='users.get',
                                 values={'user_ids': user_id})[0]
    name = response['first_name'] + " " + response['last_name']
    if name == "Роман Кислицын":
        return "РоМаН КисЛиЦЫн"
    return response['first_name'] + " " + response['last_name']


def make_notification(eaters):
    greetings = ["Привет, друзья!",
                 "Приветствую всех!",
                 "Доброго времени суток, друзья!",
                 "Всем здравствуйте!",
                 "Всем привет!"]
    breakfast = list(map(lambda x: " - " + x[1], eaters.get('breakfast', [])))
    dinner_card = list(map(lambda x: " - " + x[1], eaters.get('dinner_card', [])))
    dinner_nal = list(map(lambda x: " - " + x[1], eaters.get('dinner_nal', [])))
    nl = "\n"
    text = f"{choice(greetings)} Начинается запись в столовую.\n\n" \
        f"1) Завтрак:\n" \
        f"{nl.join(breakfast) if breakfast else '...'}\n\n" \
        f"2) Обед, карта:\n" \
        f"{nl.join(dinner_card) if dinner_card else '...'}\n\n" \
        f"3) Обед, наличка:\n" \
        f"{nl.join(dinner_nal) if dinner_nal else '...'}\n\n"

    return text


def make_finish_notification(eaters):
    breakfast = list(map(lambda x: " - " + x[1], eaters.get('breakfast', [])))
    dinner_card = list(map(lambda x: " - " + x[1], eaters.get('dinner_card', [])))
    dinner_nal = list(map(lambda x: " - " + x[1], eaters.get('dinner_nal', [])))
    nl = "\n"  # new line
    weekdays = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]
    today_weekday = weekdays[dt.date.today().weekday()]
    today_date = date_to_string(dt.datetime.now(), only_date=True)
    text = f"Итак, друзья. Запись в столовую на {today_weekday} {today_date} окончена!\n" \
        f"1) Завтрак:\n" \
        f"{nl.join(breakfast) if breakfast else '...'}\n\n" \
        f"2) Обед, карта:\n" \
        f"{nl.join(dinner_card) if dinner_card else '...'}\n\n" \
        f"3) Обед, наличка:\n" \
        f"{nl.join(dinner_nal) if dinner_nal else '...'}\n\n"

    return text


def send_notification(chat_id):
    greetings = ["Привет, друзья!",
                 "Приветствую всех!",
                 "Доброго времени суток, друзья!",
                 "Всем здравствуйте!",
                 "Всем привет!",
                 "Guten Morgen!"]

    p = "+"  # plus
    m = ""  # minus

    text = f"{greetings[0]}\n" \
        f"Начинается запись в столовую! Кто будет есть, поставьте пожалуйста ++ *тип питания*\n" \
        f"Например, ++ Обед, карта\n" \
        f"Если хотите отменить запись, то нужно ввести {m * 2} *тип питания*\n" \
        f"Так же можно записаться на постоянку, чтобы каждый раз не отмечаться. Для этого нужно написать " \
        f"+++ *тип питания*, например, +++ Обед, карта.\n" \
        f"Отписаться от постоянки можно так: {m * 3} *тип питания*\n" \
        f"Прошу писать всё корректно и на всякий случай проверять, что вы появились в списке\n" \
        f"*Beta test*\n" \
        f"(c) Роман Кислицын"
    send_message_chat(id=chat_id, text=make_notification(eaters={}))


def date_to_string(date: dt.datetime, only_date=False):
    if only_date:
        return date.strftime("%d.%m.%Y")
    return date.strftime("%d.%m.%Y %H:%M:%S")


def db_connect(path):
    if len(path) > 2 and path[-3:] != ".db":
        path += ".db"
    return sqlite3.connect(DB_PATH + os.path.sep + path)


def create_table(chat_id):
    db = db_connect(EVERYDAY_EATING_DB)
    c = db.cursor()

    c.execute(f"""
            CREATE TABLE IF NOT EXISTS "{chat_id}" (
            "user_id"       INTEGER,
            "eat_type"      INTEGER
            );
            """)

    db.commit()
    db.close()


def set_config(chat_id, chat_name=""):
    db = db_connect(EVERYDAY_EATING_DB)
    c = db.cursor()

    c.execute(f"""
            CREATE TABLE IF NOT EXISTS "config" (
            "chat_id"       INTEGER UNIQUE,
            "chat_name"     TEXT
            );
            """)
    c.execute(f"""
        SELECT * FROM 'config' WHERE chat_id = '{chat_id}'
        """)
    if not c.fetchone():
        c.execute(f"""
                INSERT INTO config VALUES (?, ?)
            """, (chat_id, chat_name))

    db.commit()
    db.close()


def set_new_mods(chat_id, user_id, mods):
    db = db_connect(EVERYDAY_EATING_DB)
    c = db.cursor()

    set_config(chat_id)
    create_table(chat_id)

    c.execute(f"""
            SELECT rowid, * from "{chat_id}"
            WHERE user_id = '{user_id}'
        """)
    arr = c.fetchone()
    delete_flag = True if mods == "0" else False
    if not arr:
        if not delete_flag:
            c.execute(f"""
                INSERT INTO "{chat_id}" VALUES (?, ?)
            """, (user_id, mods))
    else:
        if delete_flag:
            c.execute(f"""
                DELETE FROM "{chat_id}" WHERE rowid = {arr[0]}
            """)
        else:
            # mods_last = set(arr[2])
            # mods_new = set(list(mods))
            print(mods, "!")
            mods = "".join(sorted(list(mods), key=lambda x: int(x)))
            c.execute(f"""
                    UPDATE '{chat_id}'
                    SET eat_type = '{mods}'
                """)

    db.commit()
    db.close()


def get_saved_eaters(chat_id):
    """:return user_id, eat_type"""
    db = db_connect(EVERYDAY_EATING_DB)
    c = db.cursor()

    set_config(chat_id)
    create_table(chat_id)

    c.execute(f"""SELECT * FROM '{chat_id}'""")
    arr = c.fetchall()

    db.commit()
    db.close()

    return arr


def get_saved_eater1(chat_id, user_id):
    """:return user_id, eat_type"""
    db = db_connect(EVERYDAY_EATING_DB)
    c = db.cursor()

    set_config(chat_id)
    create_table(chat_id)

    c.execute(f"""SELECT eat_type FROM '{chat_id}' WHERE user_id = '{user_id}'""")
    arr = c.fetchall()

    db.commit()
    db.close()

    if not arr:
        return None
    return arr[0][0]


def add_today_eater(peer_id, id, mod):
    if mod == "1":
        if id not in list(map(lambda x: x[0], all_eaters[peer_id]['breakfast'])):
            all_eaters[peer_id]['breakfast'].append((id, get_username(id)))
    elif mod == "2":
        if id not in list(map(lambda x: x[0], all_eaters[peer_id]['dinner_card'])):
            all_eaters[peer_id]['dinner_card'].append((id, get_username(id)))
    elif mod == "3":
        if id not in list(map(lambda x: x[0], all_eaters[peer_id]['dinner_nal'])):
            all_eaters[peer_id]['dinner_nal'].append((id, get_username(id)))


def delete_today_eater(peer_id, id, mod):
    arr = None
    if mod == "1":
        arr = all_eaters[peer_id]['breakfast']
    elif mod == "2":
        arr = all_eaters[peer_id]['dinner_card']
    elif mod == "3":
        arr = all_eaters[peer_id]['dinner_nal']
    if arr is not None:
        for i in range(len(arr)):
            if arr[i][0] == id:
                arr.pop(i)
                return True


vk_session = vk_api.VkApi(token=TOKEN)
longpool = VkBotLongPoll(vk_session, GROUP_ID)
vk = vk_session.get_api()
print("Bot started!")


def send_message_ls(text, id):
    vk_session.method(method='messages.send',
                      values={'user_id': id, 'message': text, 'random_id': get_random_id()})


def print2me(text):
    send_message_ls(str(text), MY_ID)


def send_message_chat(text, id):
    return vk_session.method(method='messages.send',
                             values={'peer_id': id, 'message': text, 'random_id': get_random_id()})


def get_message_ids(peer_id, conversation_message_ids):
    message_ids = vk_session.method(method='messages.getByConversationMessageId',
                                    values={'peer_id': peer_id, 'group_id': GROUP_ID,
                                            'conversation_message_ids': conversation_message_ids})
    return message_ids['items']


def delete_message_from_chat(peer_id, conversation_message_id=None):
    if conversation_message_id is None:
        conversation_message_id = all_minimal_messages[peer_id]
    vk_session.method(method="messages.edit",
                      values={'peer_id': peer_id,
                              'message': "(deleted)",
                              'group_id': GROUP_ID,
                              'conversation_message_id': conversation_message_id})
    # return vk_session.method(method='messages.delete',
    #                          values={'message_ids': get_message_ids(peer_id, message_id)[0],
    #                                  'group_id': GROUP_ID,
    #                                  'delete_for_all': 1})


def pin_message(peer_id, conversation_message_id):
    vk_session.method(method="messages.pin",
                      values={'peer_id': peer_id,
                              'conversation_message_id': all_minimal_messages[peer_id]})


print("date now", dt.datetime.now())
send_poll = SendTodayPoll(hours=18)
finish_poll = FinishTodayPoll(hours=8)
send_poll.start()
finish_poll.start()

for event in longpool.listen():
    try:
        if event.type == VkBotEventType.MESSAGE_NEW:
            print(event)
            text = event.object.message['text'].strip()
            if not text:
                continue
            if event.from_user:  # Если написали в ЛС
                # if text.startswith("."):
                #     commands = text.split()[1:]
                #     if commands[0] == "add":
                #         peer_id = int(commands[1])
                #         user_id = int(commands[2])
                #         add_today_eater(peer_id=peer_id, id=user_id, mod=mod)
                #         vk_session.method(method="messages.edit",
                #                           values={'peer_id': peer_id,
                #                                   'message': make_notification(all_eaters[peer_id]),
                #                                   'group_id': GROUP_ID,
                #                                   'conversation_message_id': all_minimal_messages[peer_id]})
                #
                send_message_ls(text, event.message['from_id'])
            else:
                peer_id = event.message['peer_id']
                conversation_message_id = event.message['conversation_message_id']
                if peer_id not in all_minimal_messages or all_minimal_messages[peer_id] is None:
                    all_minimal_messages[peer_id] = conversation_message_id - 1
                from_id = event.message['from_id']
                if text.startswith("."):
                    command = text[1:].strip().lower()
                    if command == "список":
                        if peer_id in all_minimal_messages and all_minimal_messages[peer_id] is not None:
                            delete_message_from_chat(peer_id=peer_id)
                        message_after_list[peer_id] = conversation_message_id + 1
                        if watch_eaters:
                            # vk_session.method(method='messages.unpin',
                            #                   values={'peer_id': peer_id})
                            send_message_chat(text=make_notification(all_eaters[peer_id]), id=peer_id)
                        else:
                            send_message_chat(text=make_finish_notification(all_eaters[peer_id]), id=peer_id)
                        all_minimal_messages[peer_id] = None
                elif watch_eaters:
                    text = text.replace(" ", "")
                    if text.startswith("++"):
                        if len(text) > 2:
                            mods = get_saved_eater1(chat_id=peer_id, user_id=from_id)
                            mods = str(mods) if mods else ""
                            mod = text[2]
                            if mod not in "123":
                                continue
                            if not mods:
                                set_new_mods(peer_id, user_id=from_id, mods=mod)
                            else:
                                mods = "".join(list(set(list(mods)) | set(mod)))
                                set_new_mods(peer_id, user_id=from_id, mods=mods)
                        text = text[1:]
                    if text.startswith("+"):
                        if len(text) > 1:
                            mod = text[1]
                            if mod not in "123":
                                continue
                            add_today_eater(peer_id=peer_id, id=from_id, mod=mod)
                            vk_session.method(method="messages.edit",
                                              values={'peer_id': peer_id,
                                                      'message': make_notification(all_eaters[peer_id]),
                                                      'group_id': GROUP_ID,
                                                      'conversation_message_id': all_minimal_messages[peer_id]})
                    elif text.startswith("--") or text.startswith("—"):
                        if text.startswith("—"):
                            text = "--" + text[1:]
                        if len(text) > 2:
                            mods = get_saved_eater1(chat_id=peer_id, user_id=from_id)
                            mods = str(mods) if mods else ""
                            mod = text[2]
                            if mod not in "123":
                                continue
                            if mods:
                                if mods == mod:
                                    set_new_mods(peer_id, user_id=from_id, mods="0")
                                else:
                                    mods = "".join(list(set(list(mods)) - set(mod)))
                                    set_new_mods(peer_id, user_id=from_id, mods=mods)
                        text = text[1:]
                    if text.startswith("-"):
                        if len(text) > 1:
                            mod = text[1]
                            if mod not in "123":
                                continue
                            delete_today_eater(peer_id=peer_id, id=from_id, mod=mod)
                            vk_session.method(method="messages.edit",
                                              values={'peer_id': peer_id,
                                                      'message': make_notification(all_eaters[peer_id]),
                                                      'group_id': GROUP_ID,
                                                      'conversation_message_id': all_minimal_messages[peer_id]})
    except vk_api.VkApiError as e:
        longpool = VkBotLongPoll(vk_session, GROUP_ID)
        print(e)
        print2me(e)
