import re
import sys
import os
from itertools import product
from PIL import Image, ImageDraw, ImageFont

# ========== ФУНКЦИЯ ДЛЯ ТЕКСТА С ОБВОДКОЙ ==========
def draw_text_with_outline(draw, text, position, font, text_color="black", outline_color="gray", outline_width=1):
    """Рисует текст с тонкой серой обводкой"""
    x, y = position
    # Рисуем обводку (сдвиги по всем направлениям)
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, fill=outline_color, font=font)
    # Рисуем основной текст
    draw.text((x, y), text, fill=text_color, font=font)

# ========== ПАРСИНГ ВЫРАЖЕНИЯ В БЛОКИ ==========
def expression_to_blocks(expression: str):
    """Парсит выражение вида 'кар^1+вниз^1[з=р]' в список блоков для отрисовки"""
    blocks_str = expression.replace(" ", "").split("+")
    blocks_data = []
    
    for block in blocks_str:
        block_clean = re.sub(r"([а-яА-Яa-zA-ZёЁ])\s+([а-яА-Яa-zA-ZёЁ])", r"\1\2", block)
        word_match = re.match(r"^[a-zA-Zа-яА-ЯёЁ]+", block_clean)
        if not word_match:
            continue
        word = word_match.group()
        rest = block_clean[len(word):]
        
        removals_left = removals_right = 0
        replacements = {}
        reverse = False
        
        if match := re.search(r"\^(\d+)", rest):
            removals_left = int(match.group(1))
        if match := re.search(r"\$(\d+)", rest):
            removals_right = int(match.group(1))
        if match := re.search(r"\[([^\]]+)\]", rest):
            for repl in match.group(1).split(","):
                if "=" in repl:
                    old, new = repl.split("=")
                    replacements[old.strip()] = new.strip()
        if "~" in rest:
            reverse = True
        
        blocks_data.append({
            "word": word,
            "removals_left": removals_left,
            "removals_right": removals_right,
            "replacements": replacements,
            "reverse": reverse
        })
    
    return blocks_data

