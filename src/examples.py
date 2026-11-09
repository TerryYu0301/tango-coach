"""
search_examples：從 Tatoeba（開放的多語例句資料庫）找含有這個單字的日文例句，附中文翻譯。
API 說明：https://en.wiki.tatoeba.org/articles/show/api-migration-v1
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from src.config import MAX_EXAMPLE_RETRY, TATOEBA_TIMEOUT_S
from src.grading import masu_to_plain

TATOEBA_URL = "https://api.tatoeba.org/v1/sentences"


def _search_tatoeba(query):
    """用一個關鍵字查 Tatoeba，回傳 {"ok": True, "items": [...]} 或 {"ok": False, "error": ...}"""
    params = urllib.parse.urlencode({
        "lang": "jpn",              # 只要日文句子
        "q": query,                 # 關鍵字
        "trans:lang": "cmn",        # 只要有中文翻譯的句子
        "showtrans:lang": "cmn",    # 翻譯只顯示中文
        "sort": "words",            # 短句排前面
    })
    try:
        with urllib.request.urlopen(f"{TATOEBA_URL}?{params}", timeout=TATOEBA_TIMEOUT_S) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"Tatoeba 回傳錯誤 {e.code}"}
    except (urllib.error.URLError, TimeoutError) as e:
        return {"ok": False, "error": f"連不上 Tatoeba：{e}"}
    except json.JSONDecodeError:
        return {"ok": False, "error": "Tatoeba 回傳的不是 JSON"}

    items = data.get("data", []) if isinstance(data, dict) else []
    return {"ok": True, "items": items}


def _find_chinese(translations):
    """從 translations 裡找出第一個中文翻譯（不管它包了幾層 list）"""
    if isinstance(translations, dict):
        if translations.get("lang") == "cmn" and translations.get("text"):
            return translations["text"]
        return None
    if isinstance(translations, list):
        for t in translations:
            found = _find_chinese(t)
            if found:
                return found
    return None


def search_examples(word, max_results=2):
    """
    找含有這個單字的例句。依序用「漢字 → 原形 → 假名」搜尋，最多試 MAX_EXAMPLE_RETRY 次。
    優先選「有禮貌形（です／ます）」而且比較短的句子。
    """
    queries = []
    if word["kanji"]:
        queries.append(word["kanji"])
    converted = masu_to_plain(word["kanji"], word["kana"][0])
    if converted:
        plain_kanji, plain_kana = converted
        queries.append(plain_kanji or plain_kana)     # 例句裡動詞常常是原形
    queries.append(word["kana"][0])

    # 去掉重複的關鍵字，最多試 MAX_EXAMPLE_RETRY 次
    unique = []
    for q in queries:
        if q and q not in unique:
            unique.append(q)
    unique = unique[:MAX_EXAMPLE_RETRY]

    last_error = None
    for q in unique:
        r = _search_tatoeba(q)
        if not r["ok"]:
            last_error = r["error"]
            continue

        candidates = []
        for item in r["items"]:
            text = item.get("text", "")
            chinese = _find_chinese(item.get("translations"))
            if q in text and chinese:
                polite = ("です" in text) or ("ます" in text)
                candidates.append({"text": text, "chinese": chinese, "polite": polite})

        if candidates:
            candidates.sort(key=lambda c: (not c["polite"], len(c["text"])))   # 禮貌形優先，再來是短句
            examples = []
            for c in candidates[:max_results]:
                examples.append({
                    "japanese": c["text"].replace(q, f"【{q}】"),     # 把單字標出來
                    "chinese": c["chinese"],
                })
            return {"ok": True, "query": q, "examples": examples, "source": "Tatoeba (CC BY 2.0 FR)"}

    if last_error:
        return {"ok": False, "error": last_error}
    return {"ok": False, "error": f"Tatoeba 找不到含有「{word['kanji'] or word['kana'][0]}」又有中文翻譯的例句"}


if __name__ == "__main__":
    from src.tools import load_vocab

    words = load_vocab("data/vocab_L5-6.csv")["words"]
    by_name = {}
    for w in words:
        by_name[w["kanji"] or w["kana"][0]] = w

    for name in ["食べます", "学校", "サッカー"]:
        print(f"--- {name} ---")
        print(json.dumps(search_examples(by_name[name]), ensure_ascii=False, indent=2))