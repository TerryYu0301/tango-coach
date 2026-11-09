# Tango Coach 日文單字小考練習 Agent

## 專案簡介

Tango Coach 是一個幫助準備日文單字小考的 AI Agent。使用者匯入課本的單字表後，Agent 會出題、批改，並記錄每次作答，下次優先出使用者答錯過的字。答錯時，Agent 會從 Tatoeba 例句庫找例句和中文翻譯，幫助記憶。

設計原則是「LLM 負責說話，程式負責判分」：對錯由規則和程式決定，LLM 只負責理解使用者的話、決定下一步，以及說明結果。

## 功能

- 匯入課本單字表（CSV），依弱點優先出題
- 規則優先批改，規則判斷不了才交給 LLM，並要求附上理由
- 用 SQLite 記錄每次作答，統計正確率、弱點字、熟練字
- 答錯時從 Tatoeba 找例句和中文翻譯
- 每一步都寫入執行紀錄（trace），方便除錯與檢查

## 系統架構

採用 ReAct（Reasoning + Acting）迴圈：

- 使用者輸入後，LLM 判斷下一步要做什麼
- 如果需要工具，LLM 提出要呼叫的工具和參數（Action），由程式執行工具，再把結果（Observation）交回給 LLM
- 重複上面的步驟，直到 LLM 不需要工具，直接回覆使用者

檔案說明：

- src/main.py：程式入口，負責和使用者對話
- src/agent.py：ReAct 迴圈、工具定義、Guardrail、執行紀錄
- src/tools.py：load_vocab、pick_words
- src/grading.py：規則批改 check_answer
- src/llm.py：呼叫 Gemini、模型切換與重試、LLM 輔助批改
- src/db.py：SQLite 作答紀錄 record_result、get_stats
- src/examples.py：Tatoeba 例句搜尋 search_examples
- src/config.py：所有設定值，包括重試界線、弱點標準、模型清單
- data/vocab_L5-6.csv：單字表，第 5、6 課，共 100 個字

## 安裝與執行

### 事前準備

在專案資料夾建立 .env 檔案，填入 Gemini API 金鑰。這個檔案已被 .gitignore 排除，不會上傳。

    GEMINI_API_KEY=你的金鑰

### 方法一：直接執行

    python3.11 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python -m src.main

### 方法二：用 Podman 執行

    podman machine start
    podman build -t tango-coach .
    podman run -it --rm --env-file .env -v "$PWD/data:/app/data" -v "$PWD/logs:/app/logs" tango-coach

- API 金鑰在執行時用 --env-file 傳入，不會被打包進映像檔
- -v 讓作答紀錄和執行紀錄存回主機

### 使用方式

執行後輸入想做的事，例如：

- 考我第 6 課 3 題
- 我哪些字比較弱？
- 結束

作答時直接輸入日文答案，可以用漢字或假名。

## Tool 定義

LLM 可以呼叫的工具定義在 src/agent.py 的 TOOL_DECLARATIONS。所有工具統一回傳 {"ok": True, ...} 或 {"ok": False, "error": 原因}，錯誤不會讓程式中斷，而是回報給 Agent 決定下一步。

### pick_words

- 用途：選字出題，弱點字優先，順序為弱點、新字、複習、已熟練
- 輸入：n（題數）、lesson（課數，選填）
- 輸出：每題的 word_key、題目（中文意思）、提示、選題原因
- 錯誤處理：題數不是正整數、該課沒有單字、資料庫錯誤時回傳錯誤訊息

### check_answer

- 用途：批改答案，並自動記錄結果
- 輸入：word_key、user_answer、direction（選填，zh_to_ja 或 ja_to_zh）
- 輸出：是否正確、錯誤類型、說明、正確答案、由規則或 LLM 判斷
- 錯誤處理：單字不存在、空答案、LLM 無法使用、重複作答時回傳錯誤訊息

### get_stats

- 用途：查詢作答統計
- 輸入：lesson（課數，選填）
- 輸出：總題數、正確率、弱點字、熟練字
- 錯誤處理：資料庫錯誤時回傳錯誤訊息

### search_examples

