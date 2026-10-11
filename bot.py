import os
import re
import random
import asyncio
from io import BytesIO
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from PIL import Image, ImageDraw, ImageFont
from aiohttp import web
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageStat

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- СТАНИ FSM ---
# --- ДОДАЙ ЦЕЙ СТАН ДО ІНШИХ СТАНІВ FSM ---
class Cs16States(StatesGroup):
    waiting_for_photo = State()


# --- ДОДАЙ ЦЮ ФУНКЦІЮ ОБРОБКИ ОСВІТЛЕННЯ ТА НАКЛАДАННЯ ---
def apply_cs_overlay(background_img: Image.Image) -> Image.Image:
    bg_width, bg_height = background_img.size
    
    arms_path = "cs_arms.png"
    
    if not os.path.exists(arms_path):
        # Заглушка, якщо файлу немає
        arms_img = Image.new("RGBA", (bg_width, int(bg_height * 0.3)), (0, 0, 0, 0))
    else:
        arms_img = Image.open(arms_path).convert("RGBA")
        
        # МАГІЯ: автоматично знаходимо і вирізаємо тільки реальні руки/ніж (без прозорих відступів)
        bbox = arms_img.getbbox()
        if bbox:
            arms_img = arms_img.crop(bbox)
    
    # Визначаємо, чи фото вертикальне (портрет) чи горизонтальне (ландшафт)
    is_portrait = bg_height > bg_width
    
    if is_portrait:
        # Для вертикальних фото (як твої скріншоти з ямою) робимо руки ширшими відносно кадру
        target_arms_width = int(bg_width * 1.1)
    else:
        # Для горизонтальних фото
        target_arms_width = int(bg_width * 0.85)
        
    arms_aspect = arms_img.width / arms_img.height
    target_arms_height = int(target_arms_width / arms_aspect)
    
    # Масштабуємо руки під розраховані розміри
    arms_img = arms_img.resize((target_arms_width, target_arms_height), Image.Resampling.LANCZOS)
    
    # --- АДАПТАЦІЯ ПІД ОСВІТЛЕННЯ ФОНУ ---
    grayscale_bg = background_img.convert("L")
    stat = ImageStat.Stat(grayscale_bg)
    avg_brightness = stat.mean[0]
    
    enhancer_bright = ImageEnhance.Brightness(arms_img)
    brightness_factor = max(0.5, min(1.3, avg_brightness / 120.0))
    arms_img = enhancer_bright.enhance(brightness_factor)
    
    enhancer_contrast = ImageEnhance.Contrast(arms_img)
    arms_img = enhancer_contrast.enhance(1.1)
    
    # Центруємо по горизонталі та притискаємо до нижнього краю екрана
    paste_x = (bg_width - target_arms_width) // 2
    paste_y = bg_height - target_arms_height + int(target_arms_height * 0.08) # легкий заступ за нижню рамку
    
    # Накладаємо з урахуванням прозорості
    base_rgba = background_img.convert("RGBA")
    overlay = Image.new("RGBA", (bg_width, bg_height), (0, 0, 0, 0))
    overlay.paste(arms_img, (paste_x, paste_y), arms_img)
    
    final_img = Image.alpha_composite(base_rgba, overlay)
    
    return final_img.convert("RGB")
    
    # --- АДАПТАЦІЯ ПІД ОСВІТЛЕННЯ ФОНУ ---
    # Вираховуємо середню яскравість фонового зображення
    grayscale_bg = background_img.convert("L")
    stat = ImageStat.Stat(grayscale_bg)
    avg_brightness = stat.mean[0] # значення від 0 (темно) до 255 (сліпо світло)
    
    # Якщо фон занадто темний (нічна карта типу de_inferno вночі), затемнюємо руки
    # Якщо світлий (de_dust2 на сонці), робимо руки яскравішими й контрастнішими
    enhancer_bright = ImageEnhance.Brightness(arms_img)
    # Коефіцієнт корекції яскравості відносно середнього значення (база ~128)
    brightness_factor = max(0.4, min(1.5, avg_brightness / 128.0))
    arms_img = enhancer_bright.enhance(brightness_factor)
    
    # Додаємо легкий відтінок (Color grading), щоб руки зливалися з атмосферою кадру
    # Створюємо колірний оверлей на основі домінуючого кольору фону
    bg_thumb = background_img.resize((50, 50))
    dominant_color = bg_thumb.getpixel((25, 25)) # беремо приблизний колір середовища
    
    # Накладаємо руки унизу кадру (знизу по центру)
    paste_x = 0
    paste_y = bg_height - new_arms_height
    
    # Конвертуємо фон у RGBA для коректного накладання PNG з прозорістю
    base_rgba = background_img.convert("RGBA")
    base_rgba.paste(arms_img, (paste_x, paste_y), arms_img)
    
    return base_rgba.convert("RGB")


