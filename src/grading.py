import re
import unicodedata

# ---------- 文字處理的小工具 ----------

KANJI_PATTERN = re.compile(r"[\u4e00-\u9fff々]")
ROMAJI_PATTERN = re.compile(r"[A-Za-z]")
PUNCTUATION = "。、．，,.!?！？"

# 小字 → 大字 的對照（用來判斷促音、拗音寫錯）
SMALL_TO_BIG = str.maketrans("ぁぃぅぇぉっゃゅょゎ", "あいうえおつやゆよわ")

# い段 → う段（五段動詞：ます形變原形用，例如 いき → いく）
I_TO_U = {"い": "う", "き": "く", "ぎ": "ぐ", "し": "す", "ち": "つ",
          "に": "ぬ", "び": "ぶ", "み": "む", "り": "る"}
E_ROW = set("えけげせぜてでねへべぺめれ")

# 雖然是い段，但其實是一段動詞（原形是 +る）
ICHIDAN_I_ROW = {"みます", "おきます", "かります", "います",
                 "あびます", "できます", "おります"}
# 雖然結尾是「します」，但其實是五段動詞（原形是 〜す）
GODAN_SU = {"はなします", "かします", "だします", "けします", "おします",
            "さします", "わたします", "かえします", "さがします", "なくします"}


def normalize(text):
    """忽略空白、全形半形、句尾標點"""
    text = unicodedata.normalize("NFKC", text)   # 全形英數 → 半形、半形片假名 → 全形
    text = "".join(text.split())                  # 去掉所有空白
    return text.strip(PUNCTUATION)


def to_hiragana(text):
    """片假名 → 平假名（長音符號ー不變）"""
    result = ""
    for ch in text:
        if "ァ" <= ch <= "ヶ":
            result += chr(ord(ch) - 0x60)
        else:
            result += ch
    return result


def kanji_only(text):
    """只留下漢字，例如 食べます → 食"""
    return "".join(KANJI_PATTERN.findall(text))


def masu_to_plain(kanji, kana):
    """把ます形變成原形，回傳 (漢字原形, 假名原形)；不是ます形就回傳 None"""
    if not kana.endswith("ます"):
        return None

    if kana == "きます":                                   # 来ます → 来る（不規則）
        return (kanji[:-2] + "る" if kanji else ""), "くる"

    if kana.endswith("します") and kana not in GODAN_SU:  # します、勉強します → する
        kind = "suru"
    elif kana[-3] in E_ROW or kana in ICHIDAN_I_ROW:        # 食べます、見ます → +る
        kind = "ichidan_like"
    else:                                                  # 行きます → 行く
        kind = "godan"

    def convert(s):
        if not s:
            return ""
        if kind == "suru":
            return s[:-3] + "する"
        if kind == "ichidan_like":
            return s[:-2] + "る"
        return s[:-3] + I_TO_U.get(s[-3], s[-3])

    return convert(kanji), convert(kana)


def long_vowel_skeleton(text):
    """去掉容易寫錯的長音、促音（ー う っ），用來比對「只差在長音或促音」"""
    text = to_hiragana(text).translate(SMALL_TO_BIG)
    for ch in "ーうつ":
        text = text.replace(ch, "")
    return text


# ---------- 批改主程式 ----------

