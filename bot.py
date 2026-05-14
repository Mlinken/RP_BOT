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
    "i": {"name": "трахнути",   "emoji": "🔞", "past": "трахнув(ла)",     "prep": ""},
    "o": {"name": "потрогати",  "emoji": "🫴", "past": "потрогав(ла)",    "prep": ""},
    "f": {"name": "запустити",  "emoji": "🚀", "past": "запустив(ла)",    "prep": "", "illusion": True},
}

# ─── СТАРТ ──────────────────────────────────

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
        is_illusion = data.get("illusion", False)

        if user_text:
            detail = user_text[:30]
            display_text = f"{emoji} {user.first_name} пропонує вам {action_name} {prep}{detail}!" if is_illusion else f"{emoji} {user.first_name} хоче {action_name} {prep}{detail}!"
            desc = f"{emoji} {action_name} {prep}{detail}"
        else:
            display_text = f"{emoji} {user.first_name} пропонує вам {action_name}!" if is_illusion else f"{emoji} {user.first_name} хоче {action_name}!"
            desc = f"Наприклад: @бот {action_name} {prep}щось"

        if is_illusion:
            # Обидві кнопки погоджувальні
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Погодитись",
                        callback_data=f"rp|a|{code}|{user.id}|{short_name}|0"
                    ),
                    InlineKeyboardButton(
                        text="☑️ Звісно",
                        callback_data=f"rp|a|{code}|{user.id}|{short_name}|0"
                    )
                ]
            ])
        else:
            markup = InlineKeyboardMarkup(inline_keyboard=[
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

        results.append(
            InlineQueryResultArticle(
                id=code,
                title=f"{emoji} {action_name.capitalize()}",
                description=desc,
                input_message_content=InputTextMessageContent(
                    message_text=display_text
                ),
                reply_markup=markup
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


@dp.callback_query(F.data.startswith("rp|"))
async def rp_callback(callback: types.CallbackQuery):
    parts = callback.data.split("|")
    _, result, code, initiator_id, initiator_name, target_id = parts

    initiator_id = int(initiator_id)
    target_id_int = int(target_id)
    is_illusion = ACTIONS.get(code, {}).get("illusion", False)

    # Для ілюзії вибору — ініціатор не може натискати сам на себе
    if callback.from_user.id == initiator_id:
        await callback.answer("🙃 Ти не можеш відповісти на власний запит!", show_alert=True)
        return

    if not is_illusion and target_id_int != 0 and callback.from_user.id != target_id_int:
        await callback.answer("⛔ Ця дія адресована іншій людині!", show_alert=True)
        return

    data = ACTIONS.get(code, {"emoji": "✨", "past": code, "name": code, "prep": ""})
    emoji = data["emoji"]
    past = data["past"]
    prep = data["prep"]
    responder_name = callback.from_user.first_name

    # Дістаємо уточнення з тексту повідомлення
    detail_text = ""
    if callback.message:
        msg_text = callback.message.text
        action_name = data["name"]
        trigger = f"{action_name} {prep}" if prep else f"{action_name} "
        if trigger in msg_text:
            after = msg_text.split(trigger)[-1].rstrip("!")
            if after:
                detail_text = f" {prep}{after}" if prep else f" {after}"

    if result == "a":
        await bot.edit_message_text(
            inline_message_id=callback.inline_message_id,
            text=f"{emoji} {responder_name} {past}{detail_text}! ✅"
        )
        await callback.answer("✅ Прийнято!")

    elif result == "d":
        await bot.edit_message_text(
            inline_message_id=callback.inline_message_id,
            text=f"😔 {responder_name} відхилив(ла) пропозицію від {initiator_name}. ❌"
        )
        await callback.answer("Ти відхилив(ла).")
