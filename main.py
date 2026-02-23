import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import time
import asyncio
import yaml
import logging
import traceback
import re

# ==================== логирование ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== загрузка конфига ====================

try:
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    logger.info("Config loaded successfully")
except Exception as e:
    logger.critical(f"Failed to load config: {e}")
    exit(1)

BOT_TOKEN       = config["bot"]["token"]
PREFIX          = config["bot"]["prefix"]

GUILD_ID        = config["guild"]["id"]
CHANNEL_ID      = config["channels"]["anonymous_messages"]
WIZARD_CHANNEL  = config["channels"]["wizard_channel"]

STAFF_ROLE_ID   = config["roles"]["prison_staff"]
PRISONER_ROLE   = config["roles"]["prisoner"]

COOLDOWN        = config["cooldowns"]["send_seconds"]
COLORS          = config["embed_colors"]
MSGS            = config["messages"]
CMD             = config["commands"]
WIZARD          = config["wizard"]

# ==========================================================

user_cooldowns: dict[int, float] = {}
active_effect: str | None = None
effect_end_time: float = 0
webhook_cache: dict[int, discord.Webhook] = {}

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


# ==================== утилиты ====================

def is_cyrillic(char: str) -> bool:
    """Проверяет, является ли символ кириллицей"""
    return bool(re.match(r'[а-яА-ЯёЁіІїЇєЄґҐ]', char))

def is_letter(char: str) -> bool:
    """Проверяет, является ли символ буквой (латиница или кириллица)"""
    return char.isalpha()


# ==================== утилиты эффектов ====================

def reverse_text(text: str) -> str:
    """Текст задом наперёд"""
    return text[::-1]

def shuffle_words(text: str) -> str:
    """Перемешивает слова"""
    words = text.split()
    random.shuffle(words)
    return " ".join(words)

def stutter_text(text: str) -> str:
    """З-заикание для русского и английского"""
    words = text.split()
    result = []
    for word in words:
        if len(word) > 1 and is_letter(word[0]):
            result.append(f"{word[0]}-{word}")
        else:
            result.append(word)
    return " ".join(result)

def censor_text(text: str) -> str:
    """Цензура случайных слов"""
    words = text.split()
    result = []
    for word in words:
        if random.random() < 0.35 and len(word) > 2:
            result.append("█" * len(word))
        else:
            result.append(word)
    return " ".join(result)

def mock_text(text: str) -> str:
    """СаРкАзМ тЕкСт - работает с любым алфавитом"""
    result = []
    upper = False
    for char in text:
        if is_letter(char):
            result.append(char.upper() if upper else char.lower())
            upper = not upper
        else:
            result.append(char)
    return "".join(result)

def uwu_text(text: str) -> str:
    """UwU фикация для русского и английского"""
    # Английские замены
    text = text.replace("r", "w").replace("R", "W")
    text = text.replace("l", "w").replace("L", "W")
    text = text.replace("th", "d").replace("Th", "D").replace("TH", "D")
    
    # Русские замены
    text = text.replace("р", "в").replace("Р", "В")
    text = text.replace("л", "в").replace("Л", "В")
    text = text.replace("ш", "с").replace("Ш", "С")
    text = text.replace("щ", "с").replace("Щ", "С")
    text = text.replace("ж", "з").replace("Ж", "З")
    
    uwu_faces = ["UwU", "OwO", ">w<", "^w^", "~w~", ":3", "x3", "нян~", "ня~"]
    if random.random() < 0.3:
        text = f"{random.choice(uwu_faces)} {text}"
    if random.random() < 0.3:
        text = f"{text} {random.choice(uwu_faces)}"
    
    return text

def leetspeak_text(text: str) -> str:
    """1337 5p34k для русского и английского"""
    leet_map = {
        # Английские
        'a': '4', 'A': '4', 'e': '3', 'E': '3', 'i': '1', 'I': '1',
        'o': '0', 'O': '0', 's': '5', 'S': '5', 't': '7', 'T': '7',
        'b': '8', 'B': '8', 'g': '9', 'G': '9',
        # Русские
        'а': '4', 'А': '4', 'е': '3', 'Е': '3', 'ё': '3', 'Ё': '3',
        'о': '0', 'О': '0', 'з': '3', 'З': '3', 'ч': '4', 'Ч': '4',
        'б': '6', 'Б': '6', 'в': '8', 'В': '8', 'т': '7', 'Т': '7',
        'и': '1', 'И': '1', 'й': '1', 'Й': '1', 'л': '7', 'Л': '7',
    }
    return "".join(leet_map.get(c, c) for c in text)

