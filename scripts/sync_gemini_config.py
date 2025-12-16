#!/usr/bin/env python3
import json
import os
import shutil
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ROOT_DIR = Path.home()
SOURCE_GEMINI_DIR = ROOT_DIR / ".gemini"
SOURCE_SETTINGS = SOURCE_GEMINI_DIR / "settings.json"
SOURCE_GEMINI_MD = SOURCE_GEMINI_DIR / "GEMINI.md"

# Directories to ignore
IGNORE_DIRS = {
    'node_modules', '.git', '.venv', 'venv', '__pycache__', 
    'dist', 'build', '.next', '.cache', '.npm'
}

def load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def deep_merge(target, source):
    """Deep merge dictionaries."""
    for key, value in source.items():
        if isinstance(value, dict) and key in target and isinstance(target[key], dict):
            deep_merge(target[key], value)
        else:
            target[key] = value

def get_mcp_config():
    """Extracts the mcpServers config from the source settings."""
    settings = load_json(SOURCE_SETTINGS)
    return settings.get("mcpServers", {})

def sync_settings(target_dir, mcp_config):
    """Syncs mcpServers config to target settings.json."""
    target_file = target_dir / "settings.json"
    
    current_settings = {}
    if target_file.exists():
        current_settings = load_json(target_file)
    
    # Ensure mcpServers key exists
    if "mcpServers" not in current_settings:
        current_settings["mcpServers"] = {}
        
    # Merge the master config into the target
    # We overwrite the target's mcpServers with the source's for the keys present in source
    deep_merge(current_settings["mcpServers"], mcp_config)
    
    save_json(target_file, current_settings)
    logger.info(f"Updated settings at {target_file}")

def sync_gemini_md(target_dir):
    """Syncs GEMINI.md file."""
    if not SOURCE_GEMINI_MD.exists():
        logger.warning("Source GEMINI.md not found!")
        return

    target_file = target_dir / "GEMINI.md"
    
    if not target_file.exists():
        shutil.copy2(SOURCE_GEMINI_MD, target_file)
        logger.info(f"Created GEMINI.md at {target_file}")
    else:
        # If it exists, we skip for now to avoid destroying context
        # Unless the user specifically requested a merge strategy, 
        # overwriting is dangerous.
        logger.info(f"Skipping existing GEMINI.md at {target_file} (manual merge required)")

def find_gemini_dirs(start_path):
    """Recursively find .gemini directories."""
    for root, dirs, files in os.walk(start_path):
        # Modify dirs in-place to prune search
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        if ".gemini" in dirs:
            gemini_path = Path(root) / ".gemini"
            # Skip the source directory itself
            if gemini_path.resolve() == SOURCE_GEMINI_DIR.resolve():
                continue
            yield gemini_path

def main():
    logger.info("Starting Gemini Environment Sync...")
    
    if not SOURCE_SETTINGS.exists():
        logger.error(f"Source settings not found at {SOURCE_SETTINGS}")
        return

    mcp_config = get_mcp_config()
    if not mcp_config:
        logger.warning("No mcpServers configuration found in source settings.")
    
    count = 0
    for gemini_dir in find_gemini_dirs(ROOT_DIR):
        try:
            sync_settings(gemini_dir, mcp_config)
            sync_gemini_md(gemini_dir)
            count += 1
        except Exception as e:
            logger.error(f"Failed to sync {gemini_dir}: {e}")

    logger.info(f"Sync completed. Processed {count} directories.")

if __name__ == "__main__":
    main()
