import vk_api
from vk_api.utils import get_random_id
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import psycopg2
import os
import datetime as dt
from time import sleep
from threading import Thread
from random import choice


# first april edition готово
TOKEN = os.environ.get("BOT_TOKEN")
EVERYDAY_EATING_DB = os.environ.get("DATABASE_URL")
DB_PATH = "db"
RESTORE_DB = os.environ.get("HEROKU_POSTGRESQL_ORANGE_URL")
PROFIT_DB = 'profit'
EAT_TYPES = ["Завтрак", "Обед, карта", "Обед, наличка"]
GROUP_ID = 198636539
INF = 999999999999999
MY_ID = 222737315
UTC = 3
watch_eaters = False
all_eaters = {}  # key: peer_id, value: {'breakfast': [], 'dinner_card': [], 'dinner_nal'},
all_minimal_messages = {}  # Для хранения id сообщения с записью о столовке
message_after_list = {}  # Хранит conv.id сообщений после команды .список
TEST = False
utc_timedelta = dt.timedelta(hours=UTC)

ege_russian_date = dt.datetime(2021, 6, 4, 10, 0, 0) - utc_timedelta


class EverydaySend(Thread):
    def __init__(self, hours=0, minutes=0, seconds=0):
        super().__init__()
        self.seconds = (hours - UTC) * 60 * 60 + minutes * 60 + seconds
        self.day_to_seconds = 24 * 60 * 60

    def sleep_to_next_call(self, debug=False, finish=False):
        now = dt.datetime.utcnow()
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

        self.sleep_to_next_call(debug=False)  # !!!
        while True:
            set_watch_eaters(True)
            count_peers = 200
            drop_restore_db()
            set_config_restore()
            for i in range(1, count_peers + 1):
                if i == 3 and TEST:
                    continue
                peer_id = 2000000000 + i
                try:
                    eaters = get_saved_eaters(peer_id)
                    create_table_restore(peer_id)
                    new_eaters = {'breakfast': [], 'dinner_card': [], 'dinner_nal': []}
                    for eater in eaters:
                        user_id, eat_types = eater
                        eat_types = str(eat_types)
                        name = get_username(user_id=user_id)
                        add_today_eater_restore(peer_id, user_id, eat_types)
                        if "1" in eat_types:
                            new_eaters['breakfast'].append((user_id, name, ""))
                        if "2" in eat_types:
                            new_eaters['dinner_card'].append((user_id, name, ""))
                        if "3" in eat_types:
                            new_eaters['dinner_nal'].append((user_id, name, ""))
                    all_eaters[peer_id] = new_eaters
                    # print(all_eaters)
                    send_message_chat(text=make_notification(all_eaters[peer_id]), id=peer_id)
                    delete_all_message(peer_id)
                    # break
                except vk_api.ApiError as e:
                    print("my_error1", e)
                    # break
                    if e.code == 917:
                        break
            self.sleep_to_next_call()


class FinishTodayPoll(EverydaySend):
    def __init__(self, hours=0, minutes=0, seconds=0):
        super().__init__(hours, minutes, seconds)

    def run(self):
        global watch_eaters

        # sleep(10)
        self.sleep_to_next_call(finish=True, debug=False)  # !!!
        while True:
            if not watch_eaters:
                self.sleep_to_next_call(finish=True)
                continue
            set_watch_eaters(False)
            count_peers = 200
            for i in range(1, count_peers + 1):
                if i == 3 and TEST:
                    continue
                peer_id = 2000000000 + i
                try:
                    if get_all_minimal_message(peer_id) is not None:
                        delete_message_from_chat(peer_id=peer_id)
                    elif peer_id in message_after_list:
                        try:
                            delete_message_from_chat(peer_id=peer_id,
                                                     conversation_message_id=message_after_list[peer_id])
                        except vk_api.ApiError as e:
                            print("Can't delete message((", e)
                    if peer_id in all_eaters:
                        send_message_chat(text=make_finish_notification(all_eaters[peer_id]), id=peer_id)
                    delete_all_message(peer_id)
                    # break
                except vk_api.ApiError as e:
                    print("my_error2", e)
                    # break
                    if e.code == 917:
                        break
            self.sleep_to_next_call(finish=True)


def transliterate(string: str):
    dictionary = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
        'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h',
        'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sh', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e',
        'ю': 'u', 'я': 'ya'
    }
    new_string = ""
    for c in string:
        new_c = c
        c_lower = c.lower()
        if c_lower in dictionary:
            new_c = dictionary[c_lower]
            if c.isupper():
                new_c = new_c.capitalize()
        new_string += new_c
    return new_string


def get_username(user_id):  # Фамилия + имя
    response = vk_session.method(method='users.get',
                                 values={'user_ids': user_id})[0]
    name = response['first_name'] + " " + response['last_name']
    if name == "Роман Кислицын":
        name = "РоМаН КисЛиЦЫн"
    # return name
    # first april
    new_name = ""
    for word in name.split():
        new_name += "".join(list(word)[::-1]).capitalize() + " "
    return new_name[:-1]


# first april edit
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
    elif days >= 1:
        return f"{days_str} {hours_str} {minutes_str} 😱"
    else:
        return f"{hours_str} {minutes_str} {seconds_str} 😈"


def make_notification(eaters):
    def make_line(param):
        text = " - " + param[1]
        if len(param) < 3 or not param[2]:
            return text
        return text + f" ({param[2]})"

    # greetings = ["Привет, друзья!",
    #              "Приветствую всех!",
    #              "Доброго времени суток, друзья!",
    #              "Всем здравствуйте!",
    #              "Всем привет!"]
    greetings = ["Всем привет!"]
    breakfast = list(map(make_line, eaters.get('breakfast', [])))
    dinner_card = list(map(make_line, eaters.get('dinner_card', [])))
    dinner_nal = list(map(make_line, eaters.get('dinner_nal', [])))
    nl = "\n"
    # first april edit
    timedelta = ege_russian_date - dt.datetime.now()
    need_ege = True
    if timedelta.total_seconds() <= 0:
        need_ege = False
    text = f"{choice(greetings)} Начинается запись в столовую.\n\n" \
        f"1) Завтрак:\n" \
        f"{nl.join(breakfast) if breakfast else '...'}\n\n" \
        f"2) Обед, карта:\n" \
        f"{nl.join(dinner_card) if dinner_card else '...'}\n\n" \
        f"3) Обед, наличка:\n" \
        f"{nl.join(dinner_nal) if dinner_nal else '...'}\n\n" \
        f"First april edition 😛"  # first april edit
    if need_ege:  # first april edit
        ege_text = f"До ЕГЭ по русскому осталось: {timedelta_to_humanity(timedelta)}"
        text = ege_text + "\n\n" + text
    return text


def make_finish_notification(eaters):
    def make_line(param):
        text = " - " + param[1]
        if len(param) < 3 or not param[2]:
            return text
        return text + f" ({param[2]})"

    breakfast = list(map(make_line, eaters.get('breakfast', [])))
    dinner_card = list(map(make_line, eaters.get('dinner_card', [])))
    dinner_nal = list(map(make_line, eaters.get('dinner_nal', [])))
    nl = "\n"  # new line
    weekdays = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]
    today_weekday = weekdays[dt.date.today().weekday()]
    today_date = date_to_string(dt.datetime.now(), only_date=True)
    # first april edit
    timedelta = ege_russian_date - dt.datetime.now()
    need_ege = True
    if timedelta.total_seconds() <= 0:
        need_ege = False
    text = f"Итак, друзья. Запись в столовую на {today_weekday} {today_date} окончена!\n" \
        f"1) Завтрак:\n" \
        f"{nl.join(breakfast) if breakfast else '...'}\n\n" \
        f"2) Обед, карта:\n" \
        f"{nl.join(dinner_card) if dinner_card else '...'}\n\n" \
        f"3) Обед, наличка:\n" \
        f"{nl.join(dinner_nal) if dinner_nal else '...'}\n\n" \
        f"First april edition 😛"  # first april edit
    if need_ege:  # first april edit
        ege_text = f"До ЕГЭ по русскому осталось: {timedelta_to_humanity(timedelta)}"
        text = ege_text + "\n\n" + text

    return text


def date_to_string(date: dt.datetime, only_date=False):
    if only_date:
        return date.strftime("%d.%m.%Y")
    return date.strftime("%d.%m.%Y %H:%M:%S")


def string_to_date(date_str: str, only_date=False):
    if only_date:
        return dt.datetime.strptime(date_str, "%d.%m.%Y")
    return dt.datetime.strptime(date_str, "%d.%m.%Y %H:%M:%S")


def db_connect(path):
    # if not path.endswith(".db"):
    #     path += ".db"
    # return sqlite3.connect(path)
    return psycopg2.connect(path)


def create_table_everyday(chat_id):
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


def create_table_restore(chat_id):
    db = db_connect(RESTORE_DB)
    c = db.cursor()

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS "{chat_id}" (
        "user_id"       INTEGER,
        "eat_type"      INTEGER,
        "comments"      TEXT
        );
    """)

    db.commit()
    db.close()


def set_config(chat_id, chat_name="None"):
    db = db_connect(EVERYDAY_EATING_DB)
    c = db.cursor()

    c.execute(f"""
            CREATE TABLE IF NOT EXISTS "config" (
            "chat_id"       INTEGER UNIQUE,
            "chat_name"     TEXT
            );
            """)
    c.execute(f"""
        SELECT * FROM "config" WHERE chat_id = '{chat_id}'
    """)
    if not c.fetchone():
        c.execute(f"""
                INSERT INTO config VALUES ({chat_id}, '{chat_name}')
            """)

    db.commit()
    db.close()


def set_config_restore():
    db = db_connect(RESTORE_DB)
    c = db.cursor()

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS "config" (
        "watch_eaters"      INTEGER,
        "last_date"         TEXT
    );
    """)
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS "all_minimal_messages" (
        "peer_id"       INTEGER UNIQUE,
        "message_id"    INTEGER
        );
    """)
    c.execute(f"""
        SELECT * FROM "config"
    """)
    if not c.fetchone():
        c.execute(f"""
            INSERT INTO config VALUES ({1 if watch_eaters else 0}, '{date_to_string(dt.datetime.utcnow())}')
        """)

    db.commit()
    db.close()


def get_restore_config():
    """:returns watch_eaters, last_date"""
    db = db_connect(RESTORE_DB)
    c = db.cursor()
    c.execute("""SELECT * FROM "config" """)
    data = c.fetchone()
    db.close()
    return data


def set_all_minimal_message(peer_id, message_id):
    db = db_connect(RESTORE_DB)
    c = db.cursor()
    c.execute(f"""SELECT * FROM "all_minimal_messages" WHERE peer_id = {peer_id}""")
    if not c.fetchone():
        if message_id is not None:
            c.execute(f"""INSERT INTO "all_minimal_messages" VALUES ({peer_id}, {message_id})""")
    else:
        if message_id is not None:
            c.execute(f"""
                UPDATE "all_minimal_messages" 
                SET message_id = {message_id} WHERE peer_id = {peer_id}
            """)
        else:
            c.execute(f"""DELETE FROM "all_minimal_messages" WHERE peer_id = {peer_id}""")
    all_minimal_messages[peer_id] = message_id
    db.commit()
    db.close()


def delete_all_message(peer_id):
    set_all_minimal_message(peer_id, None)


def get_all_minimal_message(peer_id):
    db = db_connect(RESTORE_DB)
    c = db.cursor()
    c.execute(f"""SELECT message_id FROM "all_minimal_messages" WHERE peer_id = {peer_id}""")
    answer = c.fetchone()
    if answer is not None:
        answer = answer[0]
    return answer


def set_new_mods(chat_id, user_id, mods):
    db = db_connect(EVERYDAY_EATING_DB)
    c = db.cursor()

    set_config(chat_id)
    create_table_everyday(chat_id)

    c.execute(f"""
            SELECT * from "{chat_id}"
            WHERE user_id = '{user_id}'
        """)
    arr = c.fetchone()
    delete_flag = True if mods == "0" else False
    if not arr:
        if not delete_flag:
            c.execute(f"""
                INSERT INTO "{chat_id}" VALUES ({user_id}, '{mods}')
            """)
    else:
        if delete_flag:
            c.execute(f"""
                DELETE FROM "{chat_id}" WHERE user_id = {user_id}
            """)
        else:
            # mods_last = set(arr[2])
            # mods_new = set(list(mods))
            mods = "".join(sorted(list(mods), key=lambda x: int(x)))
            c.execute(f"""
                    UPDATE "{chat_id}"
                    SET eat_type = '{mods}' WHERE user_id = {user_id}
                """)

    db.commit()
    db.close()


def get_saved_eaters(chat_id):
    """:return user_id, eat_type"""
    db = db_connect(EVERYDAY_EATING_DB)
    c = db.cursor()

    set_config(chat_id)
    create_table_everyday(chat_id)

    c.execute(f"""SELECT * FROM "{chat_id}" """)
    arr = c.fetchall()

    db.commit()
    db.close()

    return arr


def get_restored_eaters(chat_id):
    """:return user_id, eat_type, comments"""
    db = db_connect(RESTORE_DB)
    c = db.cursor()

    # create_table_restore(chat_id)

    c.execute(f"""SELECT * FROM "{chat_id}" """)
    arr = c.fetchall()

    db.commit()
    db.close()

    return arr


def get_restored_eaters1(chat_id, user_id):
    """:return eat_type, comments"""
    db = db_connect(RESTORE_DB)
    c = db.cursor()

    create_table_restore(chat_id)

    c.execute(f"""SELECT eat_type, comments FROM "{chat_id}" WHERE user_id = {user_id} """)
    arr = c.fetchone()

    db.commit()
    db.close()

    return arr


def get_saved_eater1(chat_id, user_id):
    """:return eat_type"""
    db = db_connect(EVERYDAY_EATING_DB)
    c = db.cursor()

    set_config(chat_id)
    create_table_everyday(chat_id)

    c.execute(f"""SELECT eat_type FROM "{chat_id}" WHERE user_id = {user_id}""")
    arr = c.fetchall()

    db.commit()
    db.close()

    if not arr:
        return None
    return arr[0][0]


def set_watch_eaters(need_watch=False):
    global watch_eaters
    if watch_eaters == need_watch:
        return False
    watch_eaters = need_watch
    db = db_connect(RESTORE_DB)
    c = db.cursor()
    c.execute(f"""
        UPDATE "config"
        SET watch_eaters = {1 if watch_eaters else 0}, last_date = '{date_to_string(dt.datetime.utcnow())}'
    """)
    db.commit()
    db.close()


def add_today_eater_restore(chat_id, user_id, mods, comments=""):
    db = db_connect(RESTORE_DB)
    c = db.cursor()

    c.execute(f"""
        SELECT * from "{chat_id}"
        WHERE user_id = {user_id}
    """)
    arr = c.fetchone()
    delete_flag = True if mods == "0" else False
    if not arr:
        if not delete_flag:
            c.execute(f"""
                INSERT INTO "{chat_id}" VALUES ({user_id}, '{mods}', '{comments}')
            """)
    else:
        if delete_flag:
            c.execute(f"""
                DELETE FROM "{chat_id}" WHERE user_id = {user_id}
            """)
        else:
            # mods_last = set(arr[2])
            # mods_new = set(list(mods))
            mods = "".join(sorted(list(mods), key=lambda x: int(x)))
            c.execute(f"""
                UPDATE "{chat_id}"
                SET eat_type = '{mods}', comments = '{comments}' WHERE user_id = {user_id}
            """)

    db.commit()
    db.close()


def add_today_eater(peer_id, id, mod, comment=""):
    arr = None
    if mod == "1":
        arr = all_eaters[peer_id]['breakfast']
    elif mod == "2":
        arr = all_eaters[peer_id]['dinner_card']
    elif mod == "3":
        arr = all_eaters[peer_id]['dinner_nal']
    if arr is not None:
        find_user = False
        for i in range(len(arr)):
            params = arr[i]
            if params[0] == id:
                find_user = True
                arr[i] = params[0], params[1], comment
                break
        if not find_user:
            arr.append((id, get_username(id), comment))


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


def drop_restore_db():
    db = db_connect(RESTORE_DB)
    c = db.cursor()
    c.execute("""DROP TABLE IF EXISTS "config" """)
    c.execute("""DROP TABLE IF EXISTS "all_minimal_messages" """)
    count_peers = 15
    for i in range(1, count_peers + 1):
        peer_id = 2000000000 + i
        c.execute(f"""DROP TABLE IF EXISTS"{peer_id}" """)
    db.commit()
    db.close()


class MyVkBotLongPoll(VkBotLongPoll):
    def listen(self):
        while True:
            try:
                for event in self.check():
                    yield event
            except Exception as e:
                print("listen_error", e)
                sleep(5)


def do_restore(need_watch_eaters):
    global watch_eaters, all_eaters
    watch_eaters = need_watch_eaters
    count_peers = 15
    for i in range(1, count_peers + 1):
        peer_id = 2000000000 + i
        try:
            eaters = get_restored_eaters(peer_id)
        except Exception as e:
            # print("db_error", e)
            continue
        new_eaters = {'breakfast': [], 'dinner_card': [], 'dinner_nal': []}
        if not eaters:
            eaters = []
        for eater in eaters:
            user_id, eat_types, comments = eater
            comments = comments.split("\n")
            while len(comments) < 3:
                comments.append("")
            eat_types = str(eat_types)
            name = get_username(user_id=user_id)
            if "1" in eat_types:
                new_eaters['breakfast'].append((user_id, name, comments[0]))
            if "2" in eat_types:
                new_eaters['dinner_card'].append((user_id, name, comments[1]))
            if "3" in eat_types:
                new_eaters['dinner_nal'].append((user_id, name, comments[2]))
        all_eaters[peer_id] = new_eaters


vk_session = vk_api.VkApi(token=TOKEN)
longpool = MyVkBotLongPoll(vk_session, GROUP_ID)
vk = vk_session.get_api()
print("Bot started!")
set_config_restore()
data = get_restore_config()
need_watch_eaters, last_date = bool(data[0]), string_to_date(data[1])
now = dt.datetime.utcnow()
if now - last_date < dt.timedelta(hours=23, minutes=55):
    do_restore(need_watch_eaters)
else:
    pass
    # drop_restore_db()


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
    try:
        if conversation_message_id is None:
            conversation_message_id = get_all_minimal_message(peer_id)
        vk_session.method(method="messages.edit",
                          values={'peer_id': peer_id,
                                  'message': "(deleted)",
                                  'group_id': GROUP_ID,
                                  'conversation_message_id': conversation_message_id})
    except vk_api.VkApiError as e:
        print("can't delete message", e)


def pin_message(peer_id, conversation_message_id):
    vk_session.method(method="messages.pin",
                      values={'peer_id': peer_id,
                              'conversation_message_id': get_all_minimal_message(peer_id)})


send_poll = SendTodayPoll(hours=17, minutes=0)
finish_poll = FinishTodayPoll(hours=8, minutes=10)
send_poll.start()
finish_poll.start()

for event in longpool.listen():
    try:
        if event.type == VkBotEventType.MESSAGE_NEW:
            print(event.object.message)
            text = event.object.message['text'].strip()
            if not text:
                continue
            if event.from_user:  # Если написали в ЛС
                if "ты тут" in text.lower():
                    send_message_ls("Да!", event.message['from_id'])
                # send_message_ls(text, event.message['from_id'])
                # pass
            else:
                peer_id = event.message['peer_id']
                conversation_message_id = event.message['conversation_message_id']
                if get_all_minimal_message(peer_id) is None:
                    set_all_minimal_message(peer_id, conversation_message_id - 1)
                from_id = event.message['from_id']
                if text.startswith("."):
                    command = text[1:].strip().lower()
                    if command == "список":
                        if get_all_minimal_message(peer_id) is not None:
                            delete_message_from_chat(peer_id=peer_id)
                        set_all_minimal_message(peer_id, conversation_message_id + 1)
                        # message_after_list[peer_id] = conversation_message_id + 1
                        if watch_eaters:
                            # vk_session.method(method='messages.unpin',
                            #                   values={'peer_id': peer_id})
                            send_message_chat(text=make_notification(all_eaters[peer_id]), id=peer_id)
                        else:
                            send_message_chat(text=make_finish_notification(all_eaters[peer_id]), id=peer_id)
                        # all_minimal_messages[peer_id] = None
                elif watch_eaters:
                    if not text:
                        continue
                    text = text.split()
                    command = text[0]
                    comment = transliterate(" ".join(text[1:]))  # first april edit
                    if command.startswith("++"):
                        if len(command) > 2:
                            mods = get_saved_eater1(chat_id=peer_id, user_id=from_id)
                            mods = str(mods) if mods else ""
                            mod = command[2]
                            if mod not in "123":
                                continue
                            if not mods:
                                set_new_mods(peer_id, user_id=from_id, mods=mod)
                            else:
                                mods = "".join(list(set(list(mods)) | set(mod)))
                                set_new_mods(peer_id, user_id=from_id, mods=mods)
                        command = command[1:]
                    if command.startswith("+"):
                        if len(command) > 1:
                            mod = command[1]
                            if mod not in "123":
                                continue
                            add_today_eater(peer_id=peer_id, id=from_id, mod=mod, comment=comment)
                            vk_session.method(method="messages.edit",
                                              values={'peer_id': peer_id,
                                                      'message': make_notification(all_eaters[peer_id]),
                                                      'group_id': GROUP_ID,
                                                      'conversation_message_id': get_all_minimal_message(peer_id)})
                            data = get_restored_eaters1(chat_id=peer_id, user_id=from_id)
                            if data is None:
                                data = (None, "")
                            mods, comments = data
                            comments = comments.split("\n")
                            while len(comments) < 3:
                                comments.append("")
                            mods = str(mods) if mods else ""
                            index = "123".find(mod)
                            comments[index] = comment
                            comments = "\n".join(comments)
                            if not mods:
                                add_today_eater_restore(peer_id, user_id=from_id, mods=mod, comments=comments)
                            else:
                                mods = "".join(list(set(list(mods)) | set(mod)))
                                add_today_eater_restore(peer_id, user_id=from_id, mods=mods, comments=comments)
                    elif command.startswith("--") or command.startswith("—"):
                        if command.startswith("—"):
                            command = "--" + command[1:]
                        if len(command) > 2:
                            mods = get_saved_eater1(chat_id=peer_id, user_id=from_id)
                            mods = str(mods) if mods else ""
                            mod = command[2]
                            if mod not in "123":
                                continue
                            if mods:
                                if mods == mod:
                                    set_new_mods(peer_id, user_id=from_id, mods="0")
                                else:
                                    mods = "".join(list(set(list(mods)) - set(mod)))
                                    set_new_mods(peer_id, user_id=from_id, mods=mods)
                        command = command[1:]
                    if command.startswith("-"):
                        if len(command) > 1:
                            mod = command[1]
                            if mod not in "123":
                                continue
                            delete_today_eater(peer_id=peer_id, id=from_id, mod=mod)
                            try:
                                vk_session.method(method="messages.edit",
                                                  values={'peer_id': peer_id,
                                                          'message': make_notification(all_eaters[peer_id]),
                                                          'group_id': GROUP_ID,
                                                          'conversation_message_id': get_all_minimal_message(peer_id)})
                            except Exception as e:
                                print("error 111", e)
                            try:
                                data = get_restored_eaters1(chat_id=peer_id, user_id=from_id)
                            except Exception as e:
                                print("error 222", e)
                            if data is None:
                                data = (None, "")
                            mods, comments = data
                            comments = comments.split("\n")
                            while len(comments) < 3:
                                comments.append("")
                            mods = str(mods) if mods else ""
                            index = "123".find(mod)
                            comments[index] = ""
                            comments = "\n".join(comments)
                            if mods:
                                if mods == mod:
                                    add_today_eater_restore(peer_id, user_id=from_id, mods="0", comments=comments)
                                else:
                                    mods = "".join(list(set(list(mods)) - set(mod)))
                                    add_today_eater_restore(peer_id, user_id=from_id, mods=mods, comments=comments)
    except vk_api.VkApiError as e:
        print("my_longpoll", e)
    except Exception as e:
        print("my_longpoll-1", e)
