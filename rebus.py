import re
import sys
import os
from itertools import product
from PIL import Image, ImageDraw, ImageFont

# ========== ФУНКЦИЯ ДЛЯ ТЕКСТА С ОБВОДКОЙ ==========
def draw_text_with_outline(draw, text, position, font, text_color="black", outline_color="gray", outline_width=1):
    """Рисует текст с тонкой серой обводкой"""
    x, y = position
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, fill=outline_color, font=font)
    draw.text((x, y), text, fill=text_color, font=font)

# ========== ПАРСИНГ ВЫРАЖЕНИЯ В БЛОКИ ==========
def expression_to_blocks(expression: str):
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
def draw_rebus_from_blocks(blocks_data, output_path=None, images_dir="images", font_path=None, target_size=(150, 150), frame_text="ТРЯСЛО993", frame_padding=30, letter_spacing_h=5, letter_spacing_v=7):
    
    if not font_path:
        possible_fonts = [
            "minecraft.ttf",
            "fonts/minecraft.ttf",
            "/app/fonts/minecraft.ttf",
            "arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for f in possible_fonts:
            if os.path.exists(f):
                font_path = f
                break
    
    images = []
    for block in blocks_data:
        img_path = os.path.join(images_dir, f"{block['word']}.png")
        if not os.path.exists(img_path):
            for ext in ['.jpg', '.jpeg', '.webp', '.webrp']:
                alt_path = os.path.join(images_dir, f"{block['word']}{ext}")
                if os.path.exists(alt_path):
                    img_path = alt_path
                    break
            else:
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
        img.thumbnail(target_size, Image.LANCZOS)
        
        new_width = target_size[0] + frame_padding * 2
        new_height = target_size[1] + frame_padding * 2
        background = Image.new("RGBA", (new_width, new_height), (255, 255, 255, 255))
        
        offset_x = frame_padding + (target_size[0] - img.width) // 2
        offset_y = frame_padding + (target_size[1] - img.height) // 2
        background.paste(img, (offset_x, offset_y), img)
        img = background
        
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
        
        text = frame_text
        
        def draw_text_with_spacing_h(draw, text, x, y, font, spacing, text_color="black", outline_color="gray", outline_width=1):
            current_x = x
            for char in text:
                for dx in range(-outline_width, outline_width + 1):
                    for dy in range(-outline_width, outline_width + 1):
                        if dx != 0 or dy != 0:
                            draw.text((current_x + dx, y + dy), char, fill=outline_color, font=font)
                draw.text((current_x, y), char, fill=text_color, font=font)
                bbox = draw.textbbox((0, 0), char, font=font)
                char_width = bbox[2] - bbox[0]
                current_x += char_width + spacing
        
        def draw_text_with_spacing_v(draw, text, x, y, font, spacing, text_color="black", outline_color="gray", outline_width=1):
            current_y = y
            for char in text:
                for dx in range(-outline_width, outline_width + 1):
                    for dy in range(-outline_width, outline_width + 1):
                        if dx != 0 or dy != 0:
                            draw.text((x + dx, current_y + dy), char, fill=outline_color, font=font)
                draw.text((x, current_y), char, fill=text_color, font=font)
                bbox = draw.textbbox((0, 0), char, font=font)
                char_height = bbox[3] - bbox[1]
                current_y += char_height + spacing
        
        def sum_char_widths_with_spacing(draw, text, font, spacing):
            total = 0
            for i, char in enumerate(text):
                bbox = draw.textbbox((0, 0), char, font=font)
                char_width = bbox[2] - bbox[0]
                total += char_width
                if i < len(text) - 1:
                    total += spacing
            return total
        
        y_top = 5
        x_start = (img.width - sum_char_widths_with_spacing(draw, text, frame_font, letter_spacing_h)) // 2
        draw_text_with_spacing_h(draw, text, x_start, y_top, frame_font, letter_spacing_h,
                                  text_color="black", outline_color="gray", outline_width=1)
        
        bbox = draw.textbbox((0, 0), "A", font=frame_font)
        line_height = bbox[3] - bbox[1]
        y_bottom = img.height - line_height - 5
        x_start_bottom = (img.width - sum_char_widths_with_spacing(draw, text, frame_font, letter_spacing_h)) // 2
        draw_text_with_spacing_h(draw, text, x_start_bottom, y_bottom, frame_font, letter_spacing_h,
                                  text_color="black", outline_color="gray", outline_width=1)
        
        x_left = 8
        y_start = frame_padding + 10
        draw_text_with_spacing_v(draw, text, x_left, y_start, frame_font, letter_spacing_v,
                                  text_color="black", outline_color="gray", outline_width=1)
        
        max_char_width = 0
        for char in text:
            bbox = draw.textbbox((0, 0), char, font=frame_font)
            char_width = bbox[2] - bbox[0]
            if char_width > max_char_width:
                max_char_width = char_width
        x_right = img.width - max_char_width - 8
        draw_text_with_spacing_v(draw, text, x_right, y_start, frame_font, letter_spacing_v,
                                  text_color="black", outline_color="gray", outline_width=1)
        
        if block['removals_left'] > 0:
            draw_text_with_outline(draw, "," * block['removals_left'], (frame_padding + 10, frame_padding + 10), font_big, 
                                   text_color="black", outline_color="gray", outline_width=1)
        
        if block['removals_right'] > 0:
            comma_text = "," * block['removals_right']
            bbox = draw.textbbox((0, 0), comma_text, font=font_big)
            comma_width = bbox[2] - bbox[0]
            draw_text_with_outline(draw, comma_text, (img.width - comma_width - frame_padding - 10, img.height - frame_padding - 30), font_big,
                                   text_color="black", outline_color="gray", outline_width=1)
        
        if block['replacements']:
            repl_text = ", ".join([f"{k}={v}" for k, v in block['replacements'].items()])
            bbox = draw.textbbox((0, 0), repl_text, font=font_small)
            repl_width = bbox[2] - bbox[0]
            draw_text_with_outline(draw, repl_text, ((img.width - repl_width) // 2, img.height - frame_padding - 15), font_small,
                                   text_color="black", outline_color="gray", outline_width=1)
        
        if block['reverse']:
            img = img.transpose(Image.Transpose.ROTATE_180)
        
        images.append(img)
    
    if not images:
        return None
    
    total_width = sum(img.width for img in images) + 30 * (len(images) - 1)
    max_height = max(img.height for img in images)
    combined = Image.new("RGB", (total_width, max_height), "white")
    
    x_offset = 0
    for img in images:
        if img.mode == 'RGBA':
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3])
            combined.paste(rgb_img, (x_offset, 0))
        else:
            combined.paste(img, (x_offset, 0))
        x_offset += img.width + 30
    
    if output_path:
        combined.save(output_path)
    return combined

# ========== РАБОТА С БАЗОЙ СЛОВ ==========
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
    print(f"\n🧩 Ищем способы собрать слово '{target_word}' из словаря...\n")
    dictionary = load_dictionary(dict_file)
    variants = split_into_parts(target_word, dictionary, excluded_words=None, max_removals=max_removals, max_parts=max_parts)
    if not variants:
        print(f"❌ Не найдено способов собрать '{target_word}'")
        return []
    return variants

def find_image_case_insensitive(word, images_dir="images"):
    """Ищет картинку без учёта регистра"""
    if not os.path.exists(images_dir):
        return None
    for ext in ['.webrp', '.png', '.jpg', '.jpeg', '.webp']:
        for f in os.listdir(images_dir):
            if f.lower() == f"{word}{ext}".lower():
                return os.path.join(images_dir, f)
    return None
