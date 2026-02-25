#!/usr/bin/env python3
"""
Test the /api/v1/ask/stream endpoint. Run with the server up:

  conda activate langchain-env
  uvicorn app.main:app --host 127.0.0.1 --port 8000

  python scripts/test_stream_endpoint.py
"""
import json
import sys

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

URL = "http://127.0.0.1:8000/api/v1/ask/stream"
BODY = {
    "question": "What is 2+2?",
    "history": [],
    "experts": ["science", "math"],
}


def main():
    print("POST", URL)
    print("Body:", json.dumps(BODY, indent=2))
    print("-" * 40)
    try:
        r = requests.post(URL, json=BODY, stream=True, timeout=60)
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if line:
                print(line)
                obj = json.loads(line)
                if obj.get("event") == "end":
                    print("(end)")
                    break
    except requests.exceptions.ConnectionError as e:
        print("Connection failed. Is the server running?")
        print("  uvicorn app.main:app --host 127.0.0.1 --port 8000")
        sys.exit(1)
    except Exception as e:
        print("Error:", e)
        sys.exit(1)
    print("-" * 40)
    print("Done.")


if __name__ == "__main__":
    main()
