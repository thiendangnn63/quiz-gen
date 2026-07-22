from openai import OpenAI

client = OpenAI(
    base_url="http://192.168.1.96:8080/v1", 
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