"""
Step 1: pip install -q -U google-genai
Step 2: python test_gemini2.py YOUR_API_KEY
"""
import sys

api_key = sys.argv[1] if len(sys.argv) > 1 else input("Paste your Gemini API key: ").strip()

try:
    from google import genai
    from google.genai import types
    print("[INFO] Using package: google-genai (new)\n")
except ImportError:
    print("[ERROR] Run first:  pip install -q -U google-genai")
    sys.exit(1)

client = genai.Client(api_key=api_key)

# First, list ALL models available to your account
print("=== Models available to your account ===")
try:
    models = client.models.list()
    vision_models = []
    for m in models:
        name = m.name if hasattr(m, 'name') else str(m)
        # Check if model supports vision/image input
        supported = []
        if hasattr(m, 'supported_actions'):
            supported = m.supported_actions
        print(f"  {name}")
        if 'generateContent' in str(supported) or not supported:
            vision_models.append(name.replace('models/', ''))
    print(f"\nFound {len(vision_models)} potential models\n")
except Exception as e:
    print(f"  Could not list models: {e}\n")
    vision_models = [
        'gemini-2.0-flash-lite',
        'gemini-2.0-flash',
        'gemini-2.5-flash-lite',
        'gemini-2.5-flash',
        'gemini-2.5-pro',
        'gemini-2.0-flash-thinking-exp',
        'gemini-exp-1206',
    ]

# Test each with a simple text prompt
print("=== Testing models ===")
simple_prompt = 'Reply with exactly this JSON and nothing else: {"ok": true}'
working_model = None

for model_name in vision_models:
    # skip embedding / non-generative models
    if any(x in model_name for x in ['embed', 'aqa', 'retrieval', 'classifier']):
        continue
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=simple_prompt
        )
        text = response.text.strip()[:60]
        print(f"  [OK]    {model_name}  →  {text}")
        if working_model is None:
            working_model = model_name
    except Exception as e:
        err = str(e)
        if '429' in err or 'RESOURCE_EXHAUSTED' in err:
            print(f"  [QUOTA] {model_name}")
        elif '404' in err or 'not found' in err.lower():
            print(f"  [N/A]   {model_name}")
        elif 'API_KEY_INVALID' in err or 'INVALID_ARGUMENT' in err and 'key' in err.lower():
            print(f"  [BAD KEY] {model_name} — invalid API key")
            sys.exit(1)
        else:
            print(f"  [FAIL]  {model_name}  →  {err[:80]}")

print()
if working_model:
    print(f"==> Best model to use:  GEMINI_MODEL = '{working_model}'")
else:
    print("==> No models worked.")
    print("    Your free quota is fully exhausted for today — wait 24hrs or create a new Google account.")