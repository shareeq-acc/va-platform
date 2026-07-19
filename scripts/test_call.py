#!/usr/bin/env python3
import os
import sys
import httpx

def load_env():
    env_vars = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        env_vars[parts[0].strip()] = parts[1].strip()
    return env_vars

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_call.py <phone_number>")
        print("Example: python scripts/test_call.py +15551234567")
        sys.exit(1)
        
    phone_number = sys.argv[1]
    env = load_env()
    
    api_key = env.get("VAPI_API_KEY", "")
    assistant_id = env.get("VAPI_ASSISTANT_ID", "")
    phone_number_id = env.get("VAPI_PHONE_NUMBER_ID", "")
    
    if not api_key:
        print("Error: VAPI_API_KEY not found in .env")
        sys.exit(1)
    if not assistant_id:
        print("Error: VAPI_ASSISTANT_ID not found in .env")
        sys.exit(1)
        
    print("=== Launching Vapi Outbound Test Call ===")
    print(f"To Number:    {phone_number}")
    print(f"Assistant ID: {assistant_id}")
    if phone_number_id:
        print(f"Phone Num ID: {phone_number_id}")
        
    # Construct Vapi call payload
    payload = {
        "customer": {
            "number": phone_number
        },
        "assistantId": assistant_id
    }
    
    # If phone number ID is set, specify it
    if phone_number_id and "placeholder" not in phone_number_id.lower():
        payload["phoneNumberId"] = phone_number_id
        
    url = "https://api.vapi.ai/call/phone"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=15.0)
        if response.status_code not in (200, 201):
            print(f"\nError: Vapi API returned status code {response.status_code}")
            print(response.text)
            sys.exit(1)
            
        result = response.json()
        print("\n=== Call Dispatched! ===")
        print(f"Call ID:     {result.get('id')}")
        print(f"Status:      {result.get('status')}")
        print("Check your phone! Sarah should be calling you shortly.")
        
    except Exception as e:
        print(f"\nFailed to dispatch call: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