def drunk_text(text: str) -> str:
    """Пьяный текст"""
    result = []
    for char in text:
        result.append(char)
        if is_letter(char) and random.random() < 0.15:
            result.append(char * random.randint(1, 3))
        if random.random() < 0.05:
            result.append(random.choice(['...', ' *ик*', ' *хик*', ' ', '', ' ыыы']))
    
    drunk_endings = [" *ик*", " *хик*", "...", " ззз", " *бурп*", " хехе", ""]
    return "".join(result) + random.choice(drunk_endings)

def spoiler_text(text: str) -> str:
    """||Каждое|| ||слово|| ||спойлер||"""
    words = text.split()
    return " ".join(f"||{word}||" for word in words)

def clap_text(text: str) -> str:
    """Каждое 👏 слово 👏 с 👏 хлопком"""
    words = text.split()
    return " 👏 ".join(words) + " 👏"

def echo_text(text: str) -> str:
    """Эхо эхо хо о..."""
    words = text.split()
    if len(words) < 1:
        return text
    
    last_word = words[-1]
    if len(last_word) < 3:
        return text + "... " + last_word + "..."
    
    echo_parts = []
    for i in range(min(3, len(last_word) - 1)):
        start = max(1, len(last_word) - 2 - i)
        part = last_word[start:].lower()
        if part:
            echo_parts.append(part)
    
    if echo_parts:
        return text + "... " + "... ".join(echo_parts) + "..."
    return text + "..."

def dramatic_text(text: str) -> str:
    """Драматичные... паузы... везде..."""
    words = text.split()
    result = []
    for i, word in enumerate(words):
        result.append(word)
        if random.random() < 0.4 or i == len(words) - 1:
            result.append("...")
    return " ".join(result)

def glitch_text(text: str) -> str:
    """З̷а̸л̵г̶о̷ текст"""
    zalgo_chars = [
        '\u0300', '\u0301', '\u0302', '\u0303', '\u0304', '\u0305', '\u0306', '\u0307',
        '\u0308', '\u0309', '\u030A', '\u030B', '\u030C', '\u030D', '\u030E', '\u030F',
        '\u0310', '\u0311', '\u0312', '\u0313', '\u0314', '\u0315', '\u031A', '\u031B',
        '\u033D', '\u033E', '\u033F', '\u0340', '\u0341', '\u0342', '\u0343', '\u0344',
        '\u0346', '\u034A', '\u034B', '\u034C', '\u0350', '\u0351', '\u0352', '\u0357',
    ]
    result = []
    for char in text:
        result.append(char)
        if is_letter(char):
            for _ in range(random.randint(1, 3)):
                result.append(random.choice(zalgo_chars))
    return "".join(result)

def snake_text(text: str) -> str:
    """Шшшипение сссловами - русский и английский"""
    result = []
    for word in text.split():
        if not word:
            continue
        first = word[0].lower()
        # Английские шипящие
        if first == 's':
            word = 'sss' + word[1:]
        elif first in 'cz':
            word = word[0] + 'ss' + word[1:]
        # Русские шипящие
        elif first == 'с':
            word = 'ссс' + word[1:]
        elif first == 'ш':
            word = 'шшш' + word[1:]
        elif first == 'щ':
            word = 'щщщ' + word[1:]
        elif first == 'ж':
            word = 'жжж' + word[1:]
        elif first == 'з':
            word = 'ззз' + word[1:]
        elif first == 'ч':
            word = 'ччч' + word[1:]
        
        if random.random() < 0.2:
            # Добавляем шипение в конец
            if any(c in word.lower() for c in 'сшщзж'):
                word = word + "ссс"
            elif any(c in word.lower() for c in 'szc'):
                word = word + "sss"
        result.append(word)
    return " ".join(result)

def backwards_words_text(text: str) -> str:
    """Каждое слово задом наперёд"""
    words = text.split()
    return " ".join(word[::-1] for word in words)