# --- ОБРОБНИКИ КОМАНДИ /cs16 ---

@dp.message(Command("cs16knife"))
async def cs16_cmd(message: Message, state: FSMContext):
    await message.answer("Скиньте кошерное изображение")
    await state.set_state(Cs16States.waiting_for_photo)

@dp.message(Cs16States.waiting_for_photo, F.photo)
async def process_cs16_photo(message: Message, state: FSMContext):
    await message.answer("Возвращяем в 2005 год")
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    
    # Обробка зображення в пам'яті
    with Image.open(file_bytes) as img:
        img = img.convert("RGB")
        
        # Викликаємо функцію накладання з адаптацією освітлення
        result_img = apply_cs_overlay(img)
        
        output_buffer = BytesIO()
        result_img.save(output_buffer, format="JPEG", quality=95)
        output_buffer.seek(0)
        
    input_file = BufferedInputFile(output_buffer.getvalue(), filename="cs16_view.jpg")
    await message.answer_photo(photo=input_file, caption="В гостях хорошо а дома Сounter-Strike")
    await state.clear()

class MemeStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_top_text = State()
    waiting_for_bottom_text = State()

class TextProcessingStates(StatesGroup):
    waiting_for_leet = State()
    waiting_for_niche = State()


# --- ТАБЛИЦІ ЗАМІН ТА ЛОГІКА ТЕКСТУ ---

# 1. Словник для /leetshi та Leet-стилю
LEET_MAP = {
    'а': '4', 'б': '6', 'в': 'B', 'г': 'r', 'д': 'D', 'е': '3', 'є': '3', 'ё': '3',
    'ж': '>|<', 'з': '3', 'и': 'U', 'і': 'I', 'ї': 'Yi', 'й': 'Y', 'к': 'K',
    'л': 'Jl', 'м': 'M', 'н': 'H', 'о': '0', 'п': 'n', 'р': 'P', 'с': 'C',
    'т': 'T', 'у': 'Y', 'ф': 'F', 'х': 'X', 'ц': 'C', 'ч': '4', 'ш': 'W',
    'щ': 'W', 'ъ': "'", 'ы': 'bl', 'ь': 'b', 'э': '3', 'ю': '10', 'я': 'R'
}

# 2. Словник для англійських/трансліт аналогів у "нішовому" стилі
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'є': 'ye',
    'ж': 'zh', 'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'yi', 'й': 'y', 'к': 'k',
    'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 'c',
    'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh',
    'щ': 'sch', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}


def convert_to_leet(text: str) -> str:
    """Повний 1337-переклад без урахування регістру."""
    return ''.join(LEET_MAP.get(char.lower(), char) for char in text)


def convert_to_niche(text: str) -> str:
    """Читабельний нішовий стиль з міксом leet/англ по словах, помірною заміною та випадковим CAPS."""
    tokens = re.split(r'(\s+|[.,!?]+)', text)
    result = []

    for token in tokens:
        if not token:
            continue

        # Обробка пробілів (~7% шанс видалення)
        if re.match(r'^\s+$', token):
            if random.random() < 0.07:
                continue
            result.append(token)
            continue

        # Обробка пунктуації (~20% шанс дублювання розділових знаків)
        if re.match(r'^[.,!?]+$', token):
            if random.random() < 0.20:
                token = token * random.randint(2, 3)
            result.append(token)
            continue

        word = token

        # ~15% шанс перевести окреме слово у CAPS
        is_caps = random.random() < 0.15
        if is_caps:
            word = word.upper()

        # Для конкретного слова вибираємо єдиний стиль (Leet або Translit)
        use_leet = random.choice([True, False])
        current_map = LEET_MAP if use_leet else TRANSLIT_MAP

        new_word = []
        for char in word:
            char_lower = char.lower()
            
            # Заміняємо ~35% літер у слові для збереження читабельності
            if char_lower in current_map and random.random() < 0.35:
                replacement = current_map[char_lower]
                if is_caps and len(replacement) == 1:
                    replacement = replacement.upper()
                new_word.append(replacement)
            else:
                new_word.append(char)

        result.append(''.join(new_word))

    return ''.join(result)


