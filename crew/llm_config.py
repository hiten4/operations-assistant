import os
import re
import time
from crewai import LLM
import litellm

# Monkey-patch litellm to strip 'cache_breakpoint' from messages
# because Groq (and some other providers) does not support it and throws a BadRequestError.
_original_completion = litellm.completion
_original_acompletion = litellm.acompletion

def _clean_messages(messages):
    if not isinstance(messages, list):
        return messages
    cleaned = []
    for msg in messages:
        if isinstance(msg, dict):
            # Strip cache_breakpoint if present
            cleaned.append({k: v for k, v in msg.items() if k != "cache_breakpoint"})
        else:
            cleaned.append(msg)
    return cleaned

def _parse_retry_after(error_str: str, default: float = 20.0) -> float:
    """Extract 'try again in Xs' from Groq rate limit messages."""
    match = re.search(r"try again in ([0-9.]+)s", error_str)
    return float(match.group(1)) + 1.0 if match else default

def custom_completion(*args, **kwargs):
    print("\n--- LITELLM COMPLETION CALL ---")
    print(f"Model: {kwargs.get('model') or (args[0] if len(args) > 0 else 'None')}")
    print(f"Tools key present: {'tools' in kwargs}")
    if 'tools' in kwargs:
        print(f"Tools count: {len(kwargs['tools'])}")
        print(f"Tools: {kwargs['tools']}")
    if "messages" in kwargs:
        kwargs["messages"] = _clean_messages(kwargs["messages"])
        print(f"Messages count: {len(kwargs['messages'])}")
        print(f"System message (first 300 chars): {str(kwargs['messages'][0])[:300]}")
        print(f"Last message: {kwargs['messages'][-1]}")
    elif len(args) > 1:
        args_list = list(args)
        args_list[1] = _clean_messages(args_list[1])
        args = tuple(args_list)
    print("-------------------------------\n")

    max_retries = 5
    for attempt in range(max_retries):
        try:
            return _original_completion(*args, **kwargs)
        except litellm.BadRequestError as e:
            if "tool_use_failed" in str(e) and attempt < max_retries - 1:
                print(f"⚠️  Tool call generation failed (attempt {attempt + 1}/{max_retries}), retrying...")
                continue
            raise
        except litellm.RateLimitError as e:
            if attempt < max_retries - 1:
                wait = _parse_retry_after(str(e))
                print(f"⏳  Rate limit hit (attempt {attempt + 1}/{max_retries}), waiting {wait:.1f}s...")
                time.sleep(wait)
                continue
            raise

async def custom_acompletion(*args, **kwargs):
    if "messages" in kwargs:
        kwargs["messages"] = _clean_messages(kwargs["messages"])
    elif len(args) > 1:
        args_list = list(args)
        args_list[1] = _clean_messages(args_list[1])
        args = tuple(args_list)
    return await _original_acompletion(*args, **kwargs)

litellm.completion = custom_completion
litellm.acompletion = custom_acompletion


def get_llm() -> LLM:
    """Return a configured LLM instance using Groq."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY not set. Copy .env.example to .env and add your key."
        )

    model = os.getenv("GROQ_MODEL", "groq/llama-3.3-70b-versatile")

    return LLM(
        model=model,
        api_key=api_key,
        temperature=0.1,   # Low temperature for factual, grounded answers
        max_tokens=4096,
    )