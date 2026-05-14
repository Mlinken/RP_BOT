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

# ─── FSM СТАНИ ───────────────────────────────

class AddAction(StatesGroup):
    waiting_for_type = State()   # чекаємо вибір типу
    waiting_for_data = State()   # чекаємо текст

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
    # Додаємо колонку illusion якщо її нема (для старих баз)
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

# ─── СТАНДАРТНІ ДІЇ ──────────────────────────

ACTIONS = {
    "h": {"name": "обійняти",   "emoji": "🤗", "past": "обійняв(ла)",     "prep": "", "thumb": "https://em-content.zobj.net/source/google/387/hugging-face_1f917.png"},
    "k": {"name": "поцілувати", "emoji": "💋", "past": "поцілував(ла)",   "prep": "в ", "thumb": "https://em-content.zobj.net/source/google/387/kiss-mark_1f48b.png"},
    "p": {"name": "вдарити",    "emoji": "👊", "past": "вдарив(ла)",      "prep": "в ", "thumb": "https://em-content.zobj.net/source/google/387/oncoming-fist_1f44a.png"},
    "s": {"name": "погладити",  "emoji": "🖐️", "past": "погладив(ла)",    "prep": "по ", "thumb": "https://em-content.zobj.net/source/google/387/raised-hand_270b.png"},
    "u": {"name": "обнятися",   "emoji": "🫂", "past": "обнявся(лась) з", "prep": "", "thumb": "https://em-content.zobj.net/source/google/387/people-hugging_1fac2.png"},
    "i": {"name": "трахнутись",   "emoji": "🔞", "past": "трахнув(ла)",     "prep": "", "thumb": "https://assets.wprock.fr/emoji/joypixels/512/1f51e.png"},
    "o": {"name": "потрогати",  "emoji": "🫴", "past": "потрогав(ла)",    "prep": "", "thumb": "https://images.emojiterra.com/microsoft/fluent-emoji/15.1/3d/1faf4_3d.png"},
    "f": {"name": "запустити",  "emoji": "🚀", "past": "запустив(ла)",    "prep": "", "thumb": "https://em-content.zobj.net/source/google/387/rocket_1f680.png", "illusion": True},
}

# ─── СТАРТ ──────────────────────────────────

@dp.message(Command("start"))
async def start(message: types.Message):
    ensure_user(message.from_user.id)
    await message.reply(
        "🇺🇦 Вітаю! Я український RP-бот.\n\n"
        "В будь-якому чаті напиши @ukrrp_Pero_bot і обери дію!\n\n"
        "─── Свої команди ───\n"
        "/add — додати команду\n"
        "/my — мої команди\n"
        "/delete — видалити команду\n"
        "/upgrade — купити +1 ліміт (100 монет)\n\n"
        "─── Економіка ───\n"
        "/balance — скільки монет\n"
        "/daily — щоденна нагорода\n\n"
        "─── Ігри ───\n"
        "/casino <ставка> — казино\n"
        "/roulette <ставка> — рулетка"
    )

# ─── ЩОДЕННА НАГОРОДА ────────────────────────

@dp.message(Command("daily"))
async def work(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id)
    user = get_user(user_id)
    today = str(date.today())

    if user["last_work"] == today:
        await message.reply("⏰ Ти вже отримав щоденну нагороду сьогодні!\nПоверніться завтра.")
        return

    update_balance(user_id, 10)
    set_last_work(user_id, today)
    new_bal = get_user(user_id)["balance"]
    await message.reply(
        f"✅ Щоденна нагорода!\n"
        f"+10 монет 💰\n"
        f"Баланс: {new_bal} монет"
    )

# ─── БАЛАНС ─────────────────────────────────

