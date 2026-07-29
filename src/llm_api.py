from openai import OpenAI

client = OpenAI(
    base_url="http://192.168.1.249:8080/v1", 
    api_key="ollama"
)

def call_api(contents, response_json=False):
    try:
        messages = [{"role": "system", "content": "RETURN ALL ANSWERS IN ENGLISH."}]
        
        if isinstance(contents, list):
            messages.append({"role": "user", "content": contents})
        else:
            messages.append({"role": "user", "content": contents})

        kwargs = {
            "model": "qwen3.6-35b",
            #"model" : "gpt-4.1",
            "messages": messages
        }
        
        if response_json:
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        error_msg = str(e)
        print(f"[Module: llm_api, Function: call_api] Error: {error_msg}")
        
        if "Failed to load image" in error_msg or "400" in error_msg:
            print("\n[DEBUG] The local server rejected the image payload. Verify that 'qwen3.6-35b' is a Vision-Language Model (VLM). If it is a text-only model, it cannot process image rating tasks.\n")
        raise

# import os
# import time
# import random
# import base64
# import threading
# from collections import deque
# from dotenv import load_dotenv
# from google import genai
# from google.genai import types

# try:
#     load_dotenv()
#     API_KEYS = [os.getenv(key) for key in ['API1', 'API2', 'API3', 'API4', 'API5', 'API6', 'API7', 'API8', 'API9', 'API10'] if os.getenv(key)]
#     MODEL = [
#         "gemini-2.5-flash",
#         "gemini-2.5-flash-lite",
#         "gemini-2.5-pro",
#         "gemini-3-flash-preview",
#         "gemini-3-pro-preview"
#     ]
# except Exception as e:
#     print(f"[Module: llm_api, Initialization] Error: {e}")
#     raise

# _KEY_COOLDOWNS = {}

# _KEY_CALL_TIMES = {key: deque() for key in API_KEYS}
# _RATE_LOCK = threading.Lock()

# RPM_LIMIT = 15

# def _is_quota_error(e):
#     msg = str(e).lower()
#     return any(s in msg for s in ["429", "quota", "resource_exhausted", "rate limit"])

# def _is_on_cooldown(key):
#     until = _KEY_COOLDOWNS.get(key)
#     return until is not None and time.time() < until

# def _set_cooldown(key):
#     _KEY_COOLDOWNS[key] = time.time() + random.uniform(30, 60)

# def _wait_for_rpm_slot(key):
#     """Blocks until this key has room under RPM_LIMIT in the last 60s."""
#     while True:
#         with _RATE_LOCK:
#             times = _KEY_CALL_TIMES[key]
#             now = time.time()
#             while times and now - times[0] > 60:
#                 times.popleft()

#             if len(times) < RPM_LIMIT:
#                 times.append(now)
#                 return

#             wait_time = 60 - (now - times[0]) + 0.05
#         time.sleep(wait_time)

# def call_api(contents, response_json=False):
#     try:
#         for key in API_KEYS:
#             if _is_on_cooldown(key):
#                 continue

#             for mod in MODEL:
#                 try:
#                     _wait_for_rpm_slot(key)

#                     client = genai.Client(api_key=key)
#                     config_kwargs = {}
#                     if response_json:
#                         config_kwargs["response_mime_type"] = "application/json"
                    
#                     formatted_contents = []
#                     if isinstance(contents, list):
#                         for item in contents:
#                             if isinstance(item, dict) and item.get("type") == "image_url":
#                                 b64_data = item["image_url"]["url"].split(",")[1]
#                                 formatted_contents.append(
#                                     types.Part.from_bytes(
#                                         data=base64.b64decode(b64_data), 
#                                         mime_type="image/jpeg"
#                                     )
#                                 )
#                             elif isinstance(item, dict) and item.get("type") == "text":
#                                 formatted_contents.append(item["text"])
#                             else:
#                                 formatted_contents.append(item)
#                     else:
#                         formatted_contents = contents

#                     print("Calling LLM")
#                     response = client.models.generate_content(
#                         model=mod,
#                         contents=formatted_contents,
#                         config=types.GenerateContentConfig(**config_kwargs)
#                     )
#                     print("LLM call succeeded")
#                     return response.text
#                 except Exception as e:
#                     print(f"[Module: llm_api, Function: call_api] Error: {e}")
#                     if _is_quota_error(e):
#                         _set_cooldown(key)
#                         break  # no point trying other models on a quota-exhausted key
#                     continue

#         raise RuntimeError("All Gemini API keys exhausted or failed.")
#     except Exception as e:
#         print(f"[Module: llm_api, Function: call_api] Error: {e}")
#         raise