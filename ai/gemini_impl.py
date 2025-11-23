# /mnt/data/gemini_impl.py
import os
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables (safe to call multiple times)
load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-1.5-flash") # Updated default model

# Debug logging
logger.info(f"GEMINI_API_KEY loaded: {'Yes' if GEMINI_API_KEY else 'No'}")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY is not set in environment variables!")
    logger.info(f"Available env vars starting with GEMINI: {[k for k in os.environ.keys() if k.startswith('GEMINI')]}")

def ask_gemini_system_user(system_prompt: str, user_text: str, max_tokens: int = 1024, temperature: float = 0.2):
    """
    Simple wrapper to call Gemini using the Python SDK.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    genai.configure(api_key=GEMINI_API_KEY)
    
    # Use the correct model name format for the installed version
    model_name_sdk = "gemini-1.5-flash"
    
    try:
        model = genai.GenerativeModel(model_name_sdk)
        
        # The SDK expects a list of contents. The system prompt can be sent as a separate message.
        # However, to match the previous implementation, I will concatenate the prompts.
        prompt = f"{system_prompt}\n\nUser: {user_text}"
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature
            )
        )
        
        # Handle safety filter blocks
        try:
            return response.text
        except ValueError as e:
            if "safety_ratings" in str(e):
                logger.warning("Response blocked by safety filters")
                return "I understand your message, but I'm unable to provide a specific response due to safety guidelines. Please consider reaching out to a mental health professional for personalized support."
            else:
                raise e
        
    except Exception as e:
        logger.exception("Gemini call failed")
        # Try with gemini-flash-latest as a fallback (known working model)
        try:
            model = genai.GenerativeModel("gemini-flash-latest")
            prompt = f"{system_prompt}\n\nUser: {user_text}"
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature
                )
            )
            return response.text
        except Exception as e2:
            logger.exception("Gemini call with fallback model also failed")
            raise e2
