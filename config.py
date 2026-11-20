"""Настройки бота. Всё берётся из переменных окружения (файл .env)."""

import os

from dotenv import load_dotenv

# Читаем файл .env (если он лежит рядом) и кладём значения в переменные окружения
load_dotenv()


def _require(name: str) -> str:
    """Обязательная переменная: если её нет, бот не запустится и скажет почему."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Не задана переменная окружения {name}. Заполни её в файле .env"
        )
    return value


def _get_float(name: str, default: float) -> float:
    """Необязательное число с запятой. Если пусто, берём значение по умолчанию."""
    raw = os.getenv(name, "").strip().replace(",", ".")
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise RuntimeError(f"Переменная {name} должна быть числом, а там: {raw!r}")


def _get_int(name: str, default: int) -> int:
    """Необязательное целое число."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"Переменная {name} должна быть целым числом, а там: {raw!r}")


# --- Секреты и доступ к LLM (обязательные) ---
BOT_TOKEN = _require("BOT_TOKEN")        # токен бота от @BotFather
LLM_API_KEY = _require("LLM_API_KEY")    # ключ от LLM API
LLM_BASE_URL = _require("LLM_BASE_URL")  # адрес API (Base URL) от продавца или провайдера
LLM_MODEL = _require("LLM_MODEL")        # имя модели, как его просит API

# --- Поведение бота (необязательные) ---
# Вероятность спонтанного ответа на обычное сообщение (0.15 = 15%)
REPLY_CHANCE = min(1.0, max(0.0, _get_float("REPLY_CHANCE", 0.15)))
# Минимальная пауза между двумя спонтанными ответами в одном чате, секунды
COOLDOWN_SECONDS = _get_int("COOLDOWN_SECONDS", 20)
# Сколько последних сообщений чата помнит бот
HISTORY_SIZE = max(1, _get_int("HISTORY_SIZE", 20))
# Таймаут запроса к LLM, секунды
LLM_TIMEOUT = _get_int("LLM_TIMEOUT", 30)
# Максимум токенов в ответе. Если модель "думает" перед ответом, часть токенов уходит на это,
# поэтому значение с запасом. Если ответы приходят пустыми, увеличь число.
MAX_TOKENS = _get_int("MAX_TOKENS", 300)
