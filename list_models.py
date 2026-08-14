import os
from dotenv import load_dotenv
from google import genai

# Load your GEMINI_API_KEY from .env
load_dotenv()

print("🔌 Connecting to Google AI Studio...")
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

print("✅ Available Models for your account:")
for model in client.models.list():
    # We only care about models that support text generation
    if "generateContent" in model.supported_actions:
        print(f" - {model.name}")