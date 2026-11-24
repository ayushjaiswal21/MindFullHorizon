import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables (safe to call multiple times)
load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# Model ids are retired often: set GEMINI_MODEL_NAME to pin one; the "-latest" alias is the default.
GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-flash-latest")
FALLBACK_MODEL = "gemini-flash-latest"
try:
    GEMINI_TIMEOUT = float(os.environ.get("GEMINI_TIMEOUT", "20"))
except ValueError:
    GEMINI_TIMEOUT = 20.0

if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY is not set: AI features use fallbacks")


class GeminiBlocked(Exception):
    """The model refused or its safety filter blocked the reply (callers must keep crisis resources)."""


def _generate(model_name, system_prompt, user_text, max_tokens, temperature, timeout):
    # system rules go in system_instruction, so user text is never concatenated into the instructions
    model = genai.GenerativeModel(model_name, system_instruction=system_prompt)
    response = model.generate_content(
        user_text,
        generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens, temperature=temperature),
        request_options={"timeout": timeout},
    )
    try:
        return response.text
    except ValueError as e:  # no candidates / finish_reason SAFETY
        raise GeminiBlocked("response blocked or empty") from e


def ask_gemini_system_user(system_prompt: str, user_text: str, max_tokens: int = 1024,
                           temperature: float = 0.2, timeout: float = None):
    """Call Gemini with a system instruction and the user's text. Raises GeminiBlocked on safety blocks."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    genai.configure(api_key=GEMINI_API_KEY)
    timeout = timeout or GEMINI_TIMEOUT
    try:
        return _generate(GEMINI_MODEL_NAME, system_prompt, user_text, max_tokens, temperature, timeout)
    except GeminiBlocked:
        raise
    except Exception:
        if GEMINI_MODEL_NAME == FALLBACK_MODEL:
            logger.exception("Gemini call failed")
            raise
        logger.warning("Gemini model %s failed, retrying with %s", GEMINI_MODEL_NAME, FALLBACK_MODEL)
        return _generate(FALLBACK_MODEL, system_prompt, user_text, max_tokens, temperature, timeout)