- 用途：從 Tatoeba 找含有這個單字的例句
- 輸入：word_key
- 輸出：日文例句（單字以【】標示）、中文翻譯，優先選有禮貌形的短句
- 錯誤處理：連不上 Tatoeba、逾時、找不到例句時回傳錯誤訊息，不會自己編例句

### 程式內部使用的函式

以下函式由程式呼叫，LLM 不能直接使用：

- load_vocab：讀取 CSV 並檢查必填欄位、假名格式、課數、重複單字。格式錯誤的行會被跳過，並記錄是第幾行、什麼原因
- record_result：寫入作答紀錄，由 check_answer 自動呼叫，LLM 無法跳過

## 批改規則

以題目「食べます」為例。

判為正確：

- 與課本相同，漢字或假名都可以，例如 食べます、たべます
- 動詞原形，附上和ます形差別的說明，例如 食べる
- 同義詞，由 LLM 判斷並附理由，例如自転車回答「單車」

判為錯誤並附說明：

- 過去式、否定形，例如 食べました、食べません
- 長音、小字、送假名寫錯，例如 ひこき、じゆうよつか、帰ます
- 平假名和片假名寫反，例如 すーぱー
- 使用羅馬拼音，例如 taberu

忽略不計：

- 空白、全形半形、句尾標點

規則判斷不了時才呼叫 LLM。LLM 必須回傳 JSON 格式的判斷和理由，格式不符視為失敗。

## 重試與批改界線

所有數值集中在 src/config.py，修改設定不需要改其他程式碼。

- MAX_ANSWER_ATTEMPTS = 1：每題只能作答 1 次，答錯會公布答案
- MAX_EXAMPLE_RETRY = 3：找例句最多試 3 種寫法（漢字、原形、假名）
- MAX_LLM_RETRY = 2：伺服器忙碌時，同一個模型最多重試 2 次
- LLM_TIMEOUT_MS = 30000：每次呼叫 LLM 最多等 30 秒
- MAX_REACT_STEPS = 10：使用者每說一句話，Agent 最多執行 10 步
- TATOEBA_TIMEOUT_S = 10：呼叫 Tatoeba 最多等 10 秒
- WEAK_WINDOW = 3、WEAK_THRESHOLD = 2：最近 3 次作答錯 2 次以上，列為弱點
- MASTERED_STREAK = 3：最近連續答對 3 次，列為熟練

LLM 呼叫失敗時的處理方式：

- 503 伺服器忙碌：等待後重試同一個模型
- 504 逾時：不重試，直接換下一個模型
- 429 每日額度用完、404 模型不可用：記錄到 data/exhausted_models.json，當天不再使用
- 其他錯誤：不重試，直接回報

## Guardrail

用程式碼強制執行、LLM 無法跳過的規則：

- 批改一律使用使用者的原始輸入，不採用 LLM 傳給 check_answer 的版本，避免 LLM 擅自修改答案
- 每題只能作答一次，重複作答會被擋下
- 出題時只提供中文意思給 LLM，不提供答案，LLM 無法事先洩漏答案
- 批改後一定記錄，record_result 由 check_answer 自動呼叫
- ReAct 步數上限，避免 LLM 無限呼叫工具

## 使用的 LLM

使用 Google Gemini API 的免費額度。為了應對免費額度的限制，src/config.py 的 MODELS 列了多個 Flash 系列模型，依序嘗試，一個不能用就自動換下一個。

規劃文件原訂使用 GPT-4o-mini，實作時改用 Gemini 免費額度。

## 執行紀錄

每次執行會在 logs/ 產生 trace_日期_時間.jsonl，一行一筆 JSON，type 欄位代表這一筆的種類：

- user：使用者輸入
- action：LLM 決定呼叫的工具與參數
- observation：工具執行的結果
- guardrail：被 Guardrail 攔下的紀錄
- answer：給使用者的回覆
- error：錯誤