@dp.message(Command("balance"))
async def balance(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id)
    user = get_user(user_id)
    await message.reply(
        f"💰 Баланс: {user['balance']} монет\n"
        f"📋 Ліміт команд: {count_custom_actions(user_id)}/{user['limit']}\n"
        f"🔓 Розширити: /upgrade (100 монет)"
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
    if bet <= 0:
        await message.reply("❗ Ставка має бути більше 0!")
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
            f"{DICE_EMOJI[roll]} Випало {roll} — ти виграв!\n"
            f"+{bet} монет 🎉\n"
            f"Баланс: {new_bal} монет"
        )
    else:
        update_balance(user_id, -bet)
        new_bal = get_user(user_id)["balance"]
        await dice_msg.edit_text(
            f"{DICE_EMOJI[roll]} Випало {roll} — ти програв!\n"
            f"-{bet} монет 😔\n"
            f"Баланс: {new_bal} монет"
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
    if bet <= 0:
        await message.reply("❗ Ставка має бути більше 0!")
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
        f"🔴 Червоне / ⚫ Чорне — x2\n"
        f"🟢 Зелене (0) — x14",
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
            f"🎰 Кулька на {result_emoji} {number}!\n\n"
            f"{chosen_emoji[color]} {COLOR_NAMES[color]} — виграш!\n"
            f"+{winnings} монет 🎉\nБаланс: {new_bal} монет"
        )
    else:
        update_balance(owner_id, -bet)
        new_bal = get_user(owner_id)["balance"]
        await callback.message.edit_text(
            f"🎰 Кулька на {result_emoji} {number}!\n\n"
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
        await message.reply("✅ У тебе вже максимальний ліміт — 10 команд!")
        return
    if user["balance"] < 100:
        await message.reply(
            f"❌ Недостатньо монет!\n"
            f"Потрібно: 100 монет\n"
            f"У тебе: {user['balance']} монет"
        )
        return

    upgrade_limit(user_id)
    user = get_user(user_id)
    await message.reply(
        f"🔓 Ліміт розширено!\n"
        f"Тепер можеш додати до {user['limit']} команд\n"
        f"Баланс: {user['balance']} монет"
    )

# ─── ДОДАТИ КОМАНДУ (FSM) ────────────────────

@dp.message(Command("add"))
async def add_action_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    ensure_user(user_id)
    user = get_user(user_id)
    current = count_custom_actions(user_id)

    if current >= user["limit"]:
        await message.reply(
            f"❌ Досягнуто ліміт ({current}/{user['limit']})!\n"
            f"Купи розширення: /upgrade (100 монет)"
        )
        return

    await state.set_state(AddAction.waiting_for_type)
    await message.reply(
        "Який тип команди?\n\n"
        "🔀 З вибором — друг може прийняти або відхилити\n"
        "🎭 Ілюзія вибору — обидві кнопки погоджуються",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔀 З вибором",       callback_data="addtype|choice"),
            InlineKeyboardButton(text="🎭 Ілюзія вибору",   callback_data="addtype|illusion"),
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
        f"Тепер напиши команду у форматі:\n"
        f"назва|результат|емодзі\n\n"
        f"Приклад:\n"
        f"пограти|грає|🎮\n\n"
        f"Результат буде:\n"
        f"🎮 Іван пропонує пограти!\n"
        f"→ 🎮 Марія грає! ✅"
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
        await message.reply("❗ Назва і результат — до 20 символів!")
        return

    add_custom_action(user_id, name, past, emoji, illusion)
    await state.clear()

    user = get_user(user_id)
    type_text = "🎭 Ілюзія вибору" if illusion else "🔀 З вибором"
    await message.reply(
        f"✅ Команду додано!\n"
        f"{emoji} {name} → {past}\n"
        f"Тип: {type_text}\n\n"
        f"Використано: {count_custom_actions(user_id)}/{user['limit']}"
    )

# ─── МОЇ КОМАНДИ ────────────────────────────

@dp.message(Command("my"))
async def my_actions(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id)
    user = get_user(user_id)
    actions = list_custom_actions(user_id)

    if not actions:
        await message.reply("У тебе ще немає своїх команд.\nДодай: /add")
        return

    text = f"Твої команди ({len(actions)}/{user['limit']}):\n\n"
    for name, past, emoji, illusion in actions:
        type_icon = "🎭" if illusion else "🔀"
        text += f"{emoji} {name} → {past} {type_icon}\n"
    text += "\nВидалити: /delete назва"
    await message.reply(text)

# ─── ВИДАЛИТИ КОМАНДУ ────────────────────────

@dp.message(Command("delete"))
async def delete_action(message: types.Message):
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        actions = list_custom_actions(user_id)
        if not actions:
            await message.reply("У тебе немає команд для видалення.")
            return
        text = "Яку команду видалити?\n\n"
        for name, past, emoji, _ in actions:
            text += f"• /delete {name}\n"
        await message.reply(text)
        return

    name = parts[1].strip()
    if delete_custom_action(user_id, name):
        await message.reply(f"✅ Команду «{name}» видалено!")
    else:
        await message.reply(f"❌ Команду «{name}» не знайдено.")

# ─── INLINE QUERY ────────────────────────────

@dp.inline_query()
async def inline_query(query: types.InlineQuery):
    user = query.from_user
    short_name = user.first_name[:10]
    user_text = query.query.strip()
    all_actions = {**ACTIONS, **get_custom_actions(user.id)}
    results = []

    for code, data in all_actions.items():
        emoji = data["emoji"]
        action_name = data["name"]
        prep = data["prep"]
        is_illusion = data.get("illusion", False)
        is_custom = data.get("custom", False)
        thumb = data.get("thumb")

        if user_text:
            detail = user_text[:30]
            display_text = (
                f"{emoji} {user.first_name} пропонує {action_name} {prep}{detail}!"
                if is_illusion
                else f"{emoji} {user.first_name} хоче {action_name} {prep}{detail}!"
            )
            desc = f"{emoji} {action_name} {prep}{detail}"
        else:
            display_text = (
                f"{emoji} {user.first_name} пропонує {action_name}!"
                if is_illusion
                else f"{emoji} {user.first_name} хоче {action_name}!"
            )
            desc = "⭐ Своя команда" if is_custom else f"Наприклад: @бот {action_name} {prep}щось"

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
            id=code,
            title=f"{emoji} {action_name.capitalize()}{'  ⭐' if is_custom else ''}",
            description=desc,
            thumbnail_url=thumb,
            input_message_content=InputTextMessageContent(message_text=display_text),
            reply_markup=markup
        ))

    results.append(InlineQueryResultArticle(
        id="b",
        title="💰 Мій баланс",
        description="Показати скільки у вас монет",
        input_message_content=InputTextMessageContent(
            message_text=f"💰 Баланс {user.first_name}: {get_user(user.id)['balance']} монет"
        )
    ))

    await query.answer(results, cache_time=0, is_personal=False)

