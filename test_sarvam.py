import os
import sys
from pathlib import Path

# Ensure UTF-8 output encoding for non-ASCII characters on Windows consoles
if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def load_env_file(env_path: Path):
    """Loads environment variables from a .env file into os.environ if not already set."""
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val


def main():
    project_root = Path(__file__).resolve().parent
    env_file = project_root / ".env"
    load_env_file(env_file)

    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key or not api_key.strip():
        print("[ERROR] SARVAM_API_KEY not found in environment or .env file.")
        sys.exit(1)

    try:
        from sarvamai import SarvamAI
        from sarvamai.core.api_error import ApiError
        from sarvamai import UnauthorizedError, ForbiddenError, BadRequestError
    except ImportError as e:
        print(f"[ERROR] Failed to import sarvamai SDK: {e}")
        print("Please ensure the official SDK is installed: pip install sarvamai")
        sys.exit(1)

    try:
        client = SarvamAI(api_subscription_key=api_key)
    except Exception as e:
        print(f"[ERROR] Failed to initialize SarvamAI client: {e}")
        sys.exit(1)

    test_queries = [
        "ராகுலின் புகைப்படங்களைக் காட்டு",
        "Raghul oda photos kaatu",
        "राहुल की तस्वीरें दिखाओ",
    ]

    print("=" * 60)
    print("Sarvam AI (Mayura v1) Translation Test")
    print("=" * 60)

    for idx, query in enumerate(test_queries, 1):
        print(f"\n--- Query {idx} ---")
        print(f"Original Query: {query}")
        try:
            response = client.text.translate(
                input=query,
                model="mayura:v1",
                source_language_code="auto",
                target_language_code="en-IN",
            )

            translated_text = getattr(response, "translated_text", None)
            source_lang = getattr(response, "source_language_code", None)

            print(f"Translated Query: {translated_text}")
            if source_lang:
                print(f"Detected Source Language: {source_lang}")
            else:
                print("Detected Source Language: Not returned")

        except UnauthorizedError:
            print("[ERROR] Authentication failed: The provided SARVAM_API_KEY is invalid or unauthorized.")
        except ForbiddenError:
            print("[ERROR] Access forbidden: The SARVAM_API_KEY does not have permission or active subscription.")
        except BadRequestError as e:
            print(f"[ERROR] Bad request error: {e}")
        except ApiError as e:
            print(f"[ERROR] Sarvam API returned error (status {getattr(e, 'status_code', 'unknown')}): {e}")
        except Exception as e:
            print(f"[ERROR] Unexpected error occurred during translation: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("Test completed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
