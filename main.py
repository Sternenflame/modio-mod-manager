import sys
import zipfile
import os
from pathlib import Path
import webbrowser

from loader import download_mod, WrongUrl, ModFileNotFound
from loader.startup import initialize_application

def extract_and_cleanup(zip_path: Path) -> None:
    """Extract zip file and remove it afterwards"""
    try:
        # Extract
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            print(f"\nExtracting {zip_path.name}...")
            zip_ref.extractall(zip_path.parent)
            print("Extraction complete")
        
        # Remove zip file
        zip_path.unlink()
        print(f"Removed {zip_path.name}")
        
    except Exception as e:
        print(f"Error handling zip file: {e}")

def update_api_key() -> bool:
    """Update API key in .env file. Returns True if successful."""
    print("\nLet's update your API key:")
    print("1. Visit https://mod.io/me/access")
    print("2. Under 'API Access', get your API key")
    print("\nType 'o' to open website in browser")
    
    while True:
        user_input = input("Enter new API key (or 'q' to quit)\n> ").strip()
        
        if user_input.lower() == 'q':
            return False
        elif user_input.lower() == 'o':
            webbrowser.open('https://mod.io/me/access')
            continue
        elif user_input:
            try:
                # Read all lines from .env
                with open('.env', 'r') as f:
                    lines = f.readlines()
                
                # Update the API key line
                with open('.env', 'w') as f:
                    for line in lines:
                        if line.startswith('MODIO_API_KEY='):
                            f.write(f'MODIO_API_KEY="{user_input}"\n')
                        else:
                            f.write(line)
                
                # Reinitialize client with new key
                from loader import init_client
                init_client(user_input)
                print("API key updated successfully!")
                return True
                
            except Exception as e:
                print(f"Error updating API key: {e}")
                return False

def main():
    # Initialize application
    logger = initialize_application()
    
    while True:  # Main program loop
        try:
            print("\nEnter 'q' to quit")
            print("Example: https://mod.io/g/game/m/modname")
            url = input("Input Full Mod URL\n> ")
            
            if url.lower() == 'q':
                break
                
            # Download mod
            zip_path = download_mod(url)
            
            # Handle the zip file
            if zip_path and zip_path.exists():
                extract_and_cleanup(zip_path)
            
            print("\nDownload complete! Ready for next mod.")
            
        except WrongUrl:
            print("Error: Invalid mod.io URL provided")
            continue
        except ModFileNotFound:
            print("Error: No downloadable file found for this mod")
            continue
        except Exception as e:
            error_msg = str(e)
            if '401' in error_msg:
                print("\nError: Invalid or expired API key")
                if update_api_key():
                    continue  # Try again with new key
                else:
                    break    # User quit or error occurred
            elif '404' in error_msg or '14006' in error_msg:
                print("\nError: Mod not found or you don't have access to it")
                print("Please check if:")
                print("- The URL is correct")
                print("- The mod is public")
                print("- The mod still exists")
                continue
            else:
                print(f"An unexpected error occurred: {e}")
                continue

    print("\nGoodbye!")

if __name__ == "__main__":
    main()