def tiny_text(text: str) -> str:
    """Маленькие буквы (надстрочные)"""
    tiny_map = {
        # Латиница
        'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ', 'f': 'ᶠ', 'g': 'ᵍ',
        'h': 'ʰ', 'i': 'ⁱ', 'j': 'ʲ', 'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ', 'n': 'ⁿ',
        'o': 'ᵒ', 'p': 'ᵖ', 'q': 'q', 'r': 'ʳ', 's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ',
        'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ',
        'A': 'ᴬ', 'B': 'ᴮ', 'C': 'ᶜ', 'D': 'ᴰ', 'E': 'ᴱ', 'F': 'ᶠ', 'G': 'ᴳ',
        'H': 'ᴴ', 'I': 'ᴵ', 'J': 'ᴶ', 'K': 'ᴷ', 'L': 'ᴸ', 'M': 'ᴹ', 'N': 'ᴺ',
        'O': 'ᴼ', 'P': 'ᴾ', 'Q': 'Q', 'R': 'ᴿ', 'S': 'ˢ', 'T': 'ᵀ', 'U': 'ᵁ',
        'V': 'ⱽ', 'W': 'ᵂ', 'X': 'ˣ', 'Y': 'ʸ', 'Z': 'ᶻ',
        # Кириллица (используем похожие символы где возможно)
        'а': 'ᵃ', 'б': 'ᵇ', 'в': 'ᵛ', 'г': 'ᵍ', 'д': 'ᵈ', 'е': 'ᵉ', 'ё': 'ᵉ',
        'ж': 'ж', 'з': 'ᶻ', 'и': 'ⁱ', 'й': 'ⁱ', 'к': 'ᵏ', 'л': 'ˡ', 'м': 'ᵐ',
        'н': 'ⁿ', 'о': 'ᵒ', 'п': 'ᵖ', 'р': 'ʳ', 'с': 'ᶜ', 'т': 'ᵗ', 'у': 'ʸ',
        'ф': 'ᶠ', 'х': 'ˣ', 'ц': 'ᶜ', 'ч': 'ᶜ', 'ш': 'ш', 'щ': 'щ', 'ъ': 'ъ',
        'ы': 'ʸ', 'ь': 'ь', 'э': 'ᵉ', 'ю': 'ю', 'я': 'ʸ',
        'А': 'ᴬ', 'Б': 'ᴮ', 'В': 'ⱽ', 'Г': 'ᴳ', 'Д': 'ᴰ', 'Е': 'ᴱ', 'Ё': 'ᴱ',
        'Ж': 'Ж', 'З': 'ᶻ', 'И': 'ᴵ', 'Й': 'ᴵ', 'К': 'ᴷ', 'Л': 'ᴸ', 'М': 'ᴹ',
        'Н': 'ᴺ', 'О': 'ᴼ', 'П': 'ᴾ', 'Р': 'ᴿ', 'С': 'ᶜ', 'Т': 'ᵀ', 'У': 'ʸ',
        'Ф': 'ᶠ', 'Х': 'ˣ', 'Ц': 'ᶜ', 'Ч': 'ᶜ', 'Ш': 'Ш', 'Щ': 'Щ', 'Ъ': 'Ъ',
        'Ы': 'ʸ', 'Ь': 'Ь', 'Э': 'ᴱ', 'Ю': 'Ю', 'Я': 'ʸ',
    }
    return "".join(tiny_map.get(c, c) for c in text)

def yell_text(text: str) -> str:
    """КРИК!!! С ВОСКЛИЦАНИЯМИ!!!"""
    text = text.upper()
    words = text.split()
    result = []
    for word in words:
        exclamations = "!" * random.randint(1, 3)
        result.append(word + exclamations)
    return " ".join(result)

def confused_text(text: str) -> str:
    """Путаница в буквах"""
    result = []
    for word in text.split():
        new_word = list(word)
        # Дублируем случайные буквы
        for i in range(len(new_word)):
            if is_letter(new_word[i]) and random.random() < 0.2:
                new_word[i] = new_word[i] * 2
        # Меняем местами случайные буквы
        if len(new_word) > 3 and random.random() < 0.3:
            indices = [j for j in range(len(new_word)) if is_letter(new_word[j])]
            if len(indices) >= 2:
                i, j = random.sample(indices, 2)
                new_word[i], new_word[j] = new_word[j], new_word[i]
        result.append("".join(new_word))
    
    return " ".join(result) + "???"

