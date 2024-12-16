import os
import modio
from .recompiler import ModUrlScrapper
from .download import Downloader
from .config import config, Config
from .exceptions import ModFileNotFound, WrongUrl
from pathlib import Path
from typing import Optional, Callable

# Initialize client variable in global scope
client = None

def init_client(api_key):
    global client
    client = modio.Client(api_key=api_key)

# Initialize client with config
init_client(config.modio_api_key)

def download_mod(
    url: str, 
    mod_directory: Optional[Path] = None,
    progress_callback: Optional[Callable[[int], None]] = None
) -> tuple[Path, str, str]:
    """Download mod and return (path, game_id, mod_id)"""
    if not url or not url.strip():
        raise WrongUrl("Empty URL provided")
    
    mod_info = ModUrlScrapper.scrap(url.strip())
    if mod_info is None:
        raise WrongUrl("Invalid mod.io URL format")

    # Get game and mod info
    game_id, mod_id = mod_info
    game = client.get_game(f"@{game_id}")
    mod = game.get_mod(f"@{mod_id}")

    if mod.file is None:
        raise ModFileNotFound

    # Use provided directory or fallback to config
    target_dir = mod_directory or config.mod_directory_path
    
    # Ensure directory exists
    os.makedirs(target_dir, exist_ok=True)

    # Download to the correct directory
    file_path = Path(target_dir) / mod.file.filename
    Downloader.download(
        mod.file.url,
        mod.file.filename,
        mod.file.size,
        target_dir,
        progress_callback=progress_callback
    )
    return file_path, game_id, mod_id
