import csv
import random
import re

from src.db import DB_PATH, get_stats, make_word_key

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


def pick_words(words, n=10, lesson=None, db_path=DB_PATH):
    """從題庫選出 n 個字出題，弱點字優先"""
    # 檢查輸入
    if not isinstance(n, int) or n <= 0:
        return {"ok": False, "error": "n 必須是正整數"}

    # 只留下指定課的字（沒指定就全部）
    candidates = []
    for w in words:
        if lesson is None or w["lesson"] == lesson:
            candidates.append(w)
    if not candidates:
        return {"ok": False, "error": f"第 {lesson} 課沒有任何單字"}

    # 從資料庫拿作答統計
    stats = get_stats(lesson=lesson, db_path=db_path)
    if not stats["ok"]:
        return stats    # 資料庫出錯，直接把錯誤往上回報

    weak = set(stats["weak_words"])
    mastered = set(stats["mastered_words"])
    practiced = set(stats["practiced_words"])

    # 把每個字分到四個組
    weak_group = []       # 1. 弱點字
    new_group = []        # 2. 還沒考過的字
    review_group = []     # 3. 考過但還不熟
    mastered_group = []   # 4. 已經熟練
    for w in candidates:
        key = make_word_key(w)
        if key in weak:
            weak_group.append(w)
        elif key not in practiced:
            new_group.append(w)
        elif key in mastered:
            mastered_group.append(w)
        else:
            review_group.append(w)

    # 每組內部先打亂，避免每次都考一樣的順序
    random.shuffle(weak_group)
    random.shuffle(new_group)
    random.shuffle(review_group)
    random.shuffle(mastered_group)

    # 依優先順序拿，拿滿 n 個就停
    picked = []
    groups = [
        ("弱點", weak_group),
        ("新字", new_group),
        ("複習", review_group),
        ("已熟練", mastered_group),
    ]
    for reason, group in groups:
        for w in group:
            if len(picked) >= n:
                break
            picked.append({"word": w, "word_key": make_word_key(w), "reason": reason})

    return {"ok": True, "picked": picked, "total_candidates": len(candidates)}


if __name__ == "__main__":
    from pathlib import Path
    from src.db import init_db, record_result

    # 1. 讀單字表
    result = load_vocab("data/vocab_L5-6.csv")
    words = result["words"]
    print(f"讀到 {len(words)} 個字，{len(result['errors'])} 個錯誤")

    # 2. 準備測試資料庫：食べます 是弱點，パン 已熟練
    test_db = Path("data/test.db")
    test_db.unlink(missing_ok=True)
    init_db(test_db)
    record_result("6:食べます", 6, "食べました", False, "past_form", test_db)
    record_result("6:食べます", 6, "食る", False, "okurigana", test_db)
    for i in range(3):
        record_result("6:パン", 6, "パン", True, None, test_db)

    # 3. 從第 6 課選 5 個字：食べます 應該排第一，パン 不應該出現
    r = pick_words(words, n=5, lesson=6, db_path=test_db)
    for item in r["picked"]:
        print(item["reason"], item["word_key"])

    # 4. 錯誤情況
    print(pick_words(words, n=0, db_path=test_db))
    print(pick_words(words, n=5, lesson=9, db_path=test_db))