def pirate_text(text: str) -> str:
    """Пиратский говор - русский и английский"""
    # Определяем язык по первым буквам
    has_cyrillic = any(is_cyrillic(c) for c in text)
    
    if has_cyrillic:
        # Русский пиратский
        replacements = {
            "привет": "йо-хо-хо", "здравствуй": "йо-хо-хо", "здравствуйте": "йо-хо-хо",
            "да": "так точно, капитан", "нет": "никак нет", "хорошо": "добре",
            "друг": "морской волк", "друзья": "морские волки", "деньги": "дублоны",
            "человек": "морской пёс", "люди": "морские псы", "ты": "ты, каналья",
            "я": "йа, пират", "мы": "мы, пираты", "мой": "мой пиратский",
            "пойдём": "отдать швартовы", "идём": "полный вперёд",
        }
        pirate_starts = ["Йо-хо-хо!", "Тысяча чертей!", "Разрази меня гром!", "Карамба!", "Пиастры!"]
        pirate_ends = [", тысяча чертей!", ", морской волк!", ", каналья!", ", йо-хо-хо!", ""]
    else:
        # Английский пиратский
        replacements = {
            "my": "me", "you": "ye", "your": "yer", "is": "be", "are": "be",
            "hello": "ahoy", "hi": "ahoy", "friend": "matey", "friends": "mateys",
            "man": "landlubber", "money": "doubloons", "treasure": "booty",
            "yes": "aye", "no": "nay", "the": "th'",
        }
        pirate_starts = ["Arr!", "Yarr!", "Ahoy!", "Avast!", "Shiver me timbers!"]
        pirate_ends = [", matey!", ", arr!", ", ye scallywag!", ""]
    
    words = text.lower().split()
    result = [replacements.get(w, w) for w in words]
    
    return f"{random.choice(pirate_starts)} {' '.join(result)}{random.choice(pirate_ends)}"

def robot_text(text: str) -> str:
    """BEEP. BOOP. ROBOT. SPEAK."""
    # Определяем язык
    has_cyrillic = any(is_cyrillic(c) for c in text)
    
    words = text.upper().split()
    result = ". ".join(words) + "."
    
    if has_cyrillic:
        robot_prefixes = ["БИП БУП.", "[ОБРАБОТКА]", "[ПЕРЕДАЧА]", "01100010:", "[РОБОТ]"]
    else:
        robot_prefixes = ["BEEP BOOP.", "[PROCESSING]", "[TRANSMISSION]", "01100010:", "[ROBOT]"]
    
    return f"{random.choice(robot_prefixes)} {result}"

def medieval_text(text: str) -> str:
    """Старинный стиль - русский и английский"""
    has_cyrillic = any(is_cyrillic(c) for c in text)
    
    if has_cyrillic:
        # Старославянский стиль
        replacements = {
            "ты": "ты, сударь", "вы": "вы, милостивый государь",
            "я": "аз", "мы": "мы, грешные",
            "есть": "есьм", "быть": "быти",
            "говорить": "молвити", "сказать": "рекоша",
            "хорошо": "зело добре", "плохо": "худо",
            "да": "истинно", "нет": "несть",
            "привет": "здравия желаю", "пока": "прощевай",
            "друг": "друже", "человек": "человече",
            "что": "чаво", "как": "како",
        }
        medieval_starts = ["Внемлите!", "Слушайте же!", "Азъ реку:", "Истинно глаголю:", "Вот те крест!"]
        medieval_ends = [", сударь.", ", батюшка.", ", истинно.", ""]
    else:
        replacements = {
            "you": "thee", "your": "thy", "yours": "thine",
            "are": "art", "is": "be", "have": "hast", "has": "hath",
            "will": "shall", "do": "doth", "hello": "hail",
            "hi": "greetings", "good": "most wondrous",
        }
        medieval_starts = ["Hark!", "Hear ye!", "Prithee,", "Forsooth,", "Verily,"]
        medieval_ends = [", m'lord.", ", good sir.", ", I say!", ""]
    
    words = text.lower().split()
    result = [replacements.get(w, w) for w in words]
    
    return f"{random.choice(medieval_starts)} {' '.join(result)}{random.choice(medieval_ends)}"

def sarcasm_quotes_text(text: str) -> str:
    """"Конечно" ты "очень" "умный\""""
    words = text.split()
    result = []
    for word in words:
        if len(word) > 2 and random.random() < 0.35:
            result.append(f'"{word}"')
        else:
            result.append(word)
    return " ".join(result)

def void_text(text: str) -> str:
    """р а з р я д к а"""
    spaced = " ".join(text)
    void_symbols = [".", "·", "•", "。", "॰", "᛫"]
    symbol = random.choice(void_symbols)
    return f"{symbol}  {spaced}  {symbol}"

def hacker_text(text: str) -> str:
    """[SYSTEM]: Message intercepted..."""
    has_cyrillic = any(is_cyrillic(c) for c in text)
    
    if has_cyrillic:
        hacker_prefixes = [
            "[ПЕРЕХВАЧЕНО]:", "[РАСШИФРОВАНО]:", "[ВЗЛОМ СИСТЕМЫ]:",
            "[УТЕЧКА ДАННЫХ]:", "[СЛЕЖКА]:", ">>> ВЫВОД:",
        ]
    else:
        hacker_prefixes = [
            "[INTERCEPTED]:", "[DECRYPTED]:", "[SYSTEM BREACH]:",
            "[DATA LEAK]:", "[TRACE DETECTED]:", ">>> STDOUT:",
        ]
    
    glitched = leetspeak_text(text)
    return f"```\n{random.choice(hacker_prefixes)} {glitched}\n```"

def musical_text(text: str) -> str:
    """🎵 Каждое слово как песня 🎶"""
    notes = ["🎵", "🎶", "🎼", "🎤", "🎸", "🎹", "🎺", "🎻", "🥁", "🪘", "🎧", "🎷"]
    words = text.split()
    result = []
    for word in words:
        result.append(f"{random.choice(notes)} {word}")
    return " ".join(result) + f" {random.choice(notes)}"

def explosion_text(text: str) -> str:
    """💥 BOOM 💥 эффекты везде"""
    explosions = ["💥", "🔥", "✨", "⚡", "🌟", "💫", "☄️", "🎆", "🎇", "💣", "🧨"]
    text = text.upper()
    words = text.split()
    result = []
    for word in words:
        result.append(f"{random.choice(explosions)} {word}")
    return " ".join(result) + f" {random.choice(explosions)}"

def baby_text(text: str) -> str:
    """Детский лепет - агу агу"""
    has_cyrillic = any(is_cyrillic(c) for c in text)
    
    if has_cyrillic:
        # Русский детский
        text = text.replace("р", "л").replace("Р", "Л")
        text = text.replace("ш", "с").replace("Ш", "С")
        text = text.replace("ж", "з").replace("Ж", "З")
        text = text.replace("щ", "с").replace("Щ", "С")
        baby_words = ["агу", "ня", "мама", "дай", "хочу", "ааа"]
    else:
        text = text.replace("r", "w").replace("R", "W")
        text = text.replace("l", "w").replace("L", "W")
        baby_words = ["goo goo", "ga ga", "mama", "dada", "waah"]
    
    if random.random() < 0.3:
        text = f"{random.choice(baby_words)}! {text}"
    if random.random() < 0.3:
        text = f"{text} {random.choice(baby_words)}!"
    
    return text

def owoify_text(text: str) -> str:
    """OwO что это? - более агрессивный uwu"""
    has_cyrillic = any(is_cyrillic(c) for c in text)
    
    if has_cyrillic:
        text = text.replace("р", "в").replace("Р", "В")
        text = text.replace("л", "в").replace("Л", "В")
        text = text.replace("ш", "ф").replace("Ш", "Ф")
        text = text.replace("щ", "ф").replace("Щ", "Ф")
        text = text.replace("ж", "ш").replace("Ж", "Ш")
        text = text.replace("на", "ня").replace("На", "Ня")
        text = text.replace("ни", "ни~").replace("Ни", "Ни~")
        faces = ["OwO", "UwU", ">w<", "^w^", "ня~", "нян!", ":3", "(✿◠‿◠)"]
    else:
        text = text.replace("r", "w").replace("R", "W")
        text = text.replace("l", "w").replace("L", "W")
        text = text.replace("na", "nya").replace("Na", "Nya")
        text = text.replace("ni", "nyi").replace("Ni", "Nyi")
        text = text.replace("no", "nyo").replace("No", "Nyo")
        faces = ["OwO", "UwU", ">w<", "^w^", "~w~", ":3", "(✿◠‿◠)", "nyaa~"]
    
    # Добавляем случайные лица
    words = text.split()
    result = []
    for word in words:
        result.append(word)
        if random.random() < 0.15:
            result.append(random.choice(faces))
    
    return " ".join(result)

def angry_text(text: str) -> str:
    """ЗЛОЙ ТЕКСТ 😡"""
    text = text.upper()
    has_cyrillic = any(is_cyrillic(c) for c in text)
    
    if has_cyrillic:
        angry_inserts = ["БЛИН", "ААААА", "ДА КАК ТАК", "ЧЁРТ", "ОЙ ВСЁ"]
    else:
        angry_inserts = ["UGH", "ARGH", "GRRRR", "DAMN", "SERIOUSLY"]
    
    words = text.split()
    result = []
    for word in words:
        result.append(word)
        if random.random() < 0.2:
            result.append(random.choice(angry_inserts))
    
    angry_emojis = ["😡", "🤬", "💢", "👿", "😤"]
    return " ".join(result) + " " + random.choice(angry_emojis) * random.randint(1, 3)