附上的執行紀錄檔：
- logs/trace_20261109_191246.jsonl：主要範例。第 6 課小考 3 題，四個工具都有使用：規則判對、規則判錯（小字寫錯）、規則判斷不了而交給 LLM 判錯，以及查詢弱點。例句搜尋遇到「找不到例句」和「連不上 Tatoeba」兩種情況，都正確回報而沒有自行編造。
- logs/trace_20261109_022619.jsonl：在 Podman 容器中執行的紀錄，紀錄時間為 UTC。
- logs/trace_20261101_163906.jsonl：失敗案例一的完整紀錄，LLM 擅自修改使用者的答案。

執行畫面：

以下為 trace_20261109_191246 的終端機輸出：

    你：考我第 6 課 3 題
      [第 1 步｜action] {"tool": "pick_words", "args": {"lesson": 6, "n": 3}, "model": "gemini-3.6-flash"}
      [第 1 步｜observation] {"tool": "pick_words", "result": {"ok": true, "questions": [{"word_key": "6:ええ", "question": "是的", "hint": "", "reason": "新字"}, {"word_key": "6:いつも", 
      [第 2 步｜answer] {"text": "第 1 題 / 共 3 題\n\n請用日文回答以下單字：\n中文意思：是的", "model": "gemini-3.6-flash"}

    Coach：第 1 題 / 共 3 題
    請用日文回答以下單字：
    中文意思：是的

    你：ええ
      [第 1 步｜action] {"tool": "check_answer", "args": {"word_key": "6:ええ", "user_answer": "ええ"}, "model": "gemini-3.6-flash"}
      [第 1 步｜observation] {"tool": "check_answer", "result": {"ok": true, "correct": true, "error_type": null, "explanation": "正確！", "expected": "ええ", "judged_by": "rule", "rec
    [llm] gemini-3.6-flash 第 1 次失敗：503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently exp
      [第 2 步｜answer] {"text": "正確！\n\n第 2 題 / 共 3 題\n\n請用日文回答以下單字：\n中文意思：經常／總是", "model": "gemini-3.6-flash"}

    Coach：正確！
    第 2 題 / 共 3 題
    請用日文回答以下單字：
    中文意思：經常／總是

    你：いっも
      [第 1 步｜action] {"tool": "check_answer", "args": {"word_key": "6:いつも", "user_answer": "いっも"}, "model": "gemini-3.6-flash"}
      [第 1 步｜observation] {"tool": "check_answer", "result": {"ok": true, "correct": false, "error_type": "small_kana", "explanation": "小字（っ ゃ ゅ ょ）寫錯了。正確寫法：いつも", "expected": "い
      [第 2 步｜action] {"tool": "search_examples", "args": {"word_key": "6:いつも"}, "model": "gemini-3.6-flash"}
      [第 2 步｜observation] {"tool": "search_examples", "result": {"ok": false, "error": "Tatoeba 找不到含有「いつも」又有中文翻譯的例句"}}
      [第 3 步｜answer] {"text": "不正確。\n說明：小字（っ ゃ ゅ ょ）寫錯了。\n正確答案是：いつも\n\n這次找不到含有「いつも」的例句。\n\n第 3 題 / 共 3 題\n\n請用日文回答以下單字：\n中文意思：紅茶", "model": "gemini-3.6-flash"}

    Coach：不正確。
    說明：小字（っ ゃ ゅ ょ）寫錯了。
    正確答案是：いつも
    這次找不到含有「いつも」的例句。
    第 3 題 / 共 3 題
    請用日文回答以下單字：
    中文意思：紅茶

    你：お茶
      [第 1 步｜action] {"tool": "check_answer", "args": {"word_key": "6:紅茶", "user_answer": "お茶"}, "model": "gemini-3.6-flash"}
    [llm] gemini-3.6-flash 第 1 次失敗：503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently exp
    [llm] gemini-3.6-flash 第 2 次失敗：503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently exp
      [第 1 步｜observation] {"tool": "check_answer", "result": {"ok": true, "correct": false, "error_type": "llm_wrong", "explanation": "不正確。「お茶」通常泛指茶類或特指日式綠茶，無法精準表達「紅茶」（こうちゃ）的意思
      [第 2 步｜action] {"tool": "search_examples", "args": {"word_key": "6:紅茶"}, "model": "gemini-3.6-flash"}
      [第 2 步｜observation] {"tool": "search_examples", "result": {"ok": false, "error": "連不上 Tatoeba：<urlopen error timed out>"}}

    Coach：不正確。
    說明：不正確。「お茶」通常泛指茶類或特指日式綠茶，無法精準表達「紅茶」（こうちゃ）的意思。
    正確答案是：紅茶
    這次找不到含有「紅茶」的例句。
    測驗結束！
    這一輪 3 題中，你答對了 1 題。
    答對的單字：ええ
    需要加強的單字：いつも、紅茶

    你：我哪些字比較弱
      [第 1 步｜action] {"tool": "get_stats", "args": {}, "model": "gemini-3.6-flash"}
      [第 1 步｜observation] {"tool": "get_stats", "result": {"ok": true, "total_attempts": 12, "accuracy": 0.42, "words_practiced": 12, "weak_words": [], "mastered_words": [], "p

    Coach：你的作答統計資料如下：
    總作答次數：12 次
    整體正確率：42%
    已練習單字數：12 個
    目前系統中暫時沒有特別標記為弱點的單字，但建議可以針對之前錯過的單字（例如「いつも」、「紅茶」等）多做複習！

說明：
- 第 1 題「ええ」由規則直接判對（judged_by: rule），沒有呼叫 LLM 批改
- 第 2 題「いっも」由規則判錯，錯誤類型為 small_kana（小字寫錯），並說明正確寫法
- 第 3 題「お茶」規則判斷不了，交給 LLM 判錯並附理由
- 答錯後自動呼叫 search_examples；Tatoeba 找不到例句或連線逾時時，Agent 如實回報，沒有自行編造例句
- 過程中 gemini-3.6-flash 回傳 503，系統自動等待重試後成功
- 最後查詢弱點時呼叫 get_stats；每個字都只練習過一次，還沒達到弱點的判斷標準，所以弱點清單是空的

## 失敗案例

### 失敗案例一：LLM 擅自修改使用者的答案

完整紀錄：logs/failure_llm_modified_answer.txt

使用者輸入「no  みます」，LLM 呼叫 check_answer 時自行刪掉「no」，只傳「みます」，導致被判為正確。照批改規則，答案含有英文字母應判為錯誤。SYSTEM_PROMPT 和工具說明都寫了「傳入使用者的原始答案」，LLM 仍然沒有遵守。

解決方式：在 src/agent.py 加上 Guardrail，程式記住使用者每一輪實際輸入的內容，批改時一律使用原始輸入，不採用 LLM 傳來的版本。



### 失敗案例二：Gemini 伺服器忙碌與逾時

完整紀錄：logs/failure_503.txt

免費額度在尖峰時段常出現 503（伺服器忙碌）和 504（逾時），導致回應很慢，甚至失敗。一開始沒有設定等待上限，曾經等了好幾分鐘才有回應。

解決方式：設定每次呼叫最多等 30 秒；503 才重試，504 直接換下一個模型；每日額度用完的模型記錄下來，當天不再嘗試。

### 失敗案例三：LLM 沒有照 SYSTEM_PROMPT 的規則走

完整紀錄：logs/failure_prompt_rules.txt

使用者說「考我第 6 課」，LLM 呼叫 pick_words 時卻沒有傳 lesson 參數，出了第 5 課的字；回覆也用了 ** 和 * 這類 Markdown 符號和表情符號，終端機無法顯示成粗體，只會直接印出符號。

解決方式：在 SYSTEM_PROMPT 加上兩條規則，「有指定第幾課時一定要傳入 lesson 參數」和「不要使用 Markdown 符號和表情符號」。修正後重新測試，LLM 有正確傳入 lesson，回覆也沒有再出現這些符號。這類不影響判分的問題用 prompt 改善；會影響判分的規則，則用程式碼強制執行，見失敗案例一。

## 已知限制

- 例句尚未限制「最多 3 個生字」，需要日文斷詞工具，預計在作業三加入
- 動詞原形的判斷依賴 src/grading.py 裡的例外清單，清單外的特殊動詞可能判斷錯誤
- Tatoeba 部分中文翻譯為簡體字
- Gemini 免費額度有每日次數限制
- 作答時只能輸入答案本身，例如輸入「我覺得是みます」會整句拿去批改