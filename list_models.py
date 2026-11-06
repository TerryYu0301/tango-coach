from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client()

for m in client.models.list():
    if "generateContent" in (m.supported_actions or []):
        print(m.name)