def creepy_text(text: str) -> str:
    """Жуткий текст..."""
    has_cyrillic = any(is_cyrillic(c) for c in text)
    
    words = text.lower().split()
    result = []
    for word in words:
        # Растягиваем случайные буквы
        new_word = list(word)
        for i in range(len(new_word)):
            if is_letter(new_word[i]) and random.random() < 0.2:
                new_word[i] = new_word[i] * random.randint(2, 4)
        result.append("".join(new_word))
    
    text = " ".join(result)
    
    if has_cyrillic:
        creepy_adds = ["...", " хе-хе-хе...", " я вижу тебя...", " беги...", ""]
    else:
        creepy_adds = ["...", " hehe...", " I see you...", " run...", ""]
    
    creepy_emojis = ["👁️", "🌚", "👀", "🫥", "💀", "🕷️"]
    
    return f"{random.choice(creepy_emojis)} {text}{random.choice(creepy_adds)} {random.choice(creepy_emojis)}"


# ==================== вебхук ====================

async def get_or_create_webhook(channel: discord.TextChannel) -> discord.Webhook:
    try:
        if channel.id in webhook_cache:
            return webhook_cache[channel.id]
        webhooks = await channel.webhooks()
        for wh in webhooks:
            if wh.name == "WizardEffect":
                webhook_cache[channel.id] = wh
                return wh
        wh = await channel.create_webhook(name="WizardEffect")
        webhook_cache[channel.id] = wh
        return wh
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise


# ==================== применение эффекта ====================

async def apply_effect(message: discord.Message, effect: str, original: str) -> bool:
    """Применяет эффект к сообщению. Возвращает True если обработано."""
    try:
        # Эффекты без вебхука
        if effect == "anonymous":
            await message.delete()
            embed = discord.Embed(description=original, color=random.choice(COLORS))
            embed.set_author(name=WIZARD["messages"]["anonymous_format"])
            await message.channel.send(embed=embed)
            return True

        # Slowmode обрабатывается Discord'ом
        if effect in ("slowmode", "mega_slowmode"):
            return False

        # Словарь всех эффектов
        effect_functions = {
            "reverse": reverse_text,
            "caps": lambda t: t.upper(),
            "whisper": lambda t: f"*{t.lower()}*",
            "shuffle": shuffle_words,
            "stutter": stutter_text,
            "censor": censor_text,
            "mock": mock_text,
            "uwu": uwu_text,
            "leetspeak": leetspeak_text,
            "drunk": drunk_text,
            "spoiler": spoiler_text,
            "clap": clap_text,
            "echo": echo_text,
            "dramatic": dramatic_text,
            "glitch": glitch_text,
            "zalgo_lite": glitch_text,
            "snake": snake_text,
            "backwards_words": backwards_words_text,
            "tiny": tiny_text,
            "yell": yell_text,
            "confused": confused_text,
            "pirate": pirate_text,
            "robot": robot_text,
            "medieval": medieval_text,
            "sarcasm_quotes": sarcasm_quotes_text,
            "void": void_text,
            "hacker": hacker_text,
            "musical": musical_text,
            "explosion": explosion_text,
            "baby": baby_text,
            "owoify": owoify_text,
            "angry": angry_text,
            "creepy": creepy_text,
        }

        if effect in effect_functions:
            await message.delete()
            wh = await get_or_create_webhook(message.channel)
            new_content = effect_functions[effect](original)
            await wh.send(
                content=new_content,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
            )
            return True

        elif effect == "emoji_tax":
            await message.delete()
            emojis = WIZARD["effects"]["emoji_tax"].get("emojis", ["🤡", "💀", "👺"])
            wh = await get_or_create_webhook(message.channel)
            await wh.send(
                content=f"{original} {random.choice(emojis)}",
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
            )
            return True

        elif effect == "delay":
            await message.delete()
            delay = WIZARD["effects"]["delay"].get("delay_seconds", 5)
            await asyncio.sleep(delay)
            wh = await get_or_create_webhook(message.channel)
            await wh.send(
                content=original,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
            )
            return True

        elif effect == "double":
            await message.delete()
            wh = await get_or_create_webhook(message.channel)
            await wh.send(
                content=original,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
            )
            await asyncio.sleep(0.5)
            await wh.send(
                content=original,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
            )
            return True

        return False

    except discord.NotFound:
        logger.warning(f"Message already deleted for effect {effect}")
        return True
    except discord.Forbidden as e:
        logger.error(f"Permission error in effect {effect}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error applying effect {effect}: {e}\n{traceback.format_exc()}")
        return False


