from dotenv import load_dotenv
from google import genai

load_dotenv()              # 讀取 .env，把 GEMINI_API_KEY 放進環境變數
client = genai.Client()    # 自動使用 GEMINI_API_KEY

response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents="用一句話介紹日文的「勉強」是什麼意思",
)
print(response.text)