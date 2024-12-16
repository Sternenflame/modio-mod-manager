import subprocess
import sys
from pathlib import Path
import pkg_resources
import logging
from typing import List, Optional
from datetime import datetime
from .config import Config, ConfigValidationError

def setup_logging(log_dir: Optional[Path] = None) -> None:
    """Setup application logging"""
    if log_dir is None:
        log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Prune old logs
    log_files = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime)
    if len(log_files) > 10:
        for old_log in log_files[:-10]:
            try:
                old_log.unlink()
            except:
                pass

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"modio_downloader_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def check_requirements(requirements_file: Path) -> List[str]:
    """Check which requirements need to be installed"""
    required = {}
    missing = []
    
    # Parse requirements.txt
    with requirements_file.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                req = pkg_resources.Requirement.parse(line)
                required[req.name] = req.specs[0][1] if req.specs else None
            except:
                continue
    
    # Check which packages need to be installed
    for package, version in required.items():
        try:
            pkg = pkg_resources.working_set.by_key[package]
            if version and pkg.version != version:
                missing.append(f"{package}=={version}")
        except KeyError:
            if version:
                missing.append(f"{package}=={version}")
            else:
                missing.append(package)
    
    return missing

def install_requirements() -> None:
    """Install missing requirements silently unless there's an error"""
    requirements_path = Path("requirements.txt")
    if not requirements_path.exists():
        return
        
    missing = check_requirements(requirements_path)
    
    if not missing:
        return  # All requirements are already installed
        
    try:
        # Use subprocess.PIPE to hide output unless there's an error
        process = subprocess.Popen(
            [sys.executable, "-m", "pip", "install"] + missing,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            print("Error installing requirements:")
            if stderr:
                print(stderr.decode())
            print("\nPlease install manually using:")
            print("pip install -r requirements.txt")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error installing requirements: {e}")
        print("\nPlease install manually using:")
        print("pip install -r requirements.txt")
        sys.exit(1)

def initialize_application(gui_mode: bool = False) -> None:
    """Initialize the application with all necessary setup"""
    # Setup logging first
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== Application Starting ===")
    
    # Check and install requirements
    try:
        install_requirements()
        logger.info("Requirements check complete")
    except Exception as e:
        logger.error(f"Failed to install requirements: {e}")
        raise

    # Log system info
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    
    # Initialize configuration
    try:
        from .config import config
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise
    
    return logger

if __name__ == "__main__":
    initialize_application()