import csv
import re

# kana 欄只能有平假名、片假名、長音符號和 /
KANA_PATTERN = re.compile(r"^[\u3040-\u309F\u30A0-\u30FF/]+$")
REQUIRED_COLUMNS = {"kanji", "kana", "meaning", "lesson"}


def load_vocab(path):
    """讀取單字表 CSV，回傳 {"words": [...], "errors": [...]}"""
    words = []
    errors = []
    seen = set()

    try:
        f = open(path, encoding="utf-8-sig")
    except FileNotFoundError:
        return {"words": [], "errors": [f"找不到檔案：{path}"]}

    with f:
        reader = csv.DictReader(f)

        # 檢查欄位名稱有沒有缺
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            return {"words": [], "errors": [f"CSV 缺少欄位：{', '.join(sorted(missing))}"]}

        # 第 1 行是標題，所以資料從第 2 行開始算
        for line_no, row in enumerate(reader, start=2):
            kanji = (row["kanji"] or "").strip()
            kana = (row["kana"] or "").strip()
            meaning = (row["meaning"] or "").strip()
            lesson = (row["lesson"] or "").strip()
            note = (row.get("note") or "").strip()

            # 檢查 1：必填欄位不能空白
            if not kana or not meaning or not lesson:
                errors.append(f"第 {line_no} 行：kana、meaning、lesson 不能空白")
                continue

            # 檢查 2：kana 欄只能是假名
            if not KANA_PATTERN.match(kana):
                errors.append(f"第 {line_no} 行：kana「{kana}」含有非假名的字元")
                continue

            # 檢查 3：lesson 必須是數字
            if not lesson.isdigit():
                errors.append(f"第 {line_no} 行：lesson「{lesson}」不是數字")
                continue

            # 檢查 4：同一課不能有重複的字
            key = (kanji or kana, int(lesson))
            if key in seen:
                errors.append(f"第 {line_no} 行：「{kanji or kana}」在第 {lesson} 課重複了")
                continue
            seen.add(key)

            words.append({
                "kanji": kanji,
                "kana": kana.split("/"),
                "meaning": [m.strip() for m in meaning.split("/")],
                "lesson": int(lesson),
                "note": note,
            })

    return {"words": words, "errors": errors}


if __name__ == "__main__":
    result = load_vocab("data/vocab_L5-6.csv")
    print(f"讀到 {len(result['words'])} 個字，{len(result['errors'])} 個錯誤")
    for w in result["words"][:5]:      # 只印前 5 個看看
        print(w)
    for e in result["errors"]:
        print("錯誤：", e)