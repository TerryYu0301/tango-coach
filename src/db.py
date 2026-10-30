import sqlite3
from datetime import datetime
from pathlib import Path

# 資料庫檔案的位置
DB_PATH = Path("data/tango.db")

# 弱點與熟練的判斷標準（之後會搬到 config.py）
WEAK_WINDOW = 3       # 看每個字最近 3 次作答
WEAK_THRESHOLD = 2    # 最近 3 次裡錯 2 次以上 → 弱點
MASTERED_STREAK = 3   # 最近連續答對 3 次 → 熟練


def make_word_key(word):
    """把一個單字變成唯一代號，例如 '6:食べます'；沒有漢字就用假名，例如 '6:パン'"""
    if word["kanji"]:
        name = word["kanji"]
    else:
        name = word["kana"][0]
    return f"{word['lesson']}:{name}"


def init_db(db_path=DB_PATH):
    """建立 attempts 資料表（已經存在就不會重建）"""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            word_key    TEXT    NOT NULL,
            lesson      INTEGER NOT NULL,
            user_answer TEXT,
            is_correct  INTEGER NOT NULL,
            error_type  TEXT,
            created_at  TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def record_result(word_key, lesson, user_answer, is_correct,
                  error_type=None, db_path=DB_PATH):
    """寫入一筆作答紀錄"""
    # 先檢查輸入，有問題就回傳錯誤，不寫進資料庫
    if not word_key:
        return {"ok": False, "error": "word_key 不能是空的"}
    if not isinstance(is_correct, bool):
        return {"ok": False, "error": "is_correct 必須是 True 或 False"}

    now = datetime.now().isoformat(timespec="seconds")   # 例如 2026-10-30T21:30:00

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.execute(
            "INSERT INTO attempts (word_key, lesson, user_answer, is_correct, error_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (word_key, lesson, user_answer, int(is_correct), error_type, now),
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return {"ok": True, "id": new_id}
    except sqlite3.Error as e:
        return {"ok": False, "error": f"資料庫錯誤：{e}"}


def get_stats(lesson=None, db_path=DB_PATH):
    """統計作答紀錄。lesson=None 代表統計全部課"""
    try:
        conn = sqlite3.connect(db_path)
        if lesson is None:
            rows = conn.execute(
                "SELECT word_key, is_correct FROM attempts ORDER BY id DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT word_key, is_correct FROM attempts WHERE lesson = ? ORDER BY id DESC",
                (lesson,),
            ).fetchall()
        conn.close()
    except sqlite3.Error as e:
        return {"ok": False, "error": f"資料庫錯誤：{e}"}

    # rows 長這樣：[("6:パン", 1), ("6:食べます", 0), ...]，新的在前面
    total = len(rows)
    correct = 0
    recent = {}   # 每個字最近幾次的結果，例如 {"6:食べます": [1, 0, 0]}

    for word_key, is_correct in rows:
        correct += is_correct
        if word_key not in recent:
            recent[word_key] = []
        if len(recent[word_key]) < WEAK_WINDOW:
            recent[word_key].append(is_correct)

    weak_words = []
    mastered_words = []
    for word_key, results in recent.items():
        wrong_count = results.count(0)
        if wrong_count >= WEAK_THRESHOLD:
            weak_words.append(word_key)
        if len(results) >= MASTERED_STREAK and wrong_count == 0:
            mastered_words.append(word_key)

    if total > 0:
        accuracy = round(correct / total, 2)
    else:
        accuracy = None

    return {
        "ok": True,
        "total_attempts": total,
        "accuracy": accuracy,
        "words_practiced": len(recent),
        "weak_words": weak_words,
        "mastered_words": mastered_words,
        "practiced_words": list(recent.keys()),
    }


if __name__ == "__main__":
    test_db = Path("data/test.db")
    test_db.unlink(missing_ok=True)      # 每次測試都從空的資料庫開始
    init_db(test_db)

    # 食べます：錯、錯、對 → 最近 3 次錯 2 次 → 弱點
    record_result("6:食べます", 6, "食べました", False, "past_form", test_db)
    record_result("6:食べます", 6, "食る", False, "okurigana", test_db)
    record_result("6:食べます", 6, "食べる", True, None, test_db)

    # パン：連續答對 3 次 → 熟練
    for i in range(3):
        record_result("6:パン", 6, "パン", True, None, test_db)

    # 故意傳錯的參數 → 應該回傳錯誤，而不是當掉
    print(record_result("", 6, "x", True, db_path=test_db))
    print(record_result("6:水", 6, "みず", "yes", db_path=test_db))

    # 統計全部，以及只統計第 5 課（沒有紀錄）
    print(get_stats(db_path=test_db))
    print(get_stats(lesson=5, db_path=test_db))