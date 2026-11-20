"""Общение с LLM через OpenAI-совместимый API."""

import logging

from openai import AsyncOpenAI

import config
from prompts import SYSTEM_PROMPT

log = logging.getLogger(__name__)

# Один клиент на всю программу. base_url и ключ берутся из .env
_client = AsyncOpenAI(
    api_key=config.LLM_API_KEY,
    base_url=config.LLM_BASE_URL,
    timeout=config.LLM_TIMEOUT,
    max_retries=1,
)

# Максимальная длина сообщения в Telegram 4096 символов, берём с запасом
TELEGRAM_LIMIT = 4000


async def generate_reply(history_lines: list[str], direct: bool) -> str | None:
    """Просит модель написать реплику.

    history_lines - последние сообщения чата в виде строк "Имя: текст".
    direct - True, если к боту обратились напрямую (упомянули или ответили ему).
    Возвращает текст ответа или None, если что-то пошло не так.
    """
    chat_text = "\n".join(history_lines)

    if direct:
        task = (
            "К тебе обратились напрямую. Ответь на последнее сообщение "
            "в своём стиле, учитывая контекст чата."
        )
    else:
        task = (
            "Вставь свою реплику в разговор: подколи или прокомментируй "
            "последнее сообщение в своём стиле."
        )

    user_prompt = f"Последние сообщения в чате:\n{chat_text}\n\n{task}"

    try:
        response = await _client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=config.MAX_TOKENS,
            temperature=1.0,
        )
    except Exception:
        # Таймаут, неверный ключ, ошибка сервера: логируем и просто молчим
        log.exception("Ошибка при запросе к LLM")
        return None

    if not response.choices:
        log.warning("LLM вернула пустой список ответов")
        return None

    choice = response.choices[0]
    text = (choice.message.content or "").strip()
    if not text:
        log.warning(
            "LLM вернула пустой текст (finish_reason=%s). "
            "Если так часто, увеличь MAX_TOKENS в .env",
            choice.finish_reason,
        )
        return None

    # Иногда модель сама дописывает "Бот:" в начало, убираем
    for prefix in ("Бот:", "бот:"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    return text[:TELEGRAM_LIMIT] or None