# ========== ГЕНЕРАЦИЯ КАРТИНКИ РЕБУСА ==========
def draw_rebus_from_blocks(blocks_data, output_path="rebus_output.png", images_dir="images", font_path=None, target_size=(150, 150), frame_text="ТРЯСЛО993", frame_padding=30, letter_spacing_h=5, letter_spacing_v=7):
    """
    blocks_data: список блоков с полями word, removals_left, removals_right, replacements, reverse
    target_size: (ширина, высота) для каждого блока
    font_path: путь к TTF файлу шрифта
    frame_text: текст для рамки
    frame_padding: отступ для текста рамки (толщина рамки в пикселях)
    letter_spacing_h: интервал между буквами для горизонтальных строк (в пикселях)
    letter_spacing_v: интервал между буквами для вертикальных строк (в пикселях)
    """
    # Если шрифт не указали, ищем системный
    if not font_path:
        possible_fonts = [
            "minecraft.ttf",
            "C:/Users/annaa/Desktop/rebus/minecraft.ttf",
            "arial.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/times.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for f in possible_fonts:
            if os.path.exists(f):
                font_path = f
                break
    
    images = []
    for block in blocks_data:
        # Загружаем картинку
        img_path = os.path.join(images_dir, f"{block['word']}.png")
        if not os.path.exists(img_path):
            for ext in ['.jpg', '.jpeg', '.webp']:
                alt_path = os.path.join(images_dir, f"{block['word']}{ext}")
                if os.path.exists(alt_path):
                    img_path = alt_path
                    break
            else:
                # Создаём заглушку
                img = Image.new("RGB", target_size, "lightgray")
                draw = ImageDraw.Draw(img)
                if font_path:
                    try:
                        font = ImageFont.truetype(font_path, 20)
                    except:
                        font = ImageFont.load_default()
                else:
                    font = ImageFont.load_default()
                bbox = draw.textbbox((0, 0), block['word'], font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                draw.text(((target_size[0] - text_width) // 2, (target_size[1] - text_height) // 2), 
                         block['word'], fill="black", font=font)
                images.append(img)
                continue
        
        img = Image.open(img_path).convert("RGBA")
        
        # Ресайз с сохранением пропорций
        img.thumbnail(target_size, Image.Resampling.LANCZOS)
        
        # Создаём фон с отступами для рамки
        new_width = target_size[0] + frame_padding * 2
        new_height = target_size[1] + frame_padding * 2
        background = Image.new("RGBA", (new_width, new_height), (255, 255, 255, 255))
        
        # Центрируем картинку внутри
        offset_x = frame_padding + (target_size[0] - img.width) // 2
        offset_y = frame_padding + (target_size[1] - img.height) // 2
        background.paste(img, (offset_x, offset_y), img)
        img = background
        
        # Рисуем рамку
        draw = ImageDraw.Draw(img)
        
        try:
            if font_path:
                frame_font = ImageFont.truetype(font_path, frame_padding - 19)
                font_big = ImageFont.truetype(font_path, 40)
                font_small = ImageFont.truetype(font_path, 24)
            else:
                frame_font = ImageFont.load_default()
                font_big = ImageFont.load_default()
                font_small = ImageFont.load_default()
        except:
            frame_font = ImageFont.load_default()
            font_big = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # ===== ТЕКСТОВАЯ РАМКА С ИНТЕРВАЛАМИ =====
        text = frame_text
        
        # Функция для рисования строки с интервалом между буквами (горизонтально)
        def draw_text_with_spacing_h(draw, text, x, y, font, spacing, text_color="black", outline_color="gray", outline_width=1):
            current_x = x
            for char in text:
                # Рисуем обводку
                for dx in range(-outline_width, outline_width + 1):
                    for dy in range(-outline_width, outline_width + 1):
                        if dx != 0 or dy != 0:
                            draw.text((current_x + dx, y + dy), char, fill=outline_color, font=font)
                # Рисуем букву
                draw.text((current_x, y), char, fill=text_color, font=font)
                # Получаем ширину буквы
                bbox = draw.textbbox((0, 0), char, font=font)
                char_width = bbox[2] - bbox[0]
                current_x += char_width + spacing
        
        # Функция для рисования строки с интервалом между буквами (вертикально)
        def draw_text_with_spacing_v(draw, text, x, y, font, spacing, text_color="black", outline_color="gray", outline_width=1):
            current_y = y
            for char in text:
                # Рисуем обводку
                for dx in range(-outline_width, outline_width + 1):
                    for dy in range(-outline_width, outline_width + 1):
                        if dx != 0 or dy != 0:
                            draw.text((x + dx, current_y + dy), char, fill=outline_color, font=font)
                # Рисуем букву
                draw.text((x, current_y), char, fill=text_color, font=font)
                # Получаем высоту буквы
                bbox = draw.textbbox((0, 0), char, font=font)
                char_height = bbox[3] - bbox[1]
                current_y += char_height + spacing
        
        # Верхняя строка (горизонтально, с интервалом)
        y_top = 5
        x_start = (img.width - sum_char_widths_with_spacing(draw, text, frame_font, letter_spacing_h)) // 2
        draw_text_with_spacing_h(draw, text, x_start, y_top, frame_font, letter_spacing_h,
                                  text_color="black", outline_color="gray", outline_width=1)
        
        # Нижняя строка (горизонтально, с интервалом)
        bbox = draw.textbbox((0, 0), "A", font=frame_font)
        line_height = bbox[3] - bbox[1]
        y_bottom = img.height - line_height - 5
        x_start_bottom = (img.width - sum_char_widths_with_spacing(draw, text, frame_font, letter_spacing_h)) // 2
        draw_text_with_spacing_h(draw, text, x_start_bottom, y_bottom, frame_font, letter_spacing_h,
                                  text_color="black", outline_color="gray", outline_width=1)
        
        # Левая сторона (вертикально, с интервалом)
        x_left = 8
        y_start = frame_padding + 10
        draw_text_with_spacing_v(draw, text, x_left, y_start, frame_font, letter_spacing_v,
                                  text_color="black", outline_color="gray", outline_width=1)
        
        # Правая сторона (вертикально, с интервалом)
        max_char_width = 0
        for char in text:
            bbox = draw.textbbox((0, 0), char, font=frame_font)
            char_width = bbox[2] - bbox[0]
            if char_width > max_char_width:
                max_char_width = char_width
        x_right = img.width - max_char_width - 8
        draw_text_with_spacing_v(draw, text, x_right, y_start, frame_font, letter_spacing_v,
                                  text_color="black", outline_color="gray", outline_width=1)
        
        # Запятые слева (чёрный текст, серая обводка)
        if block['removals_left'] > 0:
            draw_text_with_outline(draw, "," * block['removals_left'], (frame_padding + 10, frame_padding + 10), font_big, 
                                   text_color="black", outline_color="gray", outline_width=1)
        
        # Запятые справа (чёрный текст, серая обводка)
        if block['removals_right'] > 0:
            comma_text = "," * block['removals_right']
            bbox = draw.textbbox((0, 0), comma_text, font=font_big)
            comma_width = bbox[2] - bbox[0]
            draw_text_with_outline(draw, comma_text, (img.width - comma_width - frame_padding - 10, img.height - frame_padding - 30), font_big,
                                   text_color="black", outline_color="gray", outline_width=1)
        
        # Замены (чёрный текст, серая обводка)
        if block['replacements']:
            repl_text = ", ".join([f"{k}={v}" for k, v in block['replacements'].items()])
            bbox = draw.textbbox((0, 0), repl_text, font=font_small)
            repl_width = bbox[2] - bbox[0]
            draw_text_with_outline(draw, repl_text, ((img.width - repl_width) // 2, img.height - frame_padding - 15), font_small,
                                   text_color="black", outline_color="gray", outline_width=1)
        
        # Переворот
        if block['reverse']:
            img = img.transpose(Image.Transpose.ROTATE_180)
        
        images.append(img)
    
    # Склейка
    if not images:
        return None
    
    total_width = sum(img.width for img in images) + 30 * (len(images) - 1)
    max_height = max(img.height for img in images)
    combined = Image.new("RGB", (total_width, max_height), "white")
    
    x_offset = 0
    for img in images:
       # Приводим img к RGB если она RGBA
if img.mode == 'RGBA':
    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
    rgb_img.paste(img, mask=img.split()[3])  # используем альфа-канал как маску
    combined.paste(rgb_img, (x_offset, 0))
else:
    combined.paste(img, (x_offset, 0))
    
        x_offset += img.width + 30
    
    if output_path:
        combined.save(output_path)
    return combined

# Вспомогательная функция для подсчёта общей ширины строки с интервалами
def sum_char_widths_with_spacing(draw, text, font, spacing):
    """Подсчитывает общую ширину строки с учётом интервалов между буквами"""
    total = 0
    for i, char in enumerate(text):
        bbox = draw.textbbox((0, 0), char, font=font)
        char_width = bbox[2] - bbox[0]
        total += char_width
        if i < len(text) - 1:
            total += spacing
    return total

# ========== ОСТАЛЬНЫЕ ФУНКЦИИ ==========
def parse_block(block: str):
    block_clean = re.sub(r"([а-яА-Яa-zA-ZёЁ])\s+([а-яА-Яa-zA-ZёЁ])", r"\1\2", block)
    word_match = re.match(r"^[a-zA-Zа-яА-ЯёЁ]+", block_clean)
    if not word_match:
        raise ValueError(f"Не удалось распознать слово в блоке: {block}")
    word = word_match.group()
    rest = block_clean[len(word):]
    removals_left = removals_right = 0
    replacements = {}
    reverse = False

    if match := re.search(r"\^(\d+)", rest):
        removals_left = int(match.group(1))
    if match := re.search(r"\$(\d+)", rest):
        removals_right = int(match.group(1))
    if match := re.search(r"\[([^\]]+)\]", rest):
        for repl in match.group(1).split(","):
            if "=" in repl:
                old, new = repl.split("=")
                replacements[old.strip()] = new.strip()
    if "~" in rest:
        reverse = True
    return word, removals_left, removals_right, replacements, reverse

def apply_rules(word: str, removals_left: int, removals_right: int, replacements: dict, reverse: bool) -> str:
    result = word
    if removals_left:
        result = result[removals_left:]
    if removals_right:
        result = result[:-removals_right] if removals_right <= len(result) else ""
    for old, new in replacements.items():
        result = result.replace(old, new)
    if reverse:
        result = result[::-1]
    return result

def solve_rebus(expression: str, expected_answer: str = None):
    blocks = expression.replace(" ", "").split("+")
    parts = []
    print("\n🔍 Разбор ребуса:\n")
    for i, block in enumerate(blocks, 1):
        word, ldel, rdel, repl, rev = parse_block(block)
        result = apply_rules(word, ldel, rdel, repl, rev)
        parts.append(result)
        print(f"Блок {i}: {block}")
        print(f"  → слово '{word}'")
        if ldel: print(f"  → удаляем {ldel} слева: '{word[ldel:]}'")
        if rdel: print(f"  → удаляем {rdel} справа: '{word[:-rdel]}'")
        if repl: print(f"  → замены {repl}: '{result if not rev else result[::-1]}'")
        if rev: print(f"  → переворот: '{result}'")
        print(f"  ✅ итог блока: {result}\n")
    final = "".join(parts)
    print(f"📦 Склейка: {' + '.join(parts)} = {final}")
    if expected_answer:
        if final == expected_answer:
            print(f"✅ РЕБУС СОШЁЛСЯ: {final}")
        else:
            print(f"❌ НЕ СОШЁЛСЯ: получилось {final}, а ожидалось {expected_answer}")
    else:
        print(f"💡 Ответ: {final}")
    return final

def load_dictionary(filepath: str = "words.txt") -> set:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            words = set()
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                cleaned = raw.replace(" ", "").lower()
                words.add(cleaned)
        print(f"📚 Загружено {len(words)} слов из {filepath}")
        return words
    except FileNotFoundError:
        print(f"⚠️ Файл {filepath} не найден. Использую пустой словарь.")
        return set()

def load_letters(filepath: str = "letters.txt") -> set:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            letters = set()
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                cleaned = raw.replace(" ", "").lower()
                letters.add(cleaned)
        print(f"🔤 Загружено {len(letters)} букв из {filepath}")
        return letters
    except FileNotFoundError:
        print(f"⚠️ Файл {filepath} не найден. Буквы не исключаются.")
        return set()

def can_obtain_from(base_word: str, target: str, max_removals=2, allow_replace=True, allow_reverse=True) -> list:
    results = []
    if base_word == target:
        results.append(f"{base_word}")
    for l in range(1, max_removals+1):
        if base_word[l:] == target:
            results.append(f"{base_word}^{l}")
    for r in range(1, max_removals+1):
        if base_word[:-r] == target:
            results.append(f"{base_word}${r}")
    for l in range(1, max_removals+1):
        for r in range(1, max_removals+1):
            if l+r < len(base_word) and base_word[l:-r] == target:
                results.append(f"{base_word}^{l}${r}")
    if allow_replace and len(base_word) == len(target):
        diff_positions = [i for i in range(len(base_word)) if base_word[i] != target[i]]
        if len(diff_positions) == 1:
            i = diff_positions[0]
            results.append(f"{base_word}[{base_word[i]}={target[i]}]")
    if allow_reverse and base_word[::-1] == target:
        results.append(f"{base_word}~")
    seen = set()
    unique = []
    for r in results:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique

def split_into_parts(word: str, dictionary: set, excluded_words: set = None, max_removals=2, max_parts=3) -> list:
    word = word.lower()
    dictionary = {w.lower() for w in dictionary}
    dictionary.discard(word)
    if excluded_words:
        dictionary -= excluded_words
    variants = []
    for parts_count in range(2, max_parts+1):
        lengths = []
        if parts_count == 2:
            for i in range(1, len(word)):
                lengths.append([i, len(word)-i])
        elif parts_count == 3:
            for i in range(1, len(word)-1):
                for j in range(i+1, len(word)):
                    lengths.append([i, j-i, len(word)-j])
        for split_lengths in lengths:
            parts = []
            pos = 0
            valid = True
            for l in split_lengths:
                part = word[pos:pos+l]
                if not part:
                    valid = False
                    break
                parts.append(part)
                pos += l
            if not valid:
                continue
            part_rules = []
            for part in parts:
                candidates = []
                for dict_word in dictionary:
                    rules = can_obtain_from(dict_word, part, max_removals, allow_replace=True, allow_reverse=True)
                    for rule in rules:
                        candidates.append((dict_word, rule))
                if candidates:
                    part_rules.append(candidates)
                else:
                    part_rules = None
                    break
            if part_rules and all(part_rules):
                for combination in product(*part_rules):
                    variant = {
                        "parts": [c[1] for c in combination],
                        "expression": " + ".join([c[1] for c in combination]),
                        "full_word": word,
                        "original_words": [c[0] for c in combination]
                    }
                    variants.append(variant)
    seen_expr = set()
    unique_variants = []
    for v in variants:
        if v["expression"] not in seen_expr:
            seen_expr.add(v["expression"])
            unique_variants.append(v)
    return unique_variants

def suggest_for_word(target_word: str, dict_file: str = "words.txt", letters_file: str = "letters.txt", max_parts=3, max_removals=2):
    print(f"\n🧩 Ищем способы собрать слово '{target_word}' из словаря (без букв и без самого слова)...\n")
    dictionary = load_dictionary(dict_file)
    letters = load_letters(letters_file)
    if target_word.lower() in dictionary:
        print(f"⚠️ Слово '{target_word}' есть в словаре, но оно НЕ будет использоваться как блок.")
    if letters and target_word.lower() in letters:
        print(f"⚠️ Слово '{target_word}' есть в списке букв, оно исключено.")
    variants = split_into_parts(target_word, dictionary, excluded_words=letters, max_removals=max_removals, max_parts=max_parts)
    if not variants:
        print(f"❌ Не найдено способов собрать '{target_word}' без использования букв и самого слова.")
        print("   Попробуй:")
        print("   - добавить больше слов в words.txt")
        print("   - увеличить max_parts или max_removals")
        return
    print(f"✅ Найдено {len(variants)} честных способов:\n")
    for idx, v in enumerate(variants[:30], 1):
        print(f"{idx}. {v['expression']}")
        print(f"   → {v['full_word']} (из {', '.join(v['original_words'])})\n")
    if len(variants) > 30:
        print(f"... и ещё {len(variants)-30} вариантов")

# ========== ТОЧКА ВХОДА ==========
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("=" * 50)
        print("🧩 КОНСТРУКТОР РЕБУСОВ v3.6 (СЕРАЯ ПОДВОДКА)")
        print("=" * 50)
        print("\nИспользование:")
        print("  1. Решить ребус (текст):")
        print("     python rebus_builder.py \"кар^1+вниз^1[з=р]\" [--answer арнир]")
        print("\n  2. Сгенерировать картинку ребуса:")
        print("     python rebus_builder.py --draw \"кар^1+вниз^1[з=р]\" [--output rebus.png] [--images-dir images] [--font путь/к/шрифту.ttf]")
        print("\n  3. Разбить слово на части (подобрать ребус):")
        print("     python rebus_builder.py --split арнир [--dict words.txt] [--letters letters.txt]")
        print("\n  4. Справка:")
        print("     python rebus_builder.py --help")
        sys.exit(1)
    
    if sys.argv[1] == "--help":
        print("""
📖 ПРАВИЛА СОЗДАНИЯ РЕБУСОВ:

^N   - удалить N букв СЛЕВА (запятые перед картинкой)
$N   - удалить N букв СПРАВА (запятые после картинки)
[а=б] - заменить букву а на б
~    - перевернуть слово (картинка вверх ногами)
+    - склеить блоки

Примеры:
  лиса~              → асил
  кар^1              → ар
  вниз^1[з=р]        → нир
  кар^1+вниз^1[з=р]  → арнир

Генерация картинки:
  --draw выражение    создать картинку ребуса
  --output файл       куда сохранить (по умолч. rebus_output.png)
  --images-dir папка  где лежат картинки слов (по умолч. images)
  --font путь         путь к TTF шрифту (например --font C:/Windows/Fonts/times.ttf)
        """)
        sys.exit(0)
    
    if sys.argv[1] == "--draw":
        if len(sys.argv) < 3:
            print("❌ Укажи выражение для отрисовки: --draw \"кар^1+вниз^1[з=р]\"")
            sys.exit(1)
        expression = sys.argv[2]
        output = "rebus_output.png"
        images_dir = "images"
        font_path = None
        if "--output" in sys.argv:
            output = sys.argv[sys.argv.index("--output") + 1]
        if "--images-dir" in sys.argv:
            images_dir = sys.argv[sys.argv.index("--images-dir") + 1]
        if "--font" in sys.argv:
            font_path = sys.argv[sys.argv.index("--font") + 1]
        
        print(f"\n🎨 Генерация картинки для ребуса: {expression}")
        if font_path:
            print(f"🔤 Используется шрифт: {font_path}")
        print()
        
        blocks_data = expression_to_blocks(expression)
        if not blocks_data:
            print("❌ Не удалось разобрать выражение")
            sys.exit(1)
        
        img = draw_rebus_from_blocks(blocks_data, output, images_dir=images_dir, font_path=font_path)
        if img:
            print(f"✅ Картинка сохранена: {output}")
        else:
            print("❌ Ошибка при создании картинки")
        sys.exit(0)
    
    if sys.argv[1] == "--split":
        word = sys.argv[2] if len(sys.argv) > 2 else input("Введите слово: ")
        dict_file = "words.txt"
        letters_file = "letters.txt"
        max_parts = 3
        max_removals = 2
        if "--dict" in sys.argv:
            dict_file = sys.argv[sys.argv.index("--dict") + 1]
        if "--letters" in sys.argv:
            letters_file = sys.argv[sys.argv.index("--letters") + 1]
        if "--max-parts" in sys.argv:
            max_parts = int(sys.argv[sys.argv.index("--max-parts") + 1])
        if "--max-removals" in sys.argv:
            max_removals = int(sys.argv[sys.argv.index("--max-removals") + 1])
        suggest_for_word(word, dict_file, letters_file, max_parts, max_removals)
        sys.exit(0)
    
    expr = sys.argv[1]
    answer = None
    if "--answer" in sys.argv:
        answer = sys.argv[sys.argv.index("--answer") + 1]
    solve_rebus(expr, answer)
