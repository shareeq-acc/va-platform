#!/usr/bin/env python3
import os
import sys
import json
import httpx

# Helper to load .env manually
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
    print("=== Vapi Assistant Provisioning Tool ===")
    
    env = load_env()
    api_key = env.get("VAPI_API_KEY", "")
    domain = env.get("DOMAIN", "localhost")
    
    if not api_key or "placeholder" in api_key.lower():
        print("Error: VAPI_API_KEY is not set or contains a placeholder value in your .env file.", file=sys.stderr)
        print("Please update VAPI_API_KEY in .env with your private server key first.", file=sys.stderr)
        sys.exit(1)
        
    if "localhost" in domain or "placeholder" in domain.lower():
        print("Warning: DOMAIN in .env is set to 'localhost' or placeholder.", file=sys.stderr)
        print("Vapi needs a public HTTPS url to send webhooks. If you are developing locally, use ngrok and put your ngrok domain in .env.", file=sys.stderr)
        # Ask to proceed anyway
        response = input("Do you want to proceed with creation anyway? (y/n): ")
        if response.strip().lower() != 'y':
            sys.exit(0)

    webhook_url = f"https://{domain}/webhook" if not domain.startswith("http") else f"{domain}/webhook"
    
    print(f"Creating assistant pointing to webhook URL: {webhook_url}...")
    
    # Define system prompt
    system_prompt = (
        "You are a friendly and professional AI receptionist for General Health Clinic. "
        "Your name is Sarah. When a patient calls, greet them warmly and ask how you can help. "
        "You can help with: scheduling appointments, requesting prescription refills, "
        "updating patient information, or transferring to a staff member. "
        "Collect the patient's full name and date of birth for verification. "
        "Be conversational but efficient. If you cannot help with something, let the "
        "caller know you will transfer them to a staff member."
    )
    
    # Construct Vapi assistant payload
    payload = {
        "name": "Clinic Receptionist Sarah",
        "serverUrl": webhook_url,
        "model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "messages": [
                        {
                            "type": "request-start",
                            "content": "Logging your request details, one moment please..."
                        }
                    ],
                    "function": {
                        "name": "log_call_intent",
                        "description": "Logs the customer details: name, date of birth, and reason for the call.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "The patient's full name."
                                },
                                "dob": {
                                    "type": "string",
                                    "description": "The patient's date of birth (MM/DD/YYYY)."
                                },
                                "reason": {
                                    "type": "string",
                                    "description": "The detailed reason/intent for calling (e.g., refill, schedule, update)."
                                }
                            },
                            "required": ["name", "dob", "reason"]
                        }
                    }
                }
            ]
        },
        "voice": {
            "provider": "playht",
            "voiceId": "susan"
        }
    }
    
    url = "https://api.vapi.ai/assistant"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=15.0)
        if response.status_code not in (200, 201):
            print(f"Error: Vapi API returned status code {response.status_code}", file=sys.stderr)
            print(response.text, file=sys.stderr)
            sys.exit(1)
            
        result = response.json()
        assistant_id = result.get("id")
        
        print("\n=== Success! ===")
        print(f"Assistant Name: {result.get('name')}")
        print(f"Assistant ID:   {assistant_id}")
        
        # Save assistant_id to .env file
        if os.path.exists(".env"):
            print("Writing VAPI_ASSISTANT_ID directly into your .env file...")
            with open(".env", "r") as f:
                content = f.read()
            
            # Replace placeholder
            placeholder = "VAPI_ASSISTANT_ID=vapi_assistant_id_placeholder"
            new_line = f"VAPI_ASSISTANT_ID={assistant_id}"
            if placeholder in content:
                content = content.replace(placeholder, new_line)
            else:
                # If placeholder was already replaced once or edited, search and replace or append
                import re
                content = re.sub(r"VAPI_ASSISTANT_ID=.*", new_line, content)
                
            with open(".env", "w") as f:
                f.write(content)
                
            print("Successfully updated .env with new VAPI_ASSISTANT_ID!")
        else:
            print("Warning: .env file not found, please configure VAPI_ASSISTANT_ID manually.")
            
    except Exception as e:
        print(f"Failed to create assistant: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
