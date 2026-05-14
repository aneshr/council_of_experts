#!/usr/bin/env python3
"""Diagnose langchain/langchain_core import error. Writes one NDJSON line to .cursor/debug-8f8772.log"""
import sys
import json

LOG_PATH = "/Users/aneesh/Work/chat_app/.cursor/debug-8f8772.log"

def main():
    data = {"hypothesisId": "H1_H2_H3", "message": "langchain import diagnostic", "data": {}}
    try:
        import langchain
        data["data"]["langchain_version"] = getattr(langchain, "__version__", "?")
    except Exception as e:
        data["data"]["langchain_import_error"] = str(e)
    try:
        import langchain_core
        data["data"]["langchain_core_version"] = getattr(langchain_core, "__version__", "?")
    except Exception as e:
        data["data"]["langchain_core_import_error"] = str(e)
        sys.exit(1)

    prompts = getattr(langchain_core, "prompts", None)
    if prompts is not None:
        data["data"]["has_PipelinePromptTemplate"] = hasattr(prompts, "PipelinePromptTemplate")
        data["data"]["has_PromptTemplate"] = hasattr(prompts, "PromptTemplate")
    else:
        data["data"]["langchain_core.prompts"] = None

    try:
        from langchain_core.prompts import PromptTemplate
        data["data"]["direct_PromptTemplate_import"] = "OK"
    except Exception as e:
        data["data"]["direct_PromptTemplate_import"] = str(e)

    try:
        from langchain.prompts import PromptTemplate
        data["data"]["langchain_prompts_PromptTemplate_import"] = "OK"
    except Exception as e:
        data["data"]["langchain_prompts_PromptTemplate_import"] = str(e)

    entry = {"id": "log_diagnostic", "timestamp": 0, "location": "scripts/debug_langchain_import.py", "hypothesisId": "H1_H2_H3", "message": data["message"], "data": data["data"]}
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print("Wrote log to", LOG_PATH)
    print(json.dumps(data["data"], indent=2))

if __name__ == "__main__":
    main()
