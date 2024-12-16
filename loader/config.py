from typing import Optional, Union
from pathlib import Path
import os
import webbrowser

from dotenv import load_dotenv

class ConfigValidationError(Exception):
    """Raised when config validation fails"""
    pass

class Config:
    modio_api_key: str
    mod_directory_path: Path

    def __init__(
        self,
        modio_api_key: str,
        mod_directory_path: Optional[Union[str, Path]] = None
    ) -> None:
        # Validate API key
        if not modio_api_key or modio_api_key.strip() == "":
            raise ConfigValidationError("API key cannot be empty")
        
        # Always use mods directory for initial setup
        if mod_directory_path is None:
            mod_directory_path = Path("mods").resolve()
            
        if isinstance(mod_directory_path, str):
            mod_directory_path = Path(mod_directory_path)

        # Create mods directory if it doesn't exist
        mod_directory_path.mkdir(parents=True, exist_ok=True)

        self.modio_api_key = modio_api_key
        self.mod_directory_path = mod_directory_path

    @classmethod
    def setup_config(cls):
        """Interactive configuration setup"""
        print("\nNo API key found. Let's set one up!")
        print("\nTo get your API key:")
        print("1. Go to mod.io and create an account")
        print("2. Visit https://mod.io/me/access")
        print("3. Under 'API Access', click 'Get API key'")
        print("4. Copy the API key (it should be a long string of letters and numbers)")
        print("\nType 'o' to open website in browser")
        print("Type your API key to continue")
        
        while True:
            try:
                user_input = input("> ").strip()
                if not user_input:  # Skip empty inputs
                    continue
                    
                user_input = user_input.lower()
                if user_input == 'o':
                    webbrowser.open('https://mod.io/me/access')
                    continue
                else:
                    # Validate API key before accepting it
                    if cls.validate_api_key(user_input):
                        api_key = user_input
                        break
                    else:
                        print("Error: Invalid API key. Please check your key and try again.")
                        continue
            except (KeyboardInterrupt, EOFError):
                print("\nOperation cancelled")
                raise SystemExit(1)
            except Exception as e:
                print(f"Invalid input: {e}")
                continue

        mod_dir = str(Path("mods").resolve())
        
        # Save to .env file
        with open('.env', 'w') as f:
            f.write(f'MODIO_API_KEY="{api_key}"\n')
            f.write(f'MOD_DIRECTORY_PATH="{mod_dir}"\n')
        print("\nConfiguration saved to .env file")
        
        return cls(modio_api_key=api_key, mod_directory_path=mod_dir)

    @staticmethod
    def validate_api_key(api_key: str) -> bool:
        """Test if the API key is valid"""
        if not api_key or not api_key.strip():
            return False
        # Basic format check (can be expanded)
        return len(api_key.strip()) >= 32

    @classmethod
    def from_env(cls):
        """Load configuration from environment"""
        load_dotenv()
        
        api_key = os.getenv('MODIO_API_KEY', '').strip()
        if not api_key:
            return cls.setup_config()
            
        mod_dir = os.getenv('MOD_DIRECTORY_PATH', 'mods')
        return cls(modio_api_key=api_key, mod_directory_path=mod_dir)

# Create config instance with graceful error handling
try:
    config = Config.from_env()
except ConfigValidationError as e:
    print(f"\nError: {e}")
    raise SystemExit(1)
except Exception as e:
    print(f"\nUnexpected error: {e}")
    print("Please try again or report this issue")
    raise SystemExit(1)