# --- ВЕБСЕРВЕР ДЛЯ РЕНДЕРУ ---
async def handle_ping(request):
    return web.Response(text="Bot is running!", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# --- ОБРОБНИКИ КОМАНД /leetshi ТА /nichetxt ---

@dp.message(Command("leetshi"))
async def leetshi_cmd(message: Message, state: FSMContext):
    await message.answer("Таки отправьте текст:")
    await state.set_state(TextProcessingStates.waiting_for_leet)

@dp.message(TextProcessingStates.waiting_for_leet, F.text)
async def process_leet_text(message: Message, state: FSMContext):
    converted = convert_to_leet(message.text)
    await message.answer(converted)
    await state.clear()


@dp.message(Command("nichetxt"))
async def nichetxt_cmd(message: Message, state: FSMContext):
    await message.answer("Таки отправьте текст:")
    await state.set_state(TextProcessingStates.waiting_for_niche)

@dp.message(TextProcessingStates.waiting_for_niche, F.text)
async def process_niche_text(message: Message, state: FSMContext):
    converted = convert_to_niche(message.text)
    await message.answer(converted)
    await state.clear()


# --- ОБРОБНИКИ КОМАНДИ /impact (МЕМИ) ---

@dp.message(Command("impact"))
async def start_cmd(message: Message, state: FSMContext):
    await message.answer("Скиньте кошерное изображение")
    await state.set_state(MemeStates.waiting_for_photo)

@dp.message(MemeStates.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    await state.update_data(photo_id=photo.file_id)
    await message.answer("Текст сверху: (-)")
    await state.set_state(MemeStates.waiting_for_top_text)

@dp.message(MemeStates.waiting_for_top_text, F.text)
async def process_top_text(message: Message, state: FSMContext):
    await state.update_data(top_text=message.text.upper())
    await message.answer("Текст снизу (-)")
    await state.set_state(MemeStates.waiting_for_bottom_text)

def wrap_text(text, font, max_width, draw):
    if text == "-":
        return []
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))
    return lines

def draw_meme_text(draw, text, is_top, image_width, image_height):
    if text == "-":
        return
    font_size = int(image_width * 0.09)
    max_text_width = int(image_width * 0.9)
    font_path = "impact.ttf"
    if not os.path.exists(font_path):
        font_path = "LiberationSans-Bold.ttf"
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()

    paragraphs = text.split('\n')
    all_lines = []
    for para in paragraphs:
        if para.strip():
            para_lines = wrap_text(para, font, max_text_width, draw)
            all_lines.append((para_lines, True))
        else:
            all_lines.append(([""], False))

    total_lines_count = sum(len(p[0]) for p in all_lines)
    while total_lines_count > 4 and font_size > 15:
        font_size -= 4
        try:
            font = ImageFont.truetype(font_path, font_size)
        except:
            break
        all_lines = []
        for para in paragraphs:
            if para.strip():
                all_lines.append((wrap_text(para, font, max_text_width, draw), True))
            else:
                all_lines.append(([""], False))
        total_lines_count = sum(len(p[0]) for p in all_lines)

    sample_bbox = draw.textbbox((0, 0), "AG", font=font)
    line_height = sample_bbox[3] - sample_bbox[1]
    line_spacing = int(line_height * 0.25)
    paragraph_spacing = int(line_height * 0.65)
    
    total_text_height = 0
    for i, (lines, is_para_end) in enumerate(all_lines):
        total_text_height += len(lines) * line_height + (len(lines) - 1) * line_spacing
        if i < len(all_lines) - 1 and is_para_end:
            total_text_height += paragraph_spacing

    if is_top:
        y_pos = int(image_height * 0.04)
    else:
        y_pos = int(image_height * 0.94) - total_text_height

    outline_thickness = max(1, int(font_size * 0.05))

    for lines, is_para_end in all_lines:
        for i, line in enumerate(lines):
            if not line:
                continue
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            x_pos = (image_width - line_width) / 2
            
            for adj_x in range(-outline_thickness, outline_thickness + 1):
                for adj_y in range(-outline_thickness, outline_thickness + 1):
                    if abs(adj_x) == outline_thickness and abs(adj_y) == outline_thickness:
                        continue
                    draw.text((x_pos + adj_x, y_pos + adj_y), line, font=font, fill="black")
            
            draw.text((x_pos, y_pos), line, font=font, fill="white")
            y_pos += line_height + line_spacing
            
        if is_para_end:
            y_pos += paragraph_spacing - line_spacing

@dp.message(MemeStates.waiting_for_bottom_text, F.text)
async def process_bottom_text(message: Message, state: FSMContext):
    user_data = await state.get_data()
    bottom_text = message.text.upper()
    top_text = user_data['top_text']
    
    await message.answer("Лее брат падажжи секунд.")
    
    file = await bot.get_file(user_data['photo_id'])
    file_bytes = await bot.download_file(file.file_path)
    
    with Image.open(file_bytes) as img:
        img = img.convert("RGB")
        width, height = img.size
        draw = ImageDraw.Draw(img)
        
        draw_meme_text(draw, top_text, True, width, height)
        draw_meme_text(draw, bottom_text, False, width, height)
        
        output_buffer = BytesIO()
        img.save(output_buffer, format="JPEG", quality=95)
        output_buffer.seek(0)
        
    input_file = BufferedInputFile(output_buffer.getvalue(), filename="meme.jpg")
    await message.answer_photo(photo=input_file)
    await state.clear()


async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