# ─── CHOSEN INLINE RESULT ────────────────────

@dp.chosen_inline_result()
async def chosen_inline(result: types.ChosenInlineResult):
    if result.inline_message_id and result.query.strip():
        pending_details[result.inline_message_id] = result.query.strip()[:30]

# ─── ОБРОБКА RP КНОПОК ───────────────────────

@dp.callback_query(F.data.startswith("rp|"))
async def rp_callback(callback: types.CallbackQuery):
    parts = callback.data.split("|")
    _, result, code, initiator_id, initiator_name, target_id = parts
    initiator_id = int(initiator_id)
    target_id_int = int(target_id)

    if callback.from_user.id == initiator_id:
        await callback.answer("🙃 Ти не можеш відповісти на власний запит!", show_alert=True)
        return
    if target_id_int != 0 and callback.from_user.id != target_id_int:
        await callback.answer("⛔ Ця дія адресована іншій людині!", show_alert=True)
        return

    data = ACTIONS.get(code)
    if not data:
        conn = sqlite3.connect("bot.db")
        c = conn.cursor()
        c.execute("SELECT name, past, emoji, illusion FROM custom_actions WHERE code = ?", (code,))
        row = c.fetchone()
        conn.close()
        data = {"name": row[0], "past": row[1], "emoji": row[2], "prep": "", "illusion": bool(row[3])} if row else {"emoji": "✨", "past": code, "name": code, "prep": ""}

    emoji = data["emoji"]
    past = data["past"]
    prep = data["prep"]
    responder_name = callback.from_user.first_name
    detail = pending_details.get(callback.inline_message_id, "")
    detail_text = f" {prep}{detail}" if detail else ""

    if result == "a":
        await bot.edit_message_text(
            inline_message_id=callback.inline_message_id,
            text=f"{emoji} {responder_name} {past}{detail_text}! ✅"
        )
        await callback.answer("✅ Прийнято!")
        pending_details.pop(callback.inline_message_id, None)
    elif result == "d":
        await bot.edit_message_text(
            inline_message_id=callback.inline_message_id,
            text=f"😔 {responder_name} відхилив(ла) пропозицію від {initiator_name}. ❌"
        )
        await callback.answer("Ти відхилив(ла).")
        pending_details.pop(callback.inline_message_id, None)

# ─── ЗАПУСК ──────────────────────────────────

async def main():
    init_db()
    await bot.set_chat_menu_button(menu_button=types.MenuButtonCommands())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
