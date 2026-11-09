"""
所有可以調整的設定都集中在這裡。
要改規則（例如重試次數、弱點標準），只要改這個檔案，其他程式碼都不用動。
"""
from pathlib import Path

# ---------- 檔案位置 ----------
VOCAB_PATH = "data/vocab_L5-6.csv"                    # 單字表
DB_PATH = Path("data/tango.db")                       # 作答紀錄資料庫
EXHAUSTED_FILE = Path("data/exhausted_models.json")   # 今天額度已用完的模型
LOG_DIR = Path("logs")                                # 執行紀錄（trace）

# ---------- 弱點判斷 ----------
WEAK_WINDOW = 3          # 看每個字最近 3 次作答
WEAK_THRESHOLD = 2       # 最近 3 次裡錯 2 次以上 → 弱點
MASTERED_STREAK = 3      # 最近連續答對 3 次 → 熟練

# ---------- 批改與重試界線 ----------
MAX_ANSWER_ATTEMPTS = 1  # 每一題只能作答 1 次（答錯會公布答案，不能重答）
MAX_EXAMPLE_RETRY = 3    # 找例句最多試 3 種寫法（漢字、原形、假名）
MAX_LLM_RETRY = 2        # 同一個模型遇到 503 時最多再試 2 次
LLM_TIMEOUT_MS = 30_000  # 每次呼叫 LLM 最多等 30 秒（毫秒）
MAX_REACT_STEPS = 10     # 使用者每說一句話，Agent 最多跑 10 步
TATOEBA_TIMEOUT_S = 10   # 呼叫 Tatoeba 最多等 10 秒（秒）

# ---------- LLM 模型 ----------
# 依序嘗試：遇到 429（額度用完）或 404（不能用）就自動換下一個
MODELS = [
    "gemini-3.6-flash",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]