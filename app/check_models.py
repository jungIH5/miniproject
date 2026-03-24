import os
import google.generativeai as genai
from dotenv import load_dotenv
import sys

# Windows 인코딩 처리
# sys.stdout.reconfigure(encoding='utf-8')

# .env 로드
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("[Error] GEMINI_API_KEY not found in .env")
else:
    genai.configure(api_key=api_key)
    print(f"[Info] Testing API Key (Suffix: {api_key[-4:]})")
    
    try:
        print("Available Models list:")
        print("-" * 40)
        found = False
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"Model: {m.name}")
                found = True
        
        if not found:
            print("[Warning] No models found. Check API key permissions.")
            
    except Exception as e:
        print(f"[Error] Failed to list models: {e}")
