"""Обработчики сообщений и команд."""

import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import config
from llm import generate_reply

log = logging.getLogger(__name__)
router = Router()

# Как в истории подписываются сообщения самого бота
BOT_LABEL = "Бот"
# Сообщения в истории обрезаем, чтобы запрос к LLM не раздувался
MAX_LINE_LENGTH = 500


@dataclass
class ChatState:
    """Всё, что бот помнит про один чат. Хранится в памяти, после перезапуска сбрасывается."""

    enabled: bool = True                      # включён ли бот в этом чате
    chance: float = config.REPLY_CHANCE       # вероятность спонтанного ответа
    history: deque = field(default_factory=lambda: deque(maxlen=config.HISTORY_SIZE))
    last_spontaneous: float = 0.0             # когда бот в последний раз влез сам
    busy: bool = False                        # идёт ли сейчас запрос к LLM


# Состояния всех чатов: chat_id -> ChatState
_states: dict[int, ChatState] = {}


def get_state(chat_id: int) -> ChatState:
    """Возвращает состояние чата, создаёт новое, если чат ещё не встречался."""
    if chat_id not in _states:
        _states[chat_id] = ChatState()
    return _states[chat_id]


async def is_admin(message: Message, bot: Bot) -> bool:
    """Проверяет, что команду прислал админ чата. В личке доступно всем."""
    if message.chat.type == "private":
        return True
    # Анонимный админ пишет от имени самого чата
    if message.sender_chat is not None and message.sender_chat.id == message.chat.id:
        return True
    if message.from_user is None:
        return False
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in ("creator", "administrator")


# ---------------------------------------------------------------------------
# Команды. Они должны быть выше общего обработчика сообщений: aiogram проверяет
# обработчики по порядку, и первый подошедший забирает сообщение.
# ---------------------------------------------------------------------------

@router.message(Command("on"))
async def cmd_on(message: Message, bot: Bot) -> None:
    if not await is_admin(message, bot):
        return
    get_state(message.chat.id).enabled = True
    await message.reply("Включён. Держитесь.")


@router.message(Command("off"))
async def cmd_off(message: Message, bot: Bot) -> None:
    if not await is_admin(message, bot):
        return
    get_state(message.chat.id).enabled = False
    await message.reply("Выключен. Молчу.")


@router.message(Command("chance"))
async def cmd_chance(message: Message, command: CommandObject, bot: Bot) -> None:
    if not await is_admin(message, bot):
        return
    arg = (command.args or "").strip().replace(",", ".")
    try:
        value = float(arg)
    except ValueError:
        await message.reply("Напиши число от 0 до 1, например: /chance 0.3")
        return
    if not 0.0 <= value <= 1.0:
        await message.reply("Число должно быть от 0 до 1, например: /chance 0.3")
        return
    get_state(message.chat.id).chance = value
    await message.reply(f"Вероятность ответа теперь {value}")


@router.message(Command("reset"))
async def cmd_reset(message: Message, bot: Bot) -> None:
    if not await is_admin(message, bot):
        return
    get_state(message.chat.id).history.clear()
    await message.reply("Историю чата забыл.")


# ---------------------------------------------------------------------------
# Общий обработчик: ловит все текстовые сообщения (и подписи к фото)
# ---------------------------------------------------------------------------

@router.message(F.text | F.caption)
async def on_message(message: Message, bot: Bot) -> None:
    user = message.from_user
    # Игнорируем сообщения без автора и от других ботов (в том числе от самого себя)
    if user is None or user.is_bot:
        return

    text = (message.text or message.caption or "").strip()
    # Пустые сообщения и команды (в том числе чужие) пропускаем
    if not text or text.startswith("/"):
        return

    state = get_state(message.chat.id)

    # Запоминаем сообщение в историю, даже если отвечать не будем
    name = user.first_name or user.username or "Аноним"
    state.history.append(f"{name}: {text[:MAX_LINE_LENGTH]}")

    if not state.enabled:
        return

    me = await bot.me()  # данные самого бота, aiogram кэширует результат

    # Бота упомянули по @юзернейму?
    mentioned = bool(me.username) and f"@{me.username}".lower() in text.lower()
    # Или ответили реплаем на его сообщение?
    reply_to = message.reply_to_message
    is_reply_to_bot = (
        reply_to is not None
        and reply_to.from_user is not None
        and reply_to.from_user.id == me.id
    )
    # В личке отвечаем всегда (удобно для проверки, что всё работает)
    direct = message.chat.type == "private" or mentioned or is_reply_to_bot

    if not direct:
        # Спонтанный ответ: бросаем кубик и проверяем паузу
        if random.random() >= state.chance:
            return
        if time.monotonic() - state.last_spontaneous < config.COOLDOWN_SECONDS:
            return

    # Если запрос к LLM уже идёт, не плодим второй
    if state.busy:
        return

    state.busy = True
    if not direct:
        # Засекаем паузу сразу, чтобы при ошибках бот не долбился в API
        state.last_spontaneous = time.monotonic()

    try:
        await bot.send_chat_action(message.chat.id, "typing")
        reply = await generate_reply(list(state.history), direct)
        if not reply:
            return

        if direct:
            await message.reply(reply)    # на обращения отвечаем реплаем
        else:
            await message.answer(reply)   # спонтанные реплики просто в чат

        # Запоминаем свою реплику, чтобы не повторяться
        state.history.append(f"{BOT_LABEL}: {reply[:MAX_LINE_LENGTH]}")
    except Exception:
        log.exception("Не удалось ответить в чате %s", message.chat.id)
    finally:
        state.busy = False
