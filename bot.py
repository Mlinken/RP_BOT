import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQueryResultArticle, InputTextMessageContent
)

TOKEN = "8587796773:AAHuFhOdn4UWATLSHS3k1eGdolw2VhfIpLo"

bot = Bot(token=TOKEN)
dp = Dispatcher()

balances = {}

# Зберігаємо уточнення: { "inline_message_id": "в губи" }
pending_details = {}

ACTIONS = {
    "h": {"name": "обійняти",   "emoji": "🤗", "past": "обійняв(ла)",     "prep": ""},
    "k": {"name": "поцілувати", "emoji": "💋", "past": "поцілував(ла)",   "prep": "в "},
    "p": {"name": "вдарити",    "emoji": "👊", "past": "вдарив(ла)",      "prep": "в "},
    "s": {"name": "погладити",  "emoji": "🖐️", "past": "погладив(ла)",    "prep": "по "},
    "u": {"name": "обнятися",   "emoji": "🫂", "past": "обнявся(лась) з", "prep": ""},
    "i": {"name": "трахнути",   "emoji": "🔞", "past": "трахнув(ла)",     "prep": ""}
}

# ─── СТАРТ ──────────────────────────────────

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.reply(
        "🇺🇦 Вітаю! Я український RP-бот.\n\n"
        "В будь-якому чаті напиши @ukrrp_Pero_bot і обери дію з меню!\n\n"
        "💡 Можна додати уточнення:\n"
        "@ukrrp_Pero_bot в губи → обираєш поцілувати"
    )

# ─── INLINE QUERY ────────────────────────────

@dp.inline_query()
async def inline_query(query: types.InlineQuery):
    user = query.from_user
    short_name = user.first_name[:10]
    user_text = query.query.strip()

    results = []

    for code, data in ACTIONS.items():
        emoji = data["emoji"]
        action_name = data["name"]
        prep = data["prep"]

        if user_text:
            detail = user_text[:30]
            display_text = f"{emoji} {user.first_name} хоче {action_name} {prep}{detail}!"
            desc = f"{emoji} {action_name} {prep}{detail}"
        else:
            display_text = f"{emoji} {user.first_name} хоче {action_name}!"
            desc = f"Наприклад: @бот {action_name} {prep}в щоку"

        results.append(
            InlineQueryResultArticle(
                id=code,
                title=f"{emoji} {action_name.capitalize()}",
                description=desc,
                input_message_content=InputTextMessageContent(
                    message_text=display_text
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Прийняти",
                            callback_data=f"rp|a|{code}|{user.id}|{short_name}|0"
                        ),
                        InlineKeyboardButton(
                            text="❌ Відхилити",
                            callback_data=f"rp|d|{code}|{user.id}|{short_name}|0"
                        )
                    ]
                ])
            )
        )

    results.append(
        InlineQueryResultArticle(
            id="b",
            title="💰 Мій баланс",
            description="Показати скільки у вас монет",
            input_message_content=InputTextMessageContent(
                message_text=f"💰 Баланс {user.first_name}: {balances.get(user.id, 0)} монет"
            )
        )
    )

    await query.answer(results, cache_time=0, is_personal=True)

# ─── CHOSEN INLINE RESULT — зберігаємо уточнення ───

@dp.chosen_inline_result()
async def chosen_inline(result: types.ChosenInlineResult):
    if result.inline_message_id and result.query.strip():
        # Зберігаємо уточнення прив'язане до повідомлення
        pending_details[result.inline_message_id] = result.query.strip()[:30]

# ─── ОБРОБКА КНОПОК ─────────────────────────

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

    data = ACTIONS.get(code, {"emoji": "✨", "past": code, "name": code, "prep": ""})
    emoji = data["emoji"]
    past = data["past"]
    prep = data["prep"]
    responder_name = callback.from_user.first_name

    # Дістаємо збережене уточнення
    detail = pending_details.get(callback.inline_message_id, "")
    detail_text = f" {prep}{detail}" if detail else ""

    if result == "a":
        await bot.edit_message_text(
            inline_message_id=callback.inline_message_id,
            text=f"{emoji} {initiator_name} {past} {responder_name}{detail_text}!"
        )
        await callback.answer("Ти прийняв(ла)! 🎉")
        # Видаляємо з пам'яті після використання
        pending_details.pop(callback.inline_message_id, None)

    elif result == "d":
        await bot.edit_message_text(
            inline_message_id=callback.inline_message_id,
            text=f"😔 {responder_name} відхилив(ла) пропозицію від {initiator_name}. ❌"
        )
        await callback.answer("Ти відхилив(ла).")
        pending_details.pop(callback.inline_message_id, None)

# ─── БАЛАНС / РОБОТА ─────────────────────────

@dp.message(Command("баланс"))
async def balance(message: types.Message):
    user_id = message.from_user.id
    if user_id not in balances:
        balances[user_id] = 0
    await message.reply(f"💰 Ваш баланс: {balances[user_id]} монет")

@dp.message(Command("працювати"))
async def work(message: types.Message):
    user_id = message.from_user.id
    if user_id not in balances:
        balances[user_id] = 0
    balances[user_id] += 50
    await message.reply("💼 Ви попрацювали та отримали 50 монет!")

# ─── ЗАПУСК ──────────────────────────────────

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
