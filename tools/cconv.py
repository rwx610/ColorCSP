#!/usr/bin/env python3
"""
cconv.py - конвертер цветовых палитр

Использование:
  cconv <input_file> [output_file] [--cut]

Аргументы:
  input_file    - входной файл (обязательный)
  output_file   - выходной JSON (по умолчанию: cconv_output.json)
  -c, --cut     - урезанный формат (только HEX+RGB+HSL)

Форматы входных файлов:
  • JSON: [{"color": "...", "name": "...", "id": "..."}, ...]
  • Текстовый: одна строка = один цвет (начало строки - HEX)
"""

import argparse
import json
import math
from pathlib import Path


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """#RRGGBB или RRGGBB -> (255, 255, 255)"""
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hsl(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """RGB -> HSL (H:0-360, S:0-100, L:0-100)"""
    r, g, b = [x / 255.0 for x in rgb]
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2

    if mx == mn:
        h = s = 0.0
    else:
        d = mx - mn
        s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r:
            h = (g - b) / d + (6 if g < b else 0)
        elif mx == g:
            h = (b - r) / d + 2
        else:
            h = (r - g) / d + 4
        h /= 6

    return (round(h * 360, 1), round(s * 100, 1), round(l * 100, 1))


def rgb_to_hsv(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """RGB -> HSV (H:0-360, S:0-100, V:0-100)"""
    r, g, b = [x / 255.0 for x in rgb]
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn

    v = mx * 100
    s = 0 if mx == 0 else (d / mx) * 100

    if d == 0:
        h = 0
    else:
        if mx == r:
            h = ((g - b) / d) * 60
            if h < 0:
                h += 360
        elif mx == g:
            h = ((b - r) / d + 2) * 60
        else:
            h = ((r - g) / d + 4) * 60

    return (round(h, 1), round(s, 1), round(v, 1))


def rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """RGB -> CIELAB"""
    r, g, b = [x / 255.0 for x in rgb]

    r = r / 12.92 if r <= 0.04045 else ((r + 0.055) / 1.055) ** 2.4
    g = g / 12.92 if g <= 0.04045 else ((g + 0.055) / 1.055) ** 2.4
    b = b / 12.92 if b <= 0.04045 else ((b + 0.055) / 1.055) ** 2.4

    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041

    x /= 0.95047
    z /= 1.08883

    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)

    l = max(0, 116 * fy - 16)
    a = 500 * (fx - fy)
    b_lab = 200 * (fy - fz)

    return (round(l, 2), round(a, 2), round(b_lab, 2))


def rgb_to_cmyk(rgb: tuple[int, int, int]) -> tuple[float, float, float, float]:
    """RGB -> CMYK (0-100%)"""
    r, g, b = [x / 255.0 for x in rgb]

    if (r, g, b) == (0, 0, 0):
        return (0.0, 0.0, 0.0, 100.0)

    k = 1 - max(r, g, b)

    if k == 1:
        return (0.0, 0.0, 0.0, 100.0)

    c = (1 - r - k) / (1 - k)
    m = (1 - g - k) / (1 - k)
    y = (1 - b - k) / (1 - k)

    return (round(c * 100, 1), round(m * 100, 1), round(y * 100, 1), round(k * 100, 1))


def normalize_hex(color_str: str) -> str:
    """Приводит к формату #RRGGBB (нижний регистр)"""
    import re

    hex_clean = re.sub(r"[^0-9A-Fa-f]", "", color_str)

    if len(hex_clean) == 3:
        hex_clean = "".join(c * 2 for c in hex_clean)
    elif len(hex_clean) != 6:
        return None

    return f"#{hex_clean.lower()}"


def extract_hex(text: str) -> str:
    """Извлекает HEX цвет из начала строки"""
    text = text.lstrip(";#|: \t")

    for i in range(min(7, len(text)), 0, -1):
        test_str = text[:i]
        hex_color = normalize_hex(test_str)
        if hex_color:
            return hex_color

    return None


def parse_json_file(file_path: str) -> list[dict]:
    """Парсит JSON файл со структурой [{"id", "name", "color"}, ...]"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    colors = []
    for i, item in enumerate(data, 1):
        if not isinstance(item, dict):
            continue

        # Ищем цвет
        color_value = None
        for key in ["color", "hex", "value"]:
            if key in item:
                color_value = item[key]
                break

        if not color_value:
            continue

        hex_color = normalize_hex(color_value)
        if not hex_color:
            continue

        color_id = item.get("id", f"{i:03d}")
        color_name = item.get("name", hex_color)

        colors.append(
            {"id": str(color_id), "name": str(color_name), "color": hex_color}
        )

    return colors


def parse_text_file(file_path: str) -> list[dict]:
    """Парсит текстовый файл: одна строка = один цвет"""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    colors = []
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if not parts:
            continue

        first_part = parts[0]
        hex_color = extract_hex(first_part)

        if not hex_color:
            continue

        name_parts = parts[1:]
        color_name = " ".join(name_parts) if name_parts else hex_color

        colors.append({"id": f"{i:03d}", "name": color_name, "color": hex_color})

    return colors


def convert_file(input_file: str, output_file: str, cut: bool = False):
    """Основная функция конвертации"""
    input_path = Path(input_file)

    if not input_path.exists():
        print(f"❌ File not found: {input_file}")
        return False

    # Выбираем парсер
    if input_path.suffix.lower() == ".json":
        colors = parse_json_file(input_file)
    else:
        colors = parse_text_file(input_file)

    if not colors:
        print(f"❌ Colors not found in: {input_file}")
        return False

    # Конвертируем
    result = []
    for item in colors:
        try:
            hex_color = item["color"]
            rgb = hex_to_rgb(hex_color)

            color_dict = {
                "id": item["id"],
                "name": item["name"],
                "hex": hex_color,
                "rgb": list(rgb),
                "rgb_norm": [round(x / 255.0, 4) for x in rgb],
                "hsl": list(rgb_to_hsl(rgb)),
            }

            if not cut:
                color_dict.update(
                    {
                        "hsv": list(rgb_to_hsv(rgb)),
                        "lab": list(rgb_to_lab(rgb)),
                        "cmyk": list(rgb_to_cmyk(rgb)),
                        "luminance": round(
                            0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2], 1
                        ),
                        "is_light": 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
                        > 128,
                    }
                )

            result.append(color_dict)

        except Exception as e:
            print(f"⚠️ Warning: Skipped color {item.get('name', '?')}: {e}")

    # Сохраняем
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Выводим информацию
    print(f"Converted: {len(result)} colors")
    print(f"Saved to: {output_file} ({'cut' if cut else 'full'})")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Конвертер цветовых палитр",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  cconv colors.txt                     # Текстовый файл -> cconv_output.json (полный формат)
  cconv palette.json output.json       # JSON файл -> output.json (полный формат)
  cconv colors.txt --cut               # Текстовый файл -> cconv_output.json (урезанный формат)
  cconv colors.txt my_palette.json -c  # Текстовый файл -> my_palette.json (урезанный формат)
        """,
    )

    # Обязательный аргумент
    parser.add_argument("input_file", help="Входной файл (.json, .txt, .csv и т.д.)")

    # Необязательный аргумент
    parser.add_argument(
        "output_file",
        nargs="?",  # 0 или 1 аргумент
        default="cconv_output.json",
        help="Выходной JSON файл (по умолчанию: cconv_output.json)",
    )

    # Флаг
    parser.add_argument(
        "-c",
        "--cut",
        action="store_true",
        help="Урезанный формат (только HEX, RGB, HSL)",
    )

    args = parser.parse_args()

    # Проверяем входной файл
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"❌ File not found: {args.input_file}")
        return 1

    # Конвертируем
    success = convert_file(
        input_file=args.input_file, output_file=args.output_file, cut=args.cut
    )

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
