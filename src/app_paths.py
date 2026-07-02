from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"
RESOURCES_DIR = BASE_DIR / "resources"
PROMPTS_DIR = RESOURCES_DIR / "prompts"
SCHEMAS_DIR = RESOURCES_DIR / "schemas"
ASSETS_DIR = RESOURCES_DIR / "assets"
EXTENSIONS_DIR = BASE_DIR / "extensions"
CHROME_EXTENSION_DIR = EXTENSIONS_DIR / "chrome"