# ==================== колдун таск =========================

@tasks.loop(hours=WIZARD["interval_hours"])
async def wizard_cycle():
    global active_effect, effect_end_time

    try:
        channel = bot.get_channel(WIZARD_CHANNEL)
        if channel is None:
            logger.error(f"Wizard channel {WIZARD_CHANNEL} not found")
            return

        effects = list(WIZARD["effects"].keys())
        if not effects:
            logger.error("No effects defined in config")
            return

        chosen = random.choice(effects)
        effect_data = WIZARD["effects"].get(chosen, {})
        duration = WIZARD["duration_minutes"]

        active_effect = chosen
        effect_end_time = time.time() + (duration * 60)

        logger.info(f"Wizard effect started: {chosen} for {duration} minutes")

        # slowmode
        if chosen in ("slowmode", "mega_slowmode"):
            try:
                slowmode_sec = effect_data.get("slowmode_seconds", 30)
                await channel.edit(slowmode_delay=slowmode_sec)
                logger.info(f"Slowmode set to {slowmode_sec} seconds")
            except Exception as e:
                logger.error(f"Failed to set slowmode: {e}")

        # объявление
        try:
            embed = discord.Embed(
                title=WIZARD["announcement_title"],
                color=random.choice(COLORS),
            )
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send wizard announcement: {e}")

        # ждём окончания
        await asyncio.sleep(duration * 60)

        # снятие
        active_effect = None
        effect_end_time = 0

        if chosen in ("slowmode", "mega_slowmode"):
            try:
                await channel.edit(slowmode_delay=0)
                logger.info("Slowmode removed")
            except Exception as e:
                logger.error(f"Failed to remove slowmode: {e}")

        # объявление о конце
        try:
            end_embed = discord.Embed(
                description=WIZARD["messages"]["effect_ended"],
                color=0x00FF00,
            )
            await channel.send(embed=end_embed)
        except Exception as e:
            logger.error(f"Failed to send end announcement: {e}")

        logger.info(f"Wizard effect ended: {chosen}")

    except Exception as e:
        logger.error(f"Wizard cycle error: {e}\n{traceback.format_exc()}")
        active_effect = None
        effect_end_time = 0


@wizard_cycle.before_loop
async def before_wizard():
    await bot.wait_until_ready()
    logger.info("Wizard cycle ready to start")


# ==================== обработка сообщений ==================

@bot.event
async def on_message(message: discord.Message):
    try:
        if message.author.bot:
            return

        # эффекты только в одном канале
        if message.channel.id != WIZARD_CHANNEL or active_effect is None:
            await bot.process_commands(message)
            return

        if time.time() > effect_end_time:
            await bot.process_commands(message)
            return

        original = message.content
        if not original:
            await bot.process_commands(message)
            return

        handled = await apply_effect(message, active_effect, original)

        if not handled:
            await bot.process_commands(message)

    except Exception as e:
        logger.error(f"on_message error: {e}\n{traceback.format_exc()}")
        try:
            await bot.process_commands(message)
        except Exception:
            pass


# ==================== глобальный обработчик ошибок ==================