def check_answer(word, user_answer, direction="zh_to_ja"):
    """
    批改一題。
    direction="zh_to_ja"：看中文，回答日文
    direction="ja_to_zh"：看日文，回答中文
    回傳：
      correct = True / False：規則判斷得出來
      correct = None：規則判斷不了，之後交給 LLM（Step 5）
    """
    answer = normalize(user_answer or "")
    if not answer:
        return {"ok": False, "error": "答案是空的"}

    if direction == "ja_to_zh":
        return _check_meaning(word, answer)
    if direction != "zh_to_ja":
        return {"ok": False, "error": f"不支援的題型：{direction}"}

    kanji = word["kanji"]
    kana_list = word["kana"]
    shown = kanji or kana_list[0]

    def result(correct, error_type, explanation):
        return {"ok": True, "correct": correct, "error_type": error_type,
                "explanation": explanation, "expected": shown}

    # 1. 完全符合課本（漢字或任何一種假名寫法）
    accepted = set(kana_list)
    if kanji:
        accepted.add(kanji)
    if answer in accepted:
        return result(True, None, "正確！")

    # 2. 動詞原形也算對
    plain_kanji, plain_kana = None, None
    converted = masu_to_plain(kanji, kana_list[0])
    if converted:
        plain_kanji, plain_kana = converted
        if answer in (plain_kanji, plain_kana):
            return result(True, "plain_form",
                          f"正確！你寫的是原形，課本是ます形「{shown}」。"
                          f"意思一樣，ます形比較有禮貌，原形用在朋友之間或字典。")

    # 3. 用羅馬拼音
    if ROMAJI_PATTERN.search(answer):
        return result(False, "romaji", f"請用假名或漢字作答，不要用羅馬拼音。正確答案：{shown}")

    # 4. 過去式、否定形
    if kana_list[0].endswith("ます"):
        stems = [kana_list[0][:-2]]
        if kanji:
            stems.append(kanji[:-2])
        for stem in stems:
            for ending, name in [("ませんでした", "過去否定"), ("ました", "過去式"), ("ません", "否定形")]:
                if answer == stem + ending:
                    return result(False, "conjugation",
                                  f"你寫的是{name}「{answer}」，題目要的是「{shown}」（ます形）。")
        for base in [plain_kana, plain_kanji]:
            if base and answer[0] == base[0] and answer.endswith(("た", "だ", "ない", "なかった")):
                return result(False, "conjugation",
                              f"你寫的看起來是過去式或否定形「{answer}」，題目要的是「{shown}」（ます形）。")

    # 下面幾項只檢查「全部用假名」的答案
    if not KANJI_PATTERN.search(answer):
        all_kana = list(kana_list)
        if plain_kana:
            all_kana.append(plain_kana)
        for correct_kana in all_kana:
            # 5. 平假名、片假名寫反
            if to_hiragana(answer) == to_hiragana(correct_kana):
                return result(False, "kana_type",
                              f"平假名和片假名寫反了。正確寫法：{correct_kana}")
            # 6. 促音、拗音的小字寫錯
            if answer.translate(SMALL_TO_BIG) == correct_kana.translate(SMALL_TO_BIG):
                return result(False, "small_kana",
                              f"小字（っ ゃ ゅ ょ）寫錯了。正確寫法：{correct_kana}")
            # 7. 長音、促音漏寫或多寫
            if long_vowel_skeleton(answer) == long_vowel_skeleton(correct_kana):
                return result(False, "long_vowel",
                              f"長音或促音寫錯了。正確寫法：{correct_kana}")

    # 8. 漢字對了，但送假名錯
    if KANJI_PATTERN.search(answer) and kanji:
        for k in [kanji, plain_kanji]:
            if k and kanji_only(answer) == kanji_only(k):
                return result(False, "okurigana",
                              f"漢字對了，但送假名（漢字後面的假名）寫錯。正確寫法：{k}")

    # 9. 規則判斷不了 → 交給 LLM
    return result(None, "needs_llm", "規則無法判斷，需要 LLM 進一步判斷。")


def _check_meaning(word, answer):
    """看日文、回答中文：符合課本的任何一個意思就算對"""
    shown = word["kanji"] or word["kana"][0]
    meanings = [normalize(m) for m in word["meaning"]]
    expected = "／".join(word["meaning"])
    if answer in meanings:
        return {"ok": True, "correct": True, "error_type": None,
                "explanation": "正確！", "expected": expected}
    # 不在清單上，可能是同義詞（例如「腳踏車」vs「單車」），交給 LLM
    return {"ok": True, "correct": None, "error_type": "needs_llm",
            "explanation": f"「{answer}」不在「{shown}」的課本意思裡，需要 LLM 判斷是不是同義詞。",
            "expected": expected}


if __name__ == "__main__":
    from src.tools import load_vocab

    words = load_vocab("data/vocab_L5-6.csv")["words"]
    by_name = {}
    for w in words:
        by_name[w["kanji"] or w["kana"][0]] = w

    tests = [
        ("食べます", "食べます"),      # 完全正確（漢字）
        ("食べます", "たべます"),      # 完全正確（假名）
        ("食べます", " 食べます 。"),  # 多了空白和句點 → 忽略
        ("食べます", "食べる"),        # 原形 → 對，附說明
        ("行きます", "いく"),          # 原形（五段）
        ("来ます", "くる"),            # 原形（不規則）
        ("します", "する"),            # 原形（不規則）
        ("見ます", "みる"),            # 原形（い段的一段動詞）
        ("食べます", "taberu"),        # 羅馬拼音 → 錯
        ("食べます", "食べました"),    # 過去式 → 錯
        ("飲みます", "のみません"),    # 否定形 → 錯
        ("食べます", "食べた"),        # 原形過去 → 錯
        ("スーパー", "すーぱー"),      # 平片假名寫反 → 錯
        ("14日", ""),                  # 空答案 → 回傳錯誤
        ("14日", "じゆうよつか"),      # 小字寫錯 → 錯
        ("飛行機", "ひこき"),          # 長音漏寫 → 錯
        ("学校", "がこう"),            # 促音漏寫 → 錯
        ("帰ります", "帰ます"),        # 送假名錯 → 錯
        ("お酒", "さけ"),              # お可省略 → 對
        ("自転車", "ちゃり"),          # 規則判斷不了 → 交給 LLM
    ]
    for name, ans in tests:
        r = check_answer(by_name[name], ans)
        if r["ok"]:
            print(f"[{name}] 答「{ans}」→ {r['correct']}  {r['error_type']}  {r['explanation']}")
        else:
            print(f"[{name}] 答「{ans}」→ 錯誤：{r['error']}")

    print(check_answer(by_name["自転車"], "腳踏車", direction="ja_to_zh"))
    print(check_answer(by_name["自転車"], "單車", direction="ja_to_zh"))