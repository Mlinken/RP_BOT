import asyncio
import sqlite3
import random
from datetime import date
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQueryResultArticle, InputTextMessageContent
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = "8587796773:AAHuFhOdn4UWATLSHS3k1eGdolw2VhfIpLo"

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

pending_details = {}
# Зберігаємо вибори в КНП: { inline_message_id: {user_id: choice} }
rps_games = {}
# Зберігаємо правда або дія: { inline_message_id: {initiator_id, initiator_name} }
tod_games = {}

# ─── FSM ─────────────────────────────────────

class AddAction(StatesGroup):
    waiting_for_type = State()
    waiting_for_data = State()

# ─── БАЗА ДАНИХ ──────────────────────────────

def init_db():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            cmd_limit INTEGER DEFAULT 1,
            last_work TEXT DEFAULT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS custom_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            code TEXT,
            name TEXT,
            past TEXT,
            emoji TEXT,
            illusion INTEGER DEFAULT 0
        )
    """)
    try:
        conn.execute("ALTER TABLE custom_actions ADD COLUMN illusion INTEGER DEFAULT 0")
        conn.commit()
    except:
        pass
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT balance, cmd_limit, last_work FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"balance": row[0], "limit": row[1], "last_work": row[2]}
    return {"balance": 0, "limit": 1, "last_work": None}

def ensure_user(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    ensure_user(user_id)
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def upgrade_limit(user_id):
    ensure_user(user_id)
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("UPDATE users SET cmd_limit = cmd_limit + 1, balance = balance - 100 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def set_last_work(user_id, today_str):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("UPDATE users SET last_work = ? WHERE user_id = ?", (today_str, user_id))
    conn.commit()
    conn.close()

def get_custom_actions(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT code, name, past, emoji, illusion FROM custom_actions WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return {
        row[0]: {
            "name": row[1], "past": row[2], "emoji": row[3],
            "prep": "", "custom": True, "illusion": bool(row[4])
        } for row in rows
    }

def count_custom_actions(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM custom_actions WHERE user_id = ?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def add_custom_action(user_id, name, past, emoji, illusion=False):
    code = f"c{user_id}_{name[:5]}"
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO custom_actions (user_id, code, name, past, emoji, illusion) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, code, name, past, emoji, 1 if illusion else 0)
    )
    conn.commit()
    conn.close()

def delete_custom_action(user_id, name):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("DELETE FROM custom_actions WHERE user_id = ? AND name = ?", (user_id, name))
    deleted = c.rowcount
    conn.commit()
    conn.close()
    return deleted > 0

def list_custom_actions(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT name, past, emoji, illusion FROM custom_actions WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

# ─── СТАНДАРТНІ РП ДІЇ ───────────────────────

RP_ACTIONS = {
    "h": {"name": "обійняти",   "emoji": "🤗", "past": "обійняв(ла)",     "prep": ""},
    "k": {"name": "поцілувати", "emoji": "💋", "past": "поцілував(ла)",   "prep": "в "},
    "p": {"name": "вдарити",    "emoji": "👊", "past": "вдарив(ла)",      "prep": "в "},
    "s": {"name": "погладити",  "emoji": "🖐️", "past": "погладив(ла)",    "prep": "по "},
    "u": {"name": "обнятися",   "emoji": "🫂", "past": "обнявся(лась) з", "prep": ""},
    "i": {"name": "трахнутись",   "emoji": "🔞", "past": "трахнув(ла)",     "prep": ""},
    "o": {"name": "потрогати",  "emoji": "🫴", "past": "потрогав(ла)",    "prep": ""},
    "f": {"name": "запустити",  "emoji": "🚀", "past": "запустив(ла)",    "prep": "", "illusion": True},
}

# ─── СТАРТ ──────────────────────────────────

@dp.message(Command("start"))
async def start(message: types.Message):
    ensure_user(message.from_user.id)
    await message.reply(
        "🇺🇦 Вітаю! Я український RP-бот.\n\n"
        "📝 В будь-якому чаті пиши:\n"
        "@ukrrp_Pero_bot рп обійняти\n"
        "@ukrrp_Pero_bot гра кнп\n"
        "@ukrrp_Pero_bot гра правда або дія\n\n"
        "─── Свої команди ───\n"
        "/add — додати команду\n"
        "/my — мої команди\n"
        "/delete — видалити команду\n"
        "/upgrade — +1 ліміт (100 монет)\n\n"
        "─── Економіка ───\n"
        "/balance — баланс\n"
        "/daily — щоденна нагорода\n\n"
        "─── Ігри ───\n"
        "/casino <ставка>\n"
        "/roulette <ставка>"
    )

# ─── ЩОДЕННА НАГОРОДА ────────────────────────

@dp.message(Command("daily"))
async def daily(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id)
    user = get_user(user_id)
    today = str(date.today())

    if user["last_work"] == today:
        await message.reply("⏰ Щоденна нагорода вже отримана!\nПоверніться завтра.")
        return

    update_balance(user_id, 10)
    set_last_work(user_id, today)
    new_bal = get_user(user_id)["balance"]
    await message.reply(f"✅ +10 монет 💰\nБаланс: {new_bal} монет")

# ─── БАЛАНС ─────────────────────────────────

@dp.message(Command("balance"))
async def balance(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id)
    user = get_user(user_id)
    await message.reply(
        f"💰 Баланс: {user['balance']} монет\n"
        f"📋 Команди: {count_custom_actions(user_id)}/{user['limit']}\n"
        f"🔓 /upgrade — розширити ліміт (100 монет)"
    )

# ─── КАЗИНО ─────────────────────────────────

@dp.message(Command("casino"))
async def casino(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id)
    user = get_user(user_id)

    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("❗ Вкажи ставку: /casino 50")
        return

    bet = int(parts[1])
    if bet < 10:
        await message.reply("❗ Мінімальна ставка — 10 монет!")
        return
    if bet > 500:
        await message.reply("❗ Максимальна ставка — 500 монет!")
        return
    if bet > user["balance"]:
        await message.reply(f"❌ Недостатньо монет! У тебе {user['balance']} монет.")
        return

    dice_msg = await message.reply("🎲 Кидаю кубик...")
    roll = random.randint(1, 6)
    DICE_EMOJI = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}

    if roll >= 4:
        update_balance(user_id, bet)
        new_bal = get_user(user_id)["balance"]
        await dice_msg.edit_text(
            f"{DICE_EMOJI[roll]} Випало {roll} — виграш!\n"
            f"+{bet} монет 🎉\nБаланс: {new_bal} монет"
        )
    else:
        update_balance(user_id, -bet)
        new_bal = get_user(user_id)["balance"]
        await dice_msg.edit_text(
            f"{DICE_EMOJI[roll]} Випало {roll} — програш!\n"
            f"-{bet} монет 😔\nБаланс: {new_bal} монет"
        )

# ─── РУЛЕТКА ────────────────────────────────

@dp.message(Command("roulette"))
async def roulette(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id)
    user = get_user(user_id)

    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("❗ Вкажи ставку: /roulette 50")
        return

    bet = int(parts[1])
    if bet < 10:
        await message.reply("❗ Мінімальна ставка — 10 монет!")
        return
    if bet > 500:
        await message.reply("❗ Максимальна ставка — 500 монет!")
        return
    if bet > user["balance"]:
        await message.reply(f"❌ Недостатньо монет! У тебе {user['balance']} монет.")
        return

    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔴 Червоне", callback_data=f"rl|red|{bet}|{user_id}"),
        InlineKeyboardButton(text="⚫ Чорне",   callback_data=f"rl|black|{bet}|{user_id}"),
        InlineKeyboardButton(text="🟢 Зелене x14", callback_data=f"rl|green|{bet}|{user_id}"),
    ]])
    await message.reply(
        f"🎰 Рулетка! Ставка: {bet} монет\n\n"
        f"🔴/⚫ — x2  |  🟢 — x14",
        reply_markup=markup
    )

@dp.callback_query(F.data.startswith("rl|"))
async def roulette_spin(callback: types.CallbackQuery):
    _, color, bet_str, owner_id = callback.data.split("|")
    bet = int(bet_str)
    owner_id = int(owner_id)

    if callback.from_user.id != owner_id:
        await callback.answer("⛔ Це не твоя рулетка!", show_alert=True)
        return

    user = get_user(owner_id)
    if bet > user["balance"]:
        await callback.answer("❌ Недостатньо монет!", show_alert=True)
        return

    number = random.randint(0, 36)
    if number == 0:
        result_color, result_emoji = "green", "🟢"
    elif number % 2 == 0:
        result_color, result_emoji = "black", "⚫"
    else:
        result_color, result_emoji = "red", "🔴"

    COLOR_NAMES = {"red": "Червоне", "black": "Чорне", "green": "Зелене"}
    chosen_emoji = {"red": "🔴", "black": "⚫", "green": "🟢"}

    if color == result_color:
        multiplier = 14 if color == "green" else 2
        winnings = bet * multiplier - bet
        update_balance(owner_id, winnings)
        new_bal = get_user(owner_id)["balance"]
        await callback.message.edit_text(
            f"🎰 {result_emoji} {number}!\n"
            f"{chosen_emoji[color]} {COLOR_NAMES[color]} — виграш!\n"
            f"+{winnings} монет 🎉\nБаланс: {new_bal} монет"
        )
    else:
        update_balance(owner_id, -bet)
        new_bal = get_user(owner_id)["balance"]
        await callback.message.edit_text(
            f"🎰 {result_emoji} {number}!\n"
            f"{chosen_emoji[color]} {COLOR_NAMES[color]} — програш!\n"
            f"-{bet} монет 😔\nБаланс: {new_bal} монет"
        )
    await callback.answer()

# ─── РОЗШИРИТИ ЛІМІТ ─────────────────────────

@dp.message(Command("upgrade"))
async def expand_limit(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id)
    user = get_user(user_id)

    if user["limit"] >= 10:
        await message.reply("✅ Максимальний ліміт — 10 команд!")
        return
    if user["balance"] < 100:
        await message.reply(
            f"❌ Потрібно 100 монет\n"
            f"У тебе: {user['balance']} монет"
        )
        return

    upgrade_limit(user_id)
    user = get_user(user_id)
    await message.reply(
        f"🔓 Ліміт розширено до {user['limit']} команд!\n"
        f"Баланс: {user['balance']} монет"
    )

# ─── ДОДАТИ КОМАНДУ ──────────────────────────

@dp.message(Command("add"))
async def add_action_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    ensure_user(user_id)
    user = get_user(user_id)

    if count_custom_actions(user_id) >= user["limit"]:
        await message.reply(
            f"❌ Ліміт ({count_custom_actions(user_id)}/{user['limit']})!\n"
            f"/upgrade — купити розширення (100 монет)"
        )
        return

    await state.set_state(AddAction.waiting_for_type)
    await message.reply(
        "Який тип команди?\n\n"
        "🔀 З вибором — можна прийняти або відхилити\n"
        "🎭 Ілюзія вибору — обидві кнопки погоджуються",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔀 З вибором",     callback_data="addtype|choice"),
            InlineKeyboardButton(text="🎭 Ілюзія вибору", callback_data="addtype|illusion"),
        ]])
    )

@dp.callback_query(F.data.startswith("addtype|"), AddAction.waiting_for_type)
async def add_action_type(callback: types.CallbackQuery, state: FSMContext):
    action_type = callback.data.split("|")[1]
    await state.update_data(illusion=(action_type == "illusion"))
    await state.set_state(AddAction.waiting_for_data)

    type_text = "🎭 Ілюзія вибору" if action_type == "illusion" else "🔀 З вибором"
    await callback.message.edit_text(
        f"Обрано: {type_text}\n\n"
        f"Напиши у форматі:\n"
        f"назва|результат|емодзі\n\n"
        f"Приклад: пограти|грає|🎮"
    )
    await callback.answer()

@dp.message(AddAction.waiting_for_data)
async def add_action_data(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    illusion = data.get("illusion", False)

    chunks = message.text.strip().split("|")
    if len(chunks) != 3:
        await message.reply("❗ Формат: назва|результат|емодзі\nПриклад: пограти|грає|🎮")
        return

    name, past, emoji = [c.strip() for c in chunks]
    if len(name) > 20 or len(past) > 20:
        await message.reply("❗ До 20 символів!")
        return

    add_custom_action(user_id, name, past, emoji, illusion)
    await state.clear()

    user = get_user(user_id)
    type_text = "🎭 Ілюзія вибору" if illusion else "🔀 З вибором"
    await message.reply(
        f"✅ Додано! {emoji} {name} → {past} ({type_text})\n"
        f"Використано: {count_custom_actions(user_id)}/{user['limit']}"
    )

# ─── МОЇ / ВИДАЛИТИ КОМАНДИ ─────────────────

@dp.message(Command("my"))
async def my_actions(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id)
    user = get_user(user_id)
    actions = list_custom_actions(user_id)

    if not actions:
        await message.reply("Немає команд. Додай: /add")
        return

    text = f"Твої команди ({len(actions)}/{user['limit']}):\n\n"
    for name, past, emoji, illusion in actions:
        icon = "🎭" if illusion else "🔀"
        text += f"{emoji} {name} → {past} {icon}\n"
    text += "\nВидалити: /delete назва"
    await message.reply(text)

@dp.message(Command("delete"))
async def delete_action(message: types.Message):
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        actions = list_custom_actions(user_id)
        if not actions:
            await message.reply("Немає команд.")
            return
        text = "Яку видалити?\n\n"
        for name, past, emoji, _ in actions:
            text += f"• /delete {name}\n"
        await message.reply(text)
        return

    name = parts[1].strip()
    if delete_custom_action(user_id, name):
        await message.reply(f"✅ «{name}» видалено!")
    else:
        await message.reply(f"❌ «{name}» не знайдено.")

# ─── INLINE QUERY ────────────────────────────

@dp.inline_query()
async def inline_query(query: types.InlineQuery):
    user = query.from_user
    short_name = user.first_name[:10]
    text = query.query.strip().lower()
    results = []

    # ── Категорія РП ──
    if text.startswith("рп") or text == "":
        # Прибираємо префікс "рп " щоб отримати уточнення
        detail_text = text[2:].strip() if text.startswith("рп") else ""

        all_rp = {**RP_ACTIONS, **get_custom_actions(user.id)}

        for code, data in all_rp.items():
            emoji = data["emoji"]
            action_name = data["name"]
            prep = data["prep"]
            is_illusion = data.get("illusion", False)
            is_custom = data.get("custom", False)

            if detail_text:
                display_text = (
                    f"{emoji} {user.first_name} пропонує {action_name} {prep}{detail_text}!"
                    if is_illusion
                    else f"{emoji} {user.first_name} хоче {action_name} {prep}{detail_text}!"
                )
            else:
                display_text = (
                    f"{emoji} {user.first_name} пропонує {action_name}!"
                    if is_illusion
                    else f"{emoji} {user.first_name} хоче {action_name}!"
                )

            if is_illusion:
                markup = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✅ Погодитись", callback_data=f"rp|a|{code}|{user.id}|{short_name}|0"),
                    InlineKeyboardButton(text="☑️ Звісно",    callback_data=f"rp|a|{code}|{user.id}|{short_name}|0"),
                ]])
            else:
                markup = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✅ Прийняти",  callback_data=f"rp|a|{code}|{user.id}|{short_name}|0"),
                    InlineKeyboardButton(text="❌ Відхилити", callback_data=f"rp|d|{code}|{user.id}|{short_name}|0"),
                ]])

            results.append(InlineQueryResultArticle(
                id=f"rp_{code}",
                title=f"{'⭐ ' if is_custom else ''}🎭 РП — {emoji} {action_name.capitalize()}",
                description=f"рп {action_name} {detail_text}".strip(),
                input_message_content=InputTextMessageContent(message_text=display_text),
                reply_markup=markup
            ))

    # ── Категорія ІГРИ ──
    if text.startswith("гра") or text == "":

        # КНП
        results.append(InlineQueryResultArticle(
            id="game_rps",
            title="✂️ Гра — Камінь Ножиці Папір",
            description="Зіграти з другом в КНП (+20 монет переможцю)",
            input_message_content=InputTextMessageContent(
                message_text=f"✂️ {user.first_name} запрошує пограти в Камінь-Ножиці-Папір!\nОбери свій варіант:"
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🪨 Камінь",  callback_data=f"rps|rock|{user.id}|{short_name}|?"),
                    InlineKeyboardButton(text="✂️ Ножиці", callback_data=f"rps|scissors|{user.id}|{short_name}|?"),
                    InlineKeyboardButton(text="📄 Папір",  callback_data=f"rps|paper|{user.id}|{short_name}|?"),
                ]
            ])
        ))

        # Правда або дія
        results.append(InlineQueryResultArticle(
            id="game_tod",
            title="🎯 Гра — Правда або Дія",
            description="Запропонувати другу правду або дію",
            input_message_content=InputTextMessageContent(
                message_text=f"🎯 {user.first_name} запрошує пограти в Правда або Дія!\nОбери:"
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🗣 Правда", callback_data=f"tod|truth|{user.id}|{short_name}"),
                InlineKeyboardButton(text="⚡ Дія",   callback_data=f"tod|dare|{user.id}|{short_name}"),
            ]])
        ))

    # ── Баланс ──
    if text == "" or text == "баланс":
        results.append(InlineQueryResultArticle(
            id="b",
            title="💰 Мій баланс",
            description="Показати баланс",
            input_message_content=InputTextMessageContent(
                message_text=f"💰 Баланс {user.first_name}: {get_user(user.id)['balance']} монет"
            )
        ))

    if not results:
        results.append(InlineQueryResultArticle(
            id="help",
            title="❓ Підказка",
            description="рп — РП команди  |  гра — ігри",
            input_message_content=InputTextMessageContent(
                message_text="Пиши:\n@бот рп обійняти\n@бот гра кнп\n@бот гра правда або дія"
            )
        ))

    await query.answer(results, cache_time=0, is_personal=False)

# ─── CHOSEN INLINE ───────────────────────────

@dp.chosen_inline_result()
async def chosen_inline(result: types.ChosenInlineResult):
    if not result.inline_message_id:
        return
    text = result.query.strip()
    if text.startswith("рп"):
        detail = text[2:].strip()
        if detail:
            pending_details[result.inline_message_id] = detail[:30]

# ─── РП КНОПКИ ───────────────────────────────

@dp.callback_query(F.data.startswith("rp|"))
async def rp_callback(callback: types.CallbackQuery):
    parts = callback.data.split("|")
    _, result, code, initiator_id, initiator_name, target_id = parts
    initiator_id = int(initiator_id)
    target_id_int = int(target_id)

    if callback.from_user.id == initiator_id:
        await callback.answer("🙃 Не можна відповісти на власний запит!", show_alert=True)
        return
    if target_id_int != 0 and callback.from_user.id != target_id_int:
        await callback.answer("⛔ Ця дія адресована іншій людині!", show_alert=True)
        return

    # Знімаємо префікс rp_ з коду
    clean_code = code.replace("rp_", "") if code.startswith("rp_") else code
    data = RP_ACTIONS.get(clean_code)
    if not data:
        conn = sqlite3.connect("bot.db")
        c = conn.cursor()
        c.execute("SELECT name, past, emoji, illusion FROM custom_actions WHERE code = ?", (clean_code,))
        row = c.fetchone()
        conn.close()
        data = {"name": row[0], "past": row[1], "emoji": row[2], "prep": "", "illusion": bool(row[3])} if row else {"emoji": "✨", "past": clean_code, "name": clean_code, "prep": ""}

    emoji = data["emoji"]
    past = data["past"]
    prep = data["prep"]
    responder_name = callback.from_user.first_name
    detail = pending_details.get(callback.inline_message_id, "")
    detail_text = f" {prep}{detail}" if detail else ""

    if result == "a":
        # Для ілюзії вибору — результат робить той хто натиснув (responder)
        is_illusion = data.get("illusion", False)
        if is_illusion:
            text = f"{emoji} {responder_name} {past}{detail_text}! ✅"
        else:
            text = f"{emoji} {initiator_name} {past} {responder_name}{detail_text}! ✅"
        await bot.edit_message_text(
            inline_message_id=callback.inline_message_id,
            text=text
        )
    elif result == "d":
        await bot.edit_message_text(
            inline_message_id=callback.inline_message_id,
            text=f"😔 {responder_name} відхилив(ла) пропозицію від {initiator_name}. ❌"
        )
        await callback.answer("Ти відхилив(ла).")
        pending_details.pop(callback.inline_message_id, None)

# ─── КНП КНОПКИ ──────────────────────────────

RPS_WINS = {
    "rock":     {"scissors": True,  "paper": False, "rock": None},
    "scissors": {"paper": True,     "rock": False,  "scissors": None},
    "paper":    {"rock": True,      "scissors": False, "paper": None},
}
RPS_EMOJI = {"rock": "🪨", "scissors": "✂️", "paper": "📄"}
RPS_NAME  = {"rock": "Камінь", "scissors": "Ножиці", "paper": "Папір"}

@dp.callback_query(F.data.startswith("rps|"))
async def rps_callback(callback: types.CallbackQuery):
    parts = callback.data.split("|")
    _, choice, initiator_id, initiator_name, p2_name = parts
    initiator_id = int(initiator_id)
    msg_id = callback.inline_message_id

    if msg_id not in rps_games:
        rps_games[msg_id] = {}

    # Перший гравець — ініціатор
    if callback.from_user.id == initiator_id:
        if initiator_id in rps_games[msg_id]:
            await callback.answer("Ти вже обрав!", show_alert=True)
            return
        rps_games[msg_id][initiator_id] = {
            "choice": choice,
            "name": initiator_name
        }
        await callback.answer(f"Ти обрав {RPS_EMOJI[choice]} {RPS_NAME[choice]}! Чекаємо суперника...")
    else:
        # Другий гравець
        p2_id = callback.from_user.id
        if p2_id in rps_games[msg_id]:
            await callback.answer("Ти вже обрав!", show_alert=True)
            return
        if p2_id == initiator_id:
            await callback.answer("Не можна грати з собою!", show_alert=True)
            return

        rps_games[msg_id][p2_id] = {
            "choice": choice,
            "name": callback.from_user.first_name
        }
        await callback.answer(f"Ти обрав {RPS_EMOJI[choice]} {RPS_NAME[choice]}!")

    # Якщо обидва обрали — показуємо результат
    if len(rps_games[msg_id]) == 2:
        players = list(rps_games[msg_id].items())
        p1_id, p1_data = players[0]
        p2_id, p2_data = players[1]
        p1_choice = p1_data["choice"]
        p2_choice = p2_data["choice"]
        p1_name = p1_data["name"]
        p2_name = p2_data["name"]

        result = RPS_WINS[p1_choice][p2_choice]

        if result is None:
            text = (
                f"✂️ Камінь-Ножиці-Папір!\n\n"
                f"{p1_name}: {RPS_EMOJI[p1_choice]} {RPS_NAME[p1_choice]}\n"
                f"{p2_name}: {RPS_EMOJI[p2_choice]} {RPS_NAME[p2_choice]}\n\n"
                f"🤝 Нічия!"
            )
        elif result:
            update_balance(p1_id, 20)
            text = (
                f"✂️ Камінь-Ножиці-Папір!\n\n"
                f"{p1_name}: {RPS_EMOJI[p1_choice]} {RPS_NAME[p1_choice]}\n"
                f"{p2_name}: {RPS_EMOJI[p2_choice]} {RPS_NAME[p2_choice]}\n\n"
                f"🏆 Переміг {p1_name}! +20 монет"
            )
        else:
            update_balance(p2_id, 20)
            text = (
                f"✂️ Камінь-Ножиці-Папір!\n\n"
                f"{p1_name}: {RPS_EMOJI[p1_choice]} {RPS_NAME[p1_choice]}\n"
                f"{p2_name}: {RPS_EMOJI[p2_choice]} {RPS_NAME[p2_choice]}\n\n"
                f"🏆 Переміг {p2_name}! +20 монет"
            )

        await bot.edit_message_text(
            inline_message_id=msg_id,
            text=text
        )
        rps_games.pop(msg_id, None)

# ─── ПРАВДА АБО ДІЯ ──────────────────────────

TOD_TRUTHS = [
    "Яка твоя найбільша таємниця?",
    "Кого з присутніх ти вважаєш найрозумнішим?",
    "Що ти ніколи не скажеш батькам?",
    "Твій найбільш незручний момент?",
    "Яка твоя найстрашніша фобія?",
]

TOD_DARES = [
    "Напиши повідомлення першому контакту в телефоні",
    "Зроби 10 присідань прямо зараз",
    "Напиши щось смішне на своїй сторінці",
    "Розкажи анекдот",
    "Проспівай будь-яку пісню",
]

@dp.callback_query(F.data.startswith("tod|"))
async def tod_callback(callback: types.CallbackQuery):
    parts = callback.data.split("|")
    _, choice, initiator_id, initiator_name = parts
    initiator_id = int(initiator_id)
    msg_id = callback.inline_message_id

    # Ініціатор не може обирати сам
    if callback.from_user.id == initiator_id:
        await callback.answer("🙃 Дай другу обрати!", show_alert=True)
        return

    responder_name = callback.from_user.first_name
    responder_id = callback.from_user.id

    if choice == "truth":
        task = random.choice(TOD_TRUTHS)
        task_type = "🗣 Правда"
    else:
        task = random.choice(TOD_DARES)
        task_type = "⚡ Дія"

    tod_games[msg_id] = {
        "initiator_id": initiator_id,
        "initiator_name": initiator_name,
        "responder_id": responder_id,
        "responder_name": responder_name,
        "task": task,
        "type": task_type
    }

    await bot.edit_message_text(
        inline_message_id=msg_id,
        text=(
            f"🎯 {responder_name} обрав(ла) {task_type}!\n\n"
            f"📋 Завдання:\n{task}\n\n"
            f"Очікуємо підтвердження від {initiator_name}..."
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Виконано!", callback_data=f"tod_done|done|{msg_id}"),
            InlineKeyboardButton(text="❌ Відмовився", callback_data=f"tod_done|fail|{msg_id}"),
        ]])
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("tod_done|"))
async def tod_done_callback(callback: types.CallbackQuery):
    parts = callback.data.split("|")
    _, result, msg_id = parts

    game = tod_games.get(msg_id)
    if not game:
        await callback.answer("Гра вже завершена!", show_alert=True)
        return

    # Тільки ініціатор може підтвердити
    if callback.from_user.id != game["initiator_id"]:
        await callback.answer("⛔ Тільки той хто запропонував може підтвердити!", show_alert=True)
        return

    if result == "done":
        update_balance(game["responder_id"], 15)
        await bot.edit_message_text(
            inline_message_id=msg_id,
            text=(
                f"🎯 Правда або Дія\n\n"
                f"{game['responder_name']} обрав(ла) {game['type']}\n"
                f"📋 {game['task']}\n\n"
                f"✅ {game['initiator_name']} підтвердив виконання!\n"
                f"+15 монет для {game['responder_name']} 🎉"
            )
        )
        await callback.answer("✅ Підтверджено!")
    else:
        await bot.edit_message_text(
            inline_message_id=msg_id,
            text=(
                f"🎯 Правда або Дія\n\n"
                f"{game['responder_name']} обрав(ла) {game['type']}\n"
                f"📋 {game['task']}\n\n"
                f"❌ {game['responder_name']} відмовився(лась) від завдання!"
            )
        )
        await callback.answer("❌ Відмову зафіксовано.")

    tod_games.pop(msg_id, None)

# ─── ЗАПУСК ──────────────────────────────────

async def main():
    init_db()
    await bot.set_chat_menu_button(menu_button=types.MenuButtonCommands())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