@bot.event
async def on_error(event: str, *args, **kwargs):
    logger.error(f"Error in {event}: {traceback.format_exc()}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logger.error(f"App command error: {error}\n{traceback.format_exc()}")
    try:
        if interaction.response.is_done():
            await interaction.followup.send("An error occurred.", ephemeral=True)
        else:
            await interaction.response.send_message("An error occurred.", ephemeral=True)
    except Exception:
        pass


# ======================== events ==========================

@bot.event
async def on_ready():
    logger.info(f"{bot.user.name} is online!")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands")
    except Exception as e:
        logger.error(f"Sync error: {e}")

    if not wizard_cycle.is_running():
        wizard_cycle.start()
        logger.info("Wizard cycle started")


@bot.event
async def on_disconnect():
    logger.warning("Bot disconnected")


@bot.event
async def on_resumed():
    logger.info("Bot resumed connection")


# ===================== /send ==============================

@bot.tree.command(
    name=CMD["send"]["name"],
    description=CMD["send"]["description"],
)
@app_commands.describe(message=CMD["send"]["option_description"])
async def send_message(interaction: discord.Interaction, message: str):
    try:
        user_id = interaction.user.id
        now = time.time()

        if user_id in user_cooldowns:
            passed = now - user_cooldowns[user_id]
            if passed < COOLDOWN:
                remaining = COOLDOWN - passed
                await interaction.response.send_message(
                    MSGS["cooldown"].format(
                        minutes=int(remaining // 60),
                        seconds=int(remaining % 60),
                    ),
                    ephemeral=True,
                )
                return

        await interaction.response.defer(ephemeral=True)

        guild = bot.get_guild(GUILD_ID)
        channel = bot.get_channel(CHANNEL_ID)

        if guild is None or channel is None:
            logger.error(f"Guild {GUILD_ID} or channel {CHANNEL_ID} not found")
            try:
                await interaction.delete_original_response()
            except Exception:
                pass
            return

        if guild.get_member(user_id) is None:
            logger.warning(f"User {user_id} not a member of guild {GUILD_ID}")
            try:
                await interaction.delete_original_response()
            except Exception:
                pass
            return

        embed = discord.Embed(
            description=message,
            color=random.choice(COLORS),
        )
        await channel.send(embed=embed)
        user_cooldowns[user_id] = now
        logger.info(f"Anonymous message sent by user {user_id}")

        try:
            await interaction.delete_original_response()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"/send error: {e}\n{traceback.format_exc()}")
        try:
            await interaction.delete_original_response()
        except Exception:
            pass


# ===================== /prison ============================

@bot.tree.command(
    name=CMD["prison"]["name"],
    description=CMD["prison"]["description"],
)
@app_commands.describe(
    target=CMD["prison"]["option_description"],
    reason=CMD["prison"]["reason_description"],
)
async def prison(
    interaction: discord.Interaction,
    target: discord.User,
    reason: str = None,
):
    try:
        guild = bot.get_guild(GUILD_ID)

        if guild is None:
            await interaction.response.send_message(
                MSGS["prison_fail"], ephemeral=True
            )
            return

        caller = guild.get_member(interaction.user.id)
        if caller is None or not any(r.id == STAFF_ROLE_ID for r in caller.roles):
            await interaction.response.send_message(
                MSGS["no_permission"], ephemeral=True
            )
            return

        member = guild.get_member(target.id)
        if member is None:
            await interaction.response.send_message(
                MSGS["target_not_member"], ephemeral=True
            )
            return

        inmate_number = random.randint(0, 9999)
        new_nick = MSGS["prison_nickname_format"].format(number=f"{inmate_number:04d}")

        actual_reason = reason or MSGS["prison_default_reason"]
        audit_reason = MSGS["prison_audit_reason"].format(
            staff=interaction.user,
            reason=actual_reason,
        )

        # смена ника
        try:
            await member.edit(nick=new_nick, reason=audit_reason)
        except discord.Forbidden:
            logger.warning(f"Cannot change nick for {member.id}")
        except Exception as e:
            logger.error(f"Nick change error: {e}")

        # удаление ролей
        try:
            roles_to_remove = [r for r in member.roles if r != guild.default_role]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason=audit_reason)
        except discord.Forbidden:
            logger.warning(f"Cannot remove roles from {member.id}")
        except Exception as e:
            logger.error(f"Role removal error: {e}")

        # выдача роли заключённого
        try:
            prisoner_role = guild.get_role(PRISONER_ROLE)
            if prisoner_role:
                await member.add_roles(prisoner_role, reason=audit_reason)
        except discord.Forbidden:
            logger.warning(f"Cannot add prisoner role to {member.id}")
        except Exception as e:
            logger.error(f"Role add error: {e}")

        embed = discord.Embed(
            description=MSGS["prison_success"].format(
                target=target.mention,
                new_nick=new_nick,
            ),
            color=random.choice(COLORS),
        )
        if reason:
            embed.add_field(
                name=MSGS["prison_embed_reason_field"],
                value=reason,
                inline=False,
            )

        await interaction.response.send_message(embed=embed)
        logger.info(f"User {target.id} imprisoned by {interaction.user.id}")

    except discord.Forbidden:
        try:
            await interaction.response.send_message(
                MSGS["prison_fail"], ephemeral=True
            )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"/prison error: {e}\n{traceback.format_exc()}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    MSGS["prison_fail"], ephemeral=True
                )
        except Exception:
            pass


# ==================== запуск ====================

if __name__ == "__main__":
    try:
        logger.info("Starting bot...")
        bot.run(BOT_TOKEN)
    except discord.LoginFailure:
        logger.critical("Invalid bot token!")
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}\n{traceback.format_exc()}")