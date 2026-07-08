"""
Сжатие картин > 1KB до 700-800KB и удаление картин < 100KB.
"""

import json
import os
from io import BytesIO

from PIL import Image

DIR = os.path.expanduser("~/Desktop/paintings")
JSON_PATH = os.path.join(DIR, "monet_paintings.json")
TARGET_MIN = 700 * 1024
TARGET_MAX = 800 * 1024
MIN_SIZE = 100 * 1024
MIN_VALID = 1 * 1024


def compress_image(filepath):
    """Сжимает JPEG до 700-800KB. Возвращает статус."""
    size = os.path.getsize(filepath)
    if size < MIN_VALID:
        return "BROKEN"
    if TARGET_MIN <= size <= TARGET_MAX:
        return "OK_SKIP"
    if size < MIN_SIZE:
        return "DELETE"
    if size < TARGET_MIN:
        return "OK_SMALL"

    try:
        img = Image.open(filepath)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        w, h = img.size

        best_data = None
        for quality in range(95, 65, -3):
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            data = buf.getvalue()
            if len(data) <= TARGET_MAX:
                best_data = data
                break
            if best_data is None or len(data) < len(best_data):
                best_data = data

        if best_data is None or len(best_data) > TARGET_MAX:
            for scale in [0.9, 0.8, 0.7, 0.6, 0.5]:
                nw, nh = int(w * scale), int(h * scale)
                resized = img.resize((nw, nh), Image.LANCZOS)
                for quality in range(85, 60, -5):
                    buf = BytesIO()
                    resized.save(buf, format="JPEG", quality=quality, optimize=True)
                    data = buf.getvalue()
                    if TARGET_MIN <= len(data) <= TARGET_MAX:
                        best_data = data
                        break
                    if best_data is None or len(data) < len(best_data):
                        best_data = data
                if best_data and TARGET_MIN <= len(best_data) <= TARGET_MAX:
                    break

        if best_data:
            with open(filepath, "wb") as f:
                f.write(best_data)
            new_size = os.path.getsize(filepath)
            return f"COMPRESSED {size // 1024}KB -> {new_size // 1024}KB"
        else:
            return f"SKIP_LARGE {size // 1024}KB"

    except Exception as e:
        return f"ERROR: {e}"


def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Total in JSON: {len(data)}")

    to_keep = []
    stats = {"kept": 0, "compressed": 0, "deleted": 0, "errors": 0}

    for i, item in enumerate(data):
        filename = item["filename"]
        filepath = os.path.join(DIR, filename)

        if not os.path.exists(filepath):
            stats["deleted"] += 1
            continue

        result = compress_image(filepath)

        if result in ("DELETE", "BROKEN"):
            if os.path.exists(filepath):
                os.remove(filepath)
            stats["deleted"] += 1
            if stats["deleted"] <= 3:
                print(f"  DEL: {filename}")
        elif result.startswith("COMPRESSED"):
            stats["compressed"] += 1
            to_keep.append(item)
            if stats["compressed"] <= 3:
                print(f"  {result}")
        elif result.startswith("ERROR"):
            stats["errors"] += 1
            to_keep.append(item)
            print(f"  {result}: {filename}")
        else:
            stats["kept"] += 1
            to_keep.append(item)

        if (i + 1) % 200 == 0:
            print(f"  Progress: {i + 1}/{len(data)}")

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(to_keep, f, ensure_ascii=False, indent=2)

    print(f"\nDone!")
    print(f"  Kept (already OK): {stats['kept']}")
    print(f"  Compressed:        {stats['compressed']}")
    print(f"  Deleted (<100KB):  {stats['deleted']}")
    print(f"  Errors:            {stats['errors']}")
    print(f"  Final JSON count:  {len(to_keep)}")


if __name__ == "__main__":
    main()
