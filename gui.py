# gui.py
import sys
import webbrowser
from pathlib import Path
import json
import logging
from datetime import datetime
import zipfile
import re
import os
import time
import psutil
import urllib.parse
import pkg_resources

try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QLabel,
        QListWidget, QMessageBox, QSplitter, QMenu, QAction, QInputDialog,
        QFileDialog, QProgressBar, QAbstractItemView, QHeaderView,
        QDialog, QComboBox, QCheckBox, QSpinBox, QDialogButtonBox, QTextEdit
    )
    from PyQt5.QtCore import Qt, pyqtSignal, QTimer
except ImportError:
    print("Error: PyQt5 is required. Please install it using:")
    print("pip install PyQt5")
    sys.exit(1)

# Loader code references
from loader import download_mod, WrongUrl, ModFileNotFound
from loader.startup import initialize_application
from loader.config import Config  # Add Config import

# Add config file path
CONFIG_FILE = Path("config.json")
DEFAULT_CONFIG = {
    "theme": "key",
    "auto_check_updates": False,
    "backup_count": 5,
    "download_retries": 3,
    "chunk_size": 1024 * 1024,  # 1MB
    "show_download_speed": True,
    "auto_remove_zip": True,
    "lazy_load_threshold": 100,
}

class ModDownloaderGUI(QMainWindow):
    # Theme colors
    COLORS = {
        "white": {
            "bg": "#FFFFFF",  # Pure white
            "fg": "#000000",  # Black text
            "alt": "#F5F5F5", # Slightly off-white
            "border": "#E0E0E0", # Light border
            "highlight": "#D3D3D3" # Light highlight
        },
        "lightgrey": {
            "bg": "#D3D3D3",  # Light grey
            "fg": "#000000",  # Black text
            "alt": "#C0C0C0", # Slightly darker
            "border": "#A9A9A9", # Border
            "highlight": "#BEBEBE" # Highlight
        },
        "grey": {
            "bg": "#A9A9A9",  # Medium grey
            "fg": "#FFFFFF",  # White text
            "alt": "#989898", # Slightly darker
            "border": "#787878", # Border
            "highlight": "#B8B8B8" # Highlight
        },
        "darkgrey": {
            "bg": "#808080",  # Dark grey
            "fg": "#FFFFFF",  # White text
            "alt": "#707070", # Slightly darker
            "border": "#606060", # Border
            "highlight": "#909090" # Highlight
        },
        "key": {
            "bg": "#414a4c",  # Key grey
            "fg": "#FFFFFF",  # White text
            "alt": "#363d3f", # Slightly darker
            "border": "#2b3032", # Border
            "highlight": "#4c5659" # Highlight
        },
        "black": {
            "bg": "#1B1B1B",  # Original black
            "fg": "#FFFFFF",  # White text
            "alt": "#252525", # Slightly lighter
            "border": "#2D2D2D", # Border
            "highlight": "#404040" # Highlight
        }
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mod.io Downloader")
        self.resize(800, 500)

        self.setup_logging()
        self.profiles_file = Path("profiles.json")
        self.db_file = Path("moddb.json")
        self.mod_db = {}
        
        # Load configuration
        self.config = self.load_config()
        
        self.current_api_key = self.load_api_key_from_env()
        
        # Check for API key on startup
        if not self.current_api_key or self.current_api_key == "pending":
            self.show_api_key_setup_dialog()
        
        self.profiles = self.load_profiles()

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        self.block_mod_status_change = False

        self.stats = {
            "downloads": 0,
            "updates": 0,
            "failures": 0,
            "total_size": 0,
            "start_time": datetime.now(),
        }

        # Setup UI
        self.setup_gui()

        # Load DB
        self.mod_db = self.load_mod_db()
        self.refresh_mod_tree()

        # Auto-check for updates if enabled
        if self.config["auto_check_updates"]:
            QTimer.singleShot(1000, self.check_updates)

    def load_config(self):
        """Load user configuration with defaults"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    user_config = json.load(f)
                    # Merge with defaults
                    config = DEFAULT_CONFIG.copy()
                    config.update(user_config)
                    # Validate theme and accent
                    if config["theme"] not in ["white", "lightgrey", "grey", "darkgrey", "key", "black"]:
                        config["theme"] = "key"
                    if config["theme_accent"] not in ["default", "purple", "gold", "blue", "green", "red"]:
                        config["theme_accent"] = "default"
                    return config
            except Exception as e:
                self.logger.error(f"Failed to load config: {e}")
                return DEFAULT_CONFIG.copy()
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        """Save current configuration"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            QMessageBox.warning(self, "Error", f"Failed to save configuration: {e}")

    def show_preferences_dialog(self):
        """Show preferences dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Preferences")
        layout = QVBoxLayout(dialog)

        # Theme selection
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        theme_combo = QComboBox()
        theme_combo.addItems(["white", "lightgrey", "grey", "darkgrey", "key", "black"])
        theme_combo.setCurrentText(self.config.get("theme", "darkgrey"))
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(theme_combo)
        layout.addLayout(theme_layout)

        # Auto-check updates
        auto_check = QCheckBox("Automatically check for updates")
        auto_check.setChecked(self.config["auto_check_updates"])
        layout.addWidget(auto_check)

        # Show download speed
        show_speed = QCheckBox("Show download speed")
        show_speed.setChecked(self.config["show_download_speed"])
        layout.addWidget(show_speed)

        # Auto-remove ZIP
        auto_remove = QCheckBox("Automatically remove ZIP after extraction")
        auto_remove.setChecked(self.config["auto_remove_zip"])
        layout.addWidget(auto_remove)

        # Backup count
        backup_layout = QHBoxLayout()
        backup_label = QLabel("Number of backups to keep:")
        backup_spin = QSpinBox()
        backup_spin.setRange(1, 20)
        backup_spin.setValue(self.config["backup_count"])
        backup_layout.addWidget(backup_label)
        backup_layout.addWidget(backup_spin)
        layout.addLayout(backup_layout)

        # Download retries
        retry_layout = QHBoxLayout()
        retry_label = QLabel("Download retry attempts:")
        retry_spin = QSpinBox()
        retry_spin.setRange(1, 10)
        retry_spin.setValue(self.config["download_retries"])
        retry_layout.addWidget(retry_label)
        retry_layout.addWidget(retry_spin)
        layout.addLayout(retry_layout)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec_() == QDialog.Accepted:
            # Save new preferences
            self.config.update({
                "theme": theme_combo.currentText(),
                "auto_check_updates": auto_check.isChecked(),
                "show_download_speed": show_speed.isChecked(),
                "auto_remove_zip": auto_remove.isChecked(),
                "backup_count": backup_spin.value(),
                "download_retries": retry_spin.value(),
            })
            self.save_config()
            
            # Apply theme
            self.apply_theme()
            
            QMessageBox.information(self, "Success", "Preferences saved successfully!")

    def apply_theme(self):
        """Apply the current theme"""
        # Get theme from config
        theme = self.config.get("theme", "key")
        
        # Ensure valid theme
        if theme not in self.COLORS:
            theme = "key"
            self.config["theme"] = theme
        
        theme_colors = self.COLORS[theme]
        
        self.logger.info(f"Applying theme: {theme}")
        
        # Apply the theme
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {theme_colors['bg']};
            }}
            QWidget {{
                background-color: {theme_colors['bg']};
                color: {theme_colors['fg']};
            }}
            QMenuBar, QMenu {{
                background-color: {theme_colors['bg']};
                color: {theme_colors['fg']};
            }}
            QMenuBar::item:selected, QMenu::item:selected {{
                background-color: {theme_colors['highlight']};
            }}
            QPushButton {{
                background-color: {theme_colors['alt']};
                color: {theme_colors['fg']};
                border: none;
                padding: 5px 15px;
                border-radius: 2px;
            }}
            QPushButton:hover {{
                background-color: {theme_colors['highlight']};
            }}
            QLineEdit {{
                background-color: {theme_colors['alt']};
                color: {theme_colors['fg']};
                border: 1px solid {theme_colors['border']};
                padding: 5px;
                border-radius: 2px;
            }}
            QTreeWidget, QListWidget {{
                background-color: {theme_colors['alt']};
                color: {theme_colors['fg']};
                border: 1px solid {theme_colors['border']};
                border-radius: 2px;
            }}
            QTreeWidget::item:selected, QListWidget::item:selected {{
                background-color: {theme_colors['highlight']};
                color: {theme_colors['fg']};
            }}
            QHeaderView::section {{
                background-color: {theme_colors['bg']};
                color: {theme_colors['fg']};
                border: 1px solid {theme_colors['border']};
                padding: 5px;
            }}
            QScrollBar:vertical, QScrollBar:horizontal {{
                background-color: {theme_colors['bg']};
                width: 12px;
                height: 12px;
            }}
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
                background-color: {theme_colors['alt']};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:hover {{
                background-color: {theme_colors['highlight']};
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{
                background: none;
                border: none;
            }}
            QScrollBar::add-page, QScrollBar::sub-page {{
                background: {theme_colors['bg']};
                border: none;
            }}
            QProgressBar {{
                border: 1px solid {theme_colors['border']};
                background: {theme_colors['alt']};
                height: 10px;
                text-align: center;
                color: {theme_colors['fg']};
            }}
            QProgressBar::chunk {{
                background: {theme_colors['highlight']};
            }}
            QComboBox {{
                background-color: {theme_colors['alt']};
                color: {theme_colors['fg']};
                border: 1px solid {theme_colors['border']};
                padding: 5px;
                border-radius: 2px;
            }}
            QComboBox:hover {{
                background-color: {theme_colors['highlight']};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
            }}
            QCheckBox {{
                color: {theme_colors['fg']};
            }}
            QCheckBox::indicator {{
                width: 13px;
                height: 13px;
                border: 1px solid {theme_colors['border']};
                background: {theme_colors['alt']};
            }}
            QCheckBox::indicator:checked {{
                background: {theme_colors['highlight']};
            }}
            QSpinBox {{
                background-color: {theme_colors['alt']};
                color: {theme_colors['fg']};
                border: 1px solid {theme_colors['border']};
                padding: 5px;
                border-radius: 2px;
            }}
        """)

    def download_mod(self):
        """Download the mod based on the provided URL"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a mod URL")
            return

        current_profile_item = self.profile_list.currentItem()
        if not current_profile_item:
            QMessageBox.warning(self, "Error", "No profile selected.")
            return

        profile_name = current_profile_item.text()
        mod_dir = Path(self.profiles[profile_name]["mod_directory"]).resolve()
        clean_url = url.replace("//", "/").replace("http:/", "http://").replace("https:/", "https://")

        self.logger.info(f"Downloading mod from URL: {clean_url}, to directory: {mod_dir}")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        def update_progress(progress: int):
            """Callback to update progress bar and keep UI responsive"""
            self.progress_bar.setValue(progress)
            QApplication.processEvents()

        try:
            # Download mod with progress updates
            start_time = time.time()
            file_path, file_size, _ = download_mod(
                clean_url, 
                mod_directory=mod_dir,
                progress_callback=update_progress
            )
            download_time = time.time() - start_time
            
            # Update statistics - ensure file_size is an integer
            self.stats["downloads"] += 1
            try:
                file_size = int(file_size) if file_size else 0
                self.stats["total_size"] += file_size
                
                # Show download speed if enabled and file_size is valid
                if self.config["show_download_speed"] and file_size > 0:
                    speed = file_size / download_time / 1024 / 1024  # MB/s
                    self.logger.info(f"Download speed: {speed:.1f} MB/s")
            except (TypeError, ValueError):
                self.logger.warning(f"Invalid file size value: {file_size}")
                self.stats["total_size"] += 0
            
            self.logger.info(f"Downloaded mod to: {file_path}")

            # Extract mod (already has progress updates)
            extracted_files = self.extract_mod(file_path, remove_zip=True)
            if not extracted_files:
                raise RuntimeError("No valid files extracted from archive.")

            # Update database
            now = datetime.now().isoformat()
            for extracted_file in extracted_files:
                extracted_path = mod_dir / extracted_file
                if not extracted_path.is_file():
                    continue

                local_name = extracted_path.name
                prefix = re.sub(r'^pakchunk\d+-Mods_', '', extracted_path.stem, flags=re.IGNORECASE)
                prefix = re.sub(r'_P$', '', prefix, flags=re.IGNORECASE)

                mod_info = {
                    "name": prefix,
                    "local_name": local_name,
                    "zip_name": file_path.name,
                    "installed_date": now,
                    "updated_date": now,
                    "profile": profile_name,
                    "enabled": True,
                    "installed_path": str(mod_dir),
                    "url": clean_url,
                }
                self.mod_db["mods"][local_name] = mod_info

            self.save_mod_db()
            self.refresh_mod_tree()
            self.logger.info("Mod download and extraction complete.")

        except WrongUrl:
            QMessageBox.warning(self, "Error", "Invalid mod URL. Please check the URL format.")
        except ModFileNotFound:
            QMessageBox.warning(self, "Error", "No downloadable file found for this mod.")
        except Exception as e:
            self.logger.error(f"Failed to download mod: {str(e)}", exc_info=True)
            QMessageBox.warning(self, "Error", f"An error occurred: {e}")
        finally:
            self.progress_bar.setVisible(False)

    def check_updates(self):
        """Redownload and reinstall all mods."""
        reply = QMessageBox.question(
            self, "Check for Updates",
            "This will redownload and reinstall all mods. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        # Get current profile
        current_profile = self.profile_list.currentItem()
        if not current_profile:
            QMessageBox.warning(self, "Error", "No profile selected.")
            return
        profile_name = current_profile.text()

        # Filter mods for current profile
        mods = [
            (mid, info) for mid, info in self.mod_db.get("mods", {}).items()
            if info.get("profile") == profile_name
        ]
        
        total_mods = len(mods)
        if total_mods == 0:
            return

        # Store disabled state of mods
        disabled_mods = {
            mid: info["local_name"] 
            for mid, info in mods 
            if not info.get("enabled", True)
        }
        
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.logger.info(f"Starting mod updates for profile: {profile_name}")

        # Each mod gets equal portion of progress (50% download, 50% extract)
        progress_per_mod = 100.0 / total_mods
        completed = 0
        failed_mods = []

        def make_progress_callback(start_percent):
            """Create a progress callback with the correct range"""
            def callback(progress: int):
                # Map progress (0-100) to the mod's portion of total progress
                mod_base = completed * progress_per_mod
                progress_portion = progress_per_mod / 2  # Half for download, half for extract
                current_progress = mod_base + (progress / 100.0 * progress_portion)
                
                if start_percent:  # If this is extraction phase
                    current_progress += progress_portion  # Add download portion
                    
                self.progress_bar.setValue(int(min(current_progress, 100)))
                QApplication.processEvents()
            return callback

        for mod_id, mod_info in mods:
            try:
                mod_url = mod_info.get("url", "")
                if not mod_url:
                    self.logger.warning(f"No URL for mod '{mod_id}', skipping.")
                    failed_mods.append((mod_id, "No URL found"))
                    continue

                profile_dir = Path(mod_info["installed_path"])
                disabled_dir = profile_dir / ".disabledmods"
                
                # Move any disabled version to temp location
                if mod_id in disabled_mods:
                    mod_name = disabled_mods[mod_id]
                    disabled_files = list(disabled_dir.glob(f"*{mod_name}*"))
                    for f in disabled_files:
                        try:
                            self.logger.info(f"Removing old disabled mod: {f}")
                            f.unlink(missing_ok=True)
                        except Exception as e:
                            self.logger.error(f"Failed to remove old disabled mod: {e}")
                
                # Remove any enabled version
                enabled_files = list(profile_dir.glob(f"*{mod_info['local_name']}*"))
                for f in enabled_files:
                    try:
                        self.logger.info(f"Removing old enabled mod: {f}")
                        f.unlink(missing_ok=True)
                    except Exception as e:
                        self.logger.error(f"Failed to remove old enabled mod: {e}")

                # Download and extract mod
                try:
                    start_time = time.time()
                    file_path, file_size, _ = download_mod(
                        mod_url, 
                        mod_directory=profile_dir,
                        progress_callback=make_progress_callback(False)
                    )
                    download_time = time.time() - start_time

                    # Update statistics - ensure file_size is an integer
                    try:
                        file_size = int(file_size) if file_size else 0
                        self.stats["total_size"] += file_size
                        
                        # Show download speed if enabled and file_size is valid
                        if self.config["show_download_speed"] and file_size > 0:
                            speed = file_size / download_time / 1024 / 1024  # MB/s
                            self.logger.info(f"Download speed: {speed:.1f} MB/s")
                    except (TypeError, ValueError):
                        self.logger.warning(f"Invalid file size value: {file_size}")
                        file_size = 0  # Set to 0 for invalid values

                    extracted_files = self.extract_mod(
                        file_path, 
                        remove_zip=True,
                        progress_callback=make_progress_callback(True)
                    )

                    if not extracted_files:
                        raise RuntimeError("No files extracted from archive")

                    # Update database entries and restore disabled state
                    now = datetime.now().isoformat()
                    for extracted_file in extracted_files:
                        extracted_path = profile_dir / extracted_file
                        if not extracted_path.is_file():
                            continue

                        local_name = extracted_path.name
                        was_disabled = mod_id in disabled_mods
                        
                        self.mod_db["mods"][local_name] = {
                            **mod_info,
                            "local_name": local_name,
                            "updated_date": now,
                            "enabled": not was_disabled
                        }
                        
                        # Move to disabled folder if it was disabled
                        if was_disabled:
                            try:
                                disabled_dir.mkdir(exist_ok=True)
                                # Remove existing file in disabled folder if it exists
                                disabled_path = disabled_dir / local_name
                                if disabled_path.exists():
                                    disabled_path.unlink()
                                # Now move the file
                                extracted_path.rename(disabled_path)
                            except Exception as e:
                                self.logger.error(f"Failed to move mod to disabled folder: {e}")
                                # If move fails, try to copy and delete
                                try:
                                    import shutil
                                    shutil.copy2(extracted_path, disabled_dir / local_name)
                                    extracted_path.unlink(missing_ok=True)
                                except Exception as copy_error:
                                    self.logger.error(f"Failed to copy mod to disabled folder: {copy_error}")

                except Exception as e:
                    self.logger.error(f"Failed to update mod {mod_id}: {str(e)}")
                    failed_mods.append((mod_id, str(e)))
                    continue

            except Exception as e:
                self.logger.error(f"Failed to process mod {mod_id}: {str(e)}")
                failed_mods.append((mod_id, str(e)))

            completed += 1
            self.progress_bar.setValue(int(completed * progress_per_mod))
            QApplication.processEvents()

        # Final cleanup
        self.save_mod_db()
        self.refresh_mod_tree()
        
        if completed == total_mods and not failed_mods:
            self.logger.info("All mods updated successfully!")
            self.progress_bar.setValue(100)
            QApplication.processEvents()
            time.sleep(1)  # Show 100% progress for 1 second
            QMessageBox.information(self, "Success", "All mods updated successfully!")
        else:
            self.logger.warning(f"{len(failed_mods)} mods failed to update")
            error_msg = "The following mods failed to update:\n\n"
            for mod_id, error in failed_mods:
                error_msg += f"• {mod_id}: {error}\n"
            QMessageBox.warning(self, "Update Incomplete", error_msg)
        
        self.progress_bar.setVisible(False)

    def setup_logging(self):
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
        self.logger = logging.getLogger(__name__)
        self.logger.info("=== Application Started ===")
        self.logger.info(f"Log file: {log_file}")
        self.logger.info(f"Python version: {sys.version}")

    def load_api_key_from_env(self) -> str:
        env_path = Path('.env')
        if not env_path.exists():
            self.logger.info("No .env file found; no API key loaded.")
            return ""
        lines = env_path.read_text().splitlines()
        for line in lines:
            if line.startswith('MODIO_API_KEY='):
                parts = line.split('=', 1)
                if len(parts) == 2:
                    val = parts[1].strip().strip('"')
                    if val:
                        self.logger.info("Found API key in .env.")
                        return val
        self.logger.info("No valid API key found in .env.")
        return ""

    def load_profiles(self):
        if not self.profiles_file.exists():
            # Always use mods directory without prompting
            dir_path = str(Path("mods").resolve())

            default = {
                "Default": {
                    "mod_directory": dir_path,
                    "auto_extract": True
                }
            }
            with open(self.profiles_file, 'w') as f:
                json.dump(default, f, indent=4)
            return default

        with open(self.profiles_file, 'r') as f:
            return json.load(f)

    def setup_gui(self):
        # --- Dark Theme CSS ---
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1B1B1B;
            }
            QWidget {
                background-color: #1B1B1B;
                color: #FFFFFF;
            }
            QMenuBar, QMenu {
                background-color: #1B1B1B;
                color: #FFFFFF;
            }
            QMenuBar::item:selected, QMenu::item:selected {
                background-color: #2D2D2D;
            }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: none;
                padding: 5px 15px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #404040;
            }
            QLineEdit {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: none;
                padding: 5px;
                border-radius: 2px;
            }
            QTreeWidget, QListWidget {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: none;
                border-radius: 2px;
            }
            QTreeWidget::item:selected, QListWidget::item:selected {
                background-color: #404040;
            }
            QHeaderView::section {
                background-color: #1B1B1B;
                color: #FFFFFF;
                border: none;
                padding: 5px;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background-color: #252525;
                width: 12px;
                height: 12px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background-color: #2D2D2D;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:hover {
                background-color: #404040;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                background: none;
                border: none;
            }
            QScrollBar::add-page, QScrollBar::sub-page {
                background: #252525;
                border: none;
            }
            QProgressBar {
                border: none;
                background: #2D2D2D;
                height: 10px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #4CAF50;
            }
        """)

        menubar = self.menuBar()

        # Options menu
        options_menu = menubar.addMenu("Options")

        # Show/Change API Key
        api_key_action = QAction("API Key", self)
        api_key_action.triggered.connect(self.show_current_api_key_dialog)
        options_menu.addAction(api_key_action)

        # Preferences
        preferences_action = QAction("Preferences", self)
        preferences_action.triggered.connect(self.show_preferences_dialog)
        options_menu.addAction(preferences_action)

        # Open Manager Folder
        open_manager_folder_action = QAction("Open Manager Folder", self)
        open_manager_folder_action.triggered.connect(self.open_manager_folder)
        options_menu.addAction(open_manager_folder_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        open_github_action = QAction("Open GitHub Page", self)
        open_github_action.triggered.connect(self.open_github_page)
        help_menu.addAction(open_github_action)

        # "Report a Bug" under Help
        bug_report_action = QAction("Report a Bug", self)
        bug_report_action.triggered.connect(self.open_bug_report)
        help_menu.addAction(bug_report_action)

        # Add Diagnostics to Help menu
        diagnostics_action = QAction("Show Diagnostics", self)
        diagnostics_action.triggered.connect(self.show_diagnostic_report)
        help_menu.addAction(diagnostics_action)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: profiles
        profiles_widget = QWidget()
        profiles_layout = QVBoxLayout(profiles_widget)

        self.profile_list = QListWidget()
        self.profile_list.addItems(self.profiles.keys())
        self.profile_list.setCurrentRow(0)
        self.profile_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.profile_list.customContextMenuRequested.connect(self.show_profile_context_menu)
        self.profile_list.currentItemChanged.connect(self.on_profile_changed)
        profiles_layout.addWidget(self.profile_list)

        btn_layout = QHBoxLayout()
        new_btn = QPushButton("New")
        delete_btn = QPushButton("Delete")
        new_btn.clicked.connect(self.new_profile)
        delete_btn.clicked.connect(self.delete_profile)
        btn_layout.addWidget(new_btn)
        btn_layout.addWidget(delete_btn)
        profiles_layout.addLayout(btn_layout)

        # Right side: content
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        path_frame = QHBoxLayout()
        path_label = QLabel("Current Directory:")
        self.path_display = QLabel()

        # "Open Directory" button
        open_dir_btn = QPushButton("Open Directory")
        open_dir_btn.clicked.connect(self.open_current_directory)

        change_dir_btn = QPushButton("Change Directory")
        change_dir_btn.clicked.connect(self.edit_profile)

        path_frame.addWidget(path_label)
        path_frame.addWidget(self.path_display)
        path_frame.addWidget(open_dir_btn)
        path_frame.addWidget(change_dir_btn)
        content_layout.addLayout(path_frame)

        self.update_path_display()

        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://mod.io/g/game/m/mod")

        download_btn = QPushButton("Download")
        download_btn.clicked.connect(self.download_mod)

        check_updates_btn = QPushButton("Check for Updates")
        check_updates_btn.clicked.connect(self.check_updates)

        url_layout.addWidget(self.url_input)
        url_layout.addWidget(download_btn)
        url_layout.addWidget(check_updates_btn)
        content_layout.addLayout(url_layout)

        # Add search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search mods...")
        self.search_input.textChanged.connect(self.filter_mods)
        search_layout.addWidget(self.search_input)
        content_layout.addLayout(search_layout)

        # Make these four buttons the same width
        btn_size = 120
        download_btn.setFixedWidth(btn_size)
        check_updates_btn.setFixedWidth(btn_size)
        change_dir_btn.setFixedWidth(btn_size)
        open_dir_btn.setFixedWidth(btn_size)

        self.mod_tree = QTreeWidget()
        self.mod_tree.setHeaderLabels(["On", "Local", "Mod.io", "Installed"])
        self.mod_tree.setIndentation(0)
        self.mod_tree.setRootIsDecorated(False)
        self.mod_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.mod_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.mod_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.mod_tree.customContextMenuRequested.connect(self.show_mod_context_menu)
        self.mod_tree.itemChanged.connect(self.on_mod_status_changed)
        self.mod_tree.keyPressEvent = self.handle_mod_tree_keypress
        
        # Set fixed width for "On" column
        self.mod_tree.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.mod_tree.setColumnWidth(0, 30)
        
        # Enable sorting
        self.mod_tree.setSortingEnabled(True)
        self.mod_tree.header().setSectionsClickable(True)
        # Sort by Local name by default
        self.mod_tree.sortByColumn(1, Qt.AscendingOrder)

        content_layout.addWidget(self.mod_tree)
        content_layout.addWidget(self.progress_bar)

        splitter.addWidget(profiles_widget)
        splitter.addWidget(content_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

    def open_current_directory(self):
        """Opens the current profile's directory in the file explorer."""
        dir_path = self.path_display.text().strip()
        if dir_path:
            webbrowser.open(str(Path(dir_path)))

    def show_current_api_key_dialog(self):
        """
        Display the current API key in a dialog.
        If the user edits it, we save the new key to .env.
        """
        new_key, ok = QInputDialog.getText(
            self, "API Key",
            "View or edit your mod.io API Key:",
            QLineEdit.Normal,
            self.current_api_key
        )
        if ok:
            self.current_api_key = new_key.strip()
            self.save_api_key_to_env(self.current_api_key)
            QMessageBox.information(self, "API Key", "API Key updated successfully.")

    def save_api_key_to_env(self, new_key: str):
        env_path = Path('.env')
        if not env_path.exists():
            env_path.write_text(f'MODIO_API_KEY="{new_key}"\n')
        else:
            lines = env_path.read_text().splitlines()
            new_lines = []
            found_line = False
            for line in lines:
                if line.startswith("MODIO_API_KEY="):
                    new_lines.append(f'MODIO_API_KEY="{new_key}"')
                    found_line = True
                else:
                    new_lines.append(line)
            if not found_line:
                new_lines.append(f'MODIO_API_KEY="{new_key}"')
            env_path.write_text("\n".join(new_lines) + "\n")

    def open_manager_folder(self):
        folder_path = Path(__file__).parent.resolve()
        webbrowser.open(str(folder_path))

    def open_github_page(self):
        webbrowser.open("https://github.com/Sternenflame/modio-mod-manager/")

    def open_bug_report(self):
        """Open bug report page with pre-filled diagnostic information"""
        # Generate diagnostic info
        report = []
        report.append("### System Information")
        report.append(f"- OS: {sys.platform}")
        report.append(f"- Python Version: {sys.version.split()[0]}")
        report.append(f"- Available Memory: {psutil.virtual_memory().available / (1024*1024*1024):.1f} GB")
        report.append(f"- Available Disk Space: {psutil.disk_usage('.').free / (1024*1024*1024):.1f} GB")
        
        report.append("\n### Application Information")
        report.append(f"- Total Mods: {len(self.mod_db.get('mods', {}))}")
        report.append(f"- Total Profiles: {len(self.profiles)}")
        report.append(f"- Theme: {self.config['theme']}")
        report.append(f"- Auto Updates: {self.config['auto_check_updates']}")
        
        report.append("\n### Recent Operations")
        report.append(f"- Downloads: {self.stats['downloads']}")
        report.append(f"- Updates: {self.stats['updates']}")
        report.append(f"- Failures: {self.stats['failures']}")
        
        # Get last error from logs if exists
        try:
            log_dir = Path("logs")
            recent_logs = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
            if recent_logs:
                with open(recent_logs[0], 'r') as f:
                    lines = f.readlines()
                    errors = [line for line in lines if "ERROR" in line]
                    if errors:
                        report.append("\n### Last Error")
                        report.append("```")
                        report.append(errors[-1].strip())  # Only include last error
                        report.append("```")
        except Exception:
            pass  # Skip if can't read logs

        # Add additional information
        report.append("\n### Additional Information")
        report.append("#### Configuration Files")
        report.append(f"- config.json exists: {CONFIG_FILE.exists()}")
        report.append(f"- .env exists: {Path('.env').exists()}")
        report.append(f"- profiles.json exists: {self.profiles_file.exists()}")
        report.append(f"- moddb.json exists: {self.db_file.exists()}")
        
        report.append("\n#### Theme Settings")
        report.append(f"- Current theme: {self.config.get('theme', 'default')}")
        report.append(f"- Available themes: {list(self.COLORS.keys())}")
        
        report.append("\n#### Environment")
        report.append(f"- Working directory: {os.getcwd()}")
        report.append(f"- Python path: {sys.executable}")
        report.append(f"- Dependencies: {', '.join(sorted([f'{pkg.key}=={pkg.version}' for pkg in pkg_resources.working_set]))}")
        
        # URL encode the report text
        body = urllib.parse.quote("\n".join(report))
        
        # Open GitHub issue page with pre-filled template
        url = f"https://github.com/Sternenflame/modio-mod-manager/issues/new?assignees=&labels=bug&projects=&template=bug_report.md&body={body}"
        webbrowser.open(url)

    def update_path_display(self):
        current = self.profile_list.currentItem()
        if current:
            profile_name = current.text()
            current_path = self.profiles[profile_name]["mod_directory"]
            self.path_display.setText(current_path)

    def on_profile_changed(self, current, previous):
        if current:
            self.update_path_display()

    def new_profile(self):
        name, ok = QInputDialog.getText(self, 'New Profile', 'Enter profile name:')
        if ok and name:
            if name in self.profiles:
                QMessageBox.warning(self, "Error", "Profile name already exists!")
                return
            dir_path = QFileDialog.getExistingDirectory(self, "Select Mod Directory", str(Path.home()))
            if dir_path:
                self.profiles[name] = {
                    "mod_directory": dir_path,
                    "auto_extract": True
                }
                with open(self.profiles_file, 'w') as f:
                    json.dump(self.profiles, f, indent=4)
                self.profile_list.addItem(name)

    def edit_profile(self):
        """
        When changing directory, only move the files that are actually
        registered in the mod_db for this profile.
        """
        current = self.profile_list.currentItem()
        if not current:
            return
        profile_name = current.text()
        old_path = Path(self.profiles[profile_name]["mod_directory"])

        dir_path = QFileDialog.getExistingDirectory(self, "Select New Mod Directory", str(old_path))
        if dir_path and dir_path != str(old_path):
            new_path = Path(dir_path)
            self.logger.info(f"Changing profile '{profile_name}' from {old_path} to {new_path}")

            # Gather all relevant files from mod_db that are located in old_path
            to_move = []
            for mid, info in self.mod_db.get("mods", {}).items():
                if info.get("installed_path") == str(old_path):
                    # The mod's installed path is old_path, so we move only the files
                    # that this mod installed.
                    local_filename = info.get("local_name", "")
                    if local_filename:
                        old_file_path = old_path / local_filename
                        if old_file_path.is_file():
                            to_move.append(old_file_path)

            reply = QMessageBox.question(
                self, 'Confirm Path Change',
                f'Change the mod directory to:\n{new_path}\n\n'
                f'Will move {len(to_move)} file(s) from:\n{old_path}',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

            try:
                new_path.mkdir(parents=True, exist_ok=True)
                import shutil
                moved_count = 0
                for file_path in to_move:
                    new_file_path = new_path / file_path.name
                    shutil.move(str(file_path), str(new_file_path))
                    moved_count += 1

                # Update installed_path in the mod_db
                for mid, info in self.mod_db.get("mods", {}).items():
                    if info.get("installed_path") == str(old_path):
                        info["installed_path"] = str(new_path)

                self.profiles[profile_name]["mod_directory"] = str(new_path)
                with open(self.profiles_file, 'w') as f:
                    json.dump(self.profiles, f, indent=4)
                self.update_path_display()
                self.save_mod_db()

                QMessageBox.information(self, "Success",
                    f"Directory changed and {moved_count} file(s) migrated!")
            except Exception as e:
                self.logger.error(f"Failed to migrate files: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Failed to migrate files: {e}\nReverting changes...")
                self.profiles[profile_name]["mod_directory"] = str(old_path)
                self.update_path_display()

    def delete_profile(self):
        current = self.profile_list.currentItem()
        if not current:
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete profile \"{current.text()}\"?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            profile_name = current.text()
            if len(self.profiles) == 1:
                self.profiles = {
                    "Default": {
                        "mod_directory": str(Path("mods").resolve()),
                        "auto_extract": True
                    }
                }
                self.profile_list.clear()
                self.profile_list.addItem("Default")
            else:
                del self.profiles[profile_name]
                self.profile_list.takeItem(self.profile_list.row(current))

            with open(self.profiles_file, 'w') as f:
                json.dump(self.profiles, f, indent=4)

    def load_mod_db(self):
        if self.db_file.exists():
            try:
                with open(self.db_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load mod database: {e}")
                return {"mods": {}}
        return {"mods": {}}

    def save_mod_db(self):
        """Save mod database with backup"""
        try:
            # Create backup of existing DB
            if self.db_file.exists():
                backup_path = self.db_file.with_suffix('.json.bak')
                import shutil
                shutil.copy2(self.db_file, backup_path)
            
            # Save new DB
            with open(self.db_file, 'w') as f:
                json.dump(self.mod_db, f, indent=4)
        except Exception as e:
            self.logger.error(f"Failed to save mod database: {e}")
            QMessageBox.warning(self, "Error", f"Failed to save mod database: {e}")

    def refresh_mod_tree(self):
        """Refresh mod tree with progress for large lists"""
        self.mod_tree.clear()
        mods = list(self.mod_db.get("mods", {}).items())
        
        if len(mods) > 100:  # Only show progress for large lists
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
        
        for i, (mod_id, mod_info) in enumerate(mods):
            self.add_mod_to_tree(mod_id, mod_info)
            
            if len(mods) > 100:
                self.progress_bar.setValue(int((i + 1) * 100 / len(mods)))
                if i % 10 == 0:  # Process events periodically
                    QApplication.processEvents()
        
        self.progress_bar.setVisible(False)

    def add_mod_to_tree(self, mod_id, mod_info):
        item = QTreeWidgetItem()
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        checked = Qt.Checked if mod_info.get("enabled", True) else Qt.Unchecked
        item.setCheckState(0, checked)

        local_name = mod_info.get("local_name", mod_id)
        installed_date = mod_info.get("installed_date", "")
        try:
            dt = datetime.fromisoformat(installed_date)
            installed_date = dt.strftime("%Y-%m-%d %H:%M")
        except:
            pass

        mod_url = mod_info.get("url", "")
        modio_slug = mod_url
        if "/m/" in mod_url:
            parts = mod_url.split("/m/", 1)
            modio_slug = parts[1].replace("/", "")

        item.setText(1, local_name)    # Local
        item.setText(2, modio_slug)    # Mod.io
        item.setText(3, installed_date)
        self.mod_tree.addTopLevelItem(item)

    def show_profile_context_menu(self, position):
        current = self.profile_list.currentItem()
        if not current:
            return
        context_menu = QMenu()
        rename_action = context_menu.addAction("Rename")
        edit_dir_action = context_menu.addAction("Change Directory")

        action = context_menu.exec_(self.profile_list.mapToGlobal(position))
        if action == rename_action:
            self.rename_profile()
        elif action == edit_dir_action:
            self.edit_profile()

    def rename_profile(self):
        current = self.profile_list.currentItem()
        if not current or current.text() == "Default":
            return

        old_name = current.text()
        new_name, ok = QInputDialog.getText(self, 'Rename Profile', 'Enter new profile name:', QLineEdit.Normal, old_name)
        if ok and new_name and new_name != old_name:
            if new_name in self.profiles:
                QMessageBox.warning(self, "Error", "Profile name already exists!")
                return
            self.profiles[new_name] = self.profiles.pop(old_name)
            with open(self.profiles_file, 'w') as f:
                json.dump(self.profiles, f, indent=4)
            current.setText(new_name)

    def show_mod_context_menu(self, position):
        """Show context menu for mod tree"""
        selected_items = self.mod_tree.selectedItems()
        if not selected_items:
            return

        context_menu = QMenu()
        
        # Adjust menu text based on selection count
        if len(selected_items) == 1:
            open_in_browser_action = context_menu.addAction("Open in Browser")
            open_in_browser_action.triggered.connect(
                lambda: self.open_mod_in_browser(selected_items[0])
            )
            
        delete_text = "Delete Selected Mods" if len(selected_items) > 1 else "Delete Mod"
        delete_action = context_menu.addAction(delete_text)
        delete_action.triggered.connect(self.delete_selected_mods)

        context_menu.exec_(self.mod_tree.mapToGlobal(position))

    def open_mod_in_browser(self, tree_item):
        mod_name = tree_item.text(1)
        found_mod_id = None
        for mid, info in self.mod_db.get("mods", {}).items():
            local_name = info.get("local_name", mid)
            if local_name == mod_name:
                found_mod_id = mid
                break
        if not found_mod_id:
            return
        mod_info = self.mod_db["mods"][found_mod_id]
        mod_url = mod_info.get("url", "")
        if mod_url:
            webbrowser.open(mod_url)

    def delete_selected_mods(self):
        """Delete all selected mods"""
        # Add profile check
        current_profile = self.profile_list.currentItem()
        if not current_profile:
            QMessageBox.warning(self, "Error", "No profile selected.")
            return
        profile_name = current_profile.text()

        selected_items = self.mod_tree.selectedItems()
        if not selected_items:
            return

        # Filter mods by current profile
        mod_names = [
            item.text(1) for item in selected_items 
            if self.mod_db.get("mods", {}).get(item.text(1), {}).get("profile") == profile_name
        ]
        
        if not mod_names:
            QMessageBox.warning(self, "Error", "No mods selected from current profile.")
            return

        if len(mod_names) == 1:
            message = f"Are you sure you want to delete mod '{mod_names[0]}'?"
        else:
            message = f"Are you sure you want to delete {len(mod_names)} mods?"

        reply = QMessageBox.question(
            self, "Confirm Delete",
            message,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for mod_name in mod_names:
                found_mod_id = None
                for mid, info in list(self.mod_db.get("mods", {}).items()):
                    local_name = info.get("local_name", mid)
                    if local_name == mod_name:
                        found_mod_id = mid
                        break
                    
                if found_mod_id:
                    mod_info = self.mod_db["mods"][found_mod_id]
                    path_str = mod_info.get("installed_path", "")
                    if path_str:
                        # Delete from main directory
                        main_dir = Path(path_str)
                        if main_dir.is_dir():
                            main_files = list(main_dir.glob(f"*{mod_name}*"))
                            for f in main_files:
                                try:
                                    self.logger.info(f"Deleting enabled file: {f}")
                                    f.unlink(missing_ok=True)
                                except Exception as e:
                                    self.logger.error(f"Failed to delete enabled file {f}: {e}")
                        
                        # Delete from disabled directory
                        disabled_dir = main_dir / ".disabledmods"
                        if disabled_dir.is_dir():
                            disabled_files = list(disabled_dir.glob(f"*{mod_name}*"))
                            for f in disabled_files:
                                try:
                                    self.logger.info(f"Deleting disabled file: {f}")
                                    f.unlink(missing_ok=True)
                                except Exception as e:
                                    self.logger.error(f"Failed to delete disabled file {f}: {e}")
                    
                    # Remove from database
                    del self.mod_db["mods"][found_mod_id]
                    self.logger.info(f"Removed mod {mod_name} from database")

            self.save_mod_db()
            self.refresh_mod_tree()
            self.logger.info(f"Deleted {len(mod_names)} mod(s)")

    def extract_mod(self, mod_path: Path, remove_zip=False, progress_callback=None) -> list[str]:
        """Extract mod with chunked processing to prevent UI freezing"""
        try:
            if not mod_path.exists():
                raise FileNotFoundError(f"File not found: {mod_path}")
            
            if not mod_path.is_file():
                raise ValueError(f"Path is not a file: {mod_path}")
            
            if mod_path.suffix.lower() != '.zip':
                raise ValueError(f"File is not a ZIP archive: {mod_path}")
            
            extracted_files = []
            if not mod_path.exists():
                self.logger.warning(f"File not found: {mod_path}")
                return extracted_files

            CHUNK_SIZE = 1024 * 1024  # 1MB chunks
            try:
                # Add small delay to ensure file is released
                QApplication.processEvents()
                time.sleep(0.5)  # 500ms delay
                
                with zipfile.ZipFile(mod_path, 'r') as zip_ref:
                    self.logger.info(f"Reading ZIP contents of {mod_path.name}...")
                    
                    # Filter valid files
                    valid_files = [
                        f for f in zip_ref.namelist() 
                        if not (f.endswith('/') or f.endswith('\\') or '.disabledmods' in f)
                    ]
                    
                    total_files = len(valid_files)
                    if total_files == 0:
                        return extracted_files

                    # Calculate total size for progress
                    total_size = sum(zip_ref.getinfo(name).file_size for name in valid_files)
                    processed_size = 0

                    for i, member in enumerate(valid_files, 1):
                        source = None
                        try:
                            # Get file info
                            info = zip_ref.getinfo(member)
                            target_path = Path(mod_path.parent) / member

                            # Create parent directories
                            target_path.parent.mkdir(parents=True, exist_ok=True)

                            # Extract file in chunks
                            source = zip_ref.open(member)
                            with open(target_path, 'wb') as target:
                                while True:
                                    chunk = source.read(CHUNK_SIZE)
                                    if not chunk:
                                        break
                                    target.write(chunk)
                                    processed_size += len(chunk)
                                    
                                    # Update progress only through callback
                                    if progress_callback:
                                        progress = int((processed_size / total_size) * 100)
                                        progress_callback(progress)
                                    QApplication.processEvents()
                        finally:
                            if source:
                                source.close()

                        extracted_files.append(Path(member).name)
                        QApplication.processEvents()

                # Add small delay before removing zip
                QApplication.processEvents()
                time.sleep(0.5)  # 500ms delay

                # Remove ZIP if requested
                if remove_zip and mod_path.exists():
                    mod_path.unlink()
                    self.logger.info(f"Removed ZIP file: {mod_path}")

                self.logger.info(f"Extracted {len(extracted_files)} file(s) from {mod_path.name}.")

            except Exception as e:
                self.logger.error(f"Failed to extract mod: {e}")
                extracted_files.clear()
                raise

            return extracted_files

        except Exception as e:
            self.logger.error(f"Failed to extract mod: {e}")
            return []

    def on_mod_status_changed(self, item, column):
        if column != 0:
            return
        if self.block_mod_status_change:
            return

        is_enabled = (item.checkState(0) == Qt.Checked)
        mod_name = item.text(1)
        self.logger.info(f"Toggling mod: {mod_name}, is_enabled={is_enabled}")

        # Look up DB by the actual key = local_name
        if mod_name not in self.mod_db.get("mods", {}):
            self.logger.warning(f"Mod '{mod_name}' not found in DB by local_name key.")
            return

        mod_info = self.mod_db["mods"][mod_name]
        profile_dir = Path(mod_info["installed_path"])
        disabled_dir = profile_dir / ".disabledmods"
        disabled_dir.mkdir(exist_ok=True)

        try:
            import shutil
            file_candidate = list(profile_dir.glob(f"*{mod_name}*"))
            disabled_candidate = list(disabled_dir.glob(f"*{mod_name}*"))

            if is_enabled:
                # If the file is in disabledmods, move it back
                if disabled_candidate:
                    for f in disabled_candidate:
                        shutil.move(str(f), str(profile_dir / f.name))
                    self.logger.info(f"Enabled mod: {mod_name}")
                else:
                    # Possibly it's already in the main folder, do nothing
                    if not file_candidate:
                        QMessageBox.warning(
                            self, "Error",
                            f"No mod files found for '{mod_name}' in:\n{profile_dir}\nor {disabled_dir}\nCannot enable/disable."
                        )
                        self.block_mod_status_change = True
                        item.setCheckState(0, Qt.Unchecked)
                        self.block_mod_status_change = False
                        return
            else:
                # Move it to disabledmods folder
                if file_candidate:
                    for f in file_candidate:
                        shutil.move(str(f), str(disabled_dir / f.name))
                    self.logger.info(f"Disabled mod: {mod_name}")
                else:
                    # Maybe it's already disabled
                    if not disabled_candidate:
                        QMessageBox.warning(
                            self, "Error",
                            f"No mod files found for '{mod_name}' in:\n{profile_dir}\nor {disabled_dir}\nCannot enable/disable."
                        )
                        self.block_mod_status_change = True
                        item.setCheckState(0, Qt.Checked)
                        self.block_mod_status_change = False
                        return

            self.mod_db["mods"][mod_name]["enabled"] = is_enabled
            self.save_mod_db()

        except Exception as e:
            self.logger.error(f"Failed to change mod state: {str(e)}", exc_info=False)
            self.block_mod_status_change = True
            item.setCheckState(0, Qt.Unchecked if is_enabled else Qt.Checked)
            self.block_mod_status_change = False

    def handle_mod_tree_keypress(self, event):
        """Handle keyboard shortcuts for mod tree"""
        if event.key() == Qt.Key_Delete:
            self.delete_selected_mods()
        else:
            # Call original keyPressEvent for default handling (like navigation)
            QTreeWidget.keyPressEvent(self.mod_tree, event)

    def safe_file_move(self, src: Path, dst: Path) -> bool:
        """Safely move file with fallback to copy+delete"""
        try:
            # Ensure destination directory exists
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            # Remove destination if it exists
            if dst.exists():
                dst.unlink()
            
            # Try to move file
            src.rename(dst)
            return True
        except Exception as e:
            self.logger.warning(f"Direct move failed, trying copy+delete: {e}")
            try:
                import shutil
                shutil.copy2(src, dst)
                src.unlink()
                return True
            except Exception as e2:
                self.logger.error(f"File operation failed: {e2}")
                return False

    def update_mod_state(self, mod_name: str, is_enabled: bool) -> bool:
        """Update mod state with proper error handling"""
        try:
            mod_info = self.mod_db["mods"][mod_name]
            profile_dir = Path(mod_info["installed_path"])
            disabled_dir = profile_dir / ".disabledmods"
            
            src_dir = profile_dir if not is_enabled else disabled_dir
            dst_dir = disabled_dir if not is_enabled else profile_dir
            
            files = list(src_dir.glob(f"*{mod_name}*"))
            if not files:
                return False
            
            for f in files:
                if not self.safe_file_move(f, dst_dir / f.name):
                    return False
                
            self.mod_db["mods"][mod_name]["enabled"] = is_enabled
            self.save_mod_db()
            return True
        except Exception as e:
            self.logger.error(f"Failed to update mod state: {e}")
            return False

    def filter_mods(self, text):
        """Filter mods based on search text"""
        search_text = text.lower()
        
        # If empty search, show all items
        if not search_text:
            for i in range(self.mod_tree.topLevelItemCount()):
                self.mod_tree.topLevelItem(i).setHidden(False)
            return

        for i in range(self.mod_tree.topLevelItemCount()):
            item = self.mod_tree.topLevelItem(i)
            local_name = item.text(1)  # Local name column
            
            # Get additional searchable fields from the database
            mod_info = self.mod_db["mods"].get(local_name, {})
            searchable_fields = [
                local_name.lower(),                    # Local name
                mod_info.get("name", "").lower(),     # Name
                mod_info.get("zip_name", "").lower(), # ZIP name
                mod_info.get("url", "").lower(),      # Full URL
            ]
            
            # Add mod.io slug if URL exists
            mod_url = mod_info.get("url", "")
            if "/m/" in mod_url:
                try:
                    parts = mod_url.split("/m/", 1)
                    modio_slug = parts[1].replace("/", "").lower()
                    searchable_fields.append(modio_slug)
                except:
                    pass
            
            # Show item if search text matches any field
            item.setHidden(not any(search_text in field for field in searchable_fields))

    def generate_diagnostic_report(self):
        """Generate a diagnostic report"""
        report = []
        report.append("=== Diagnostic Report ===")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append(f"Uptime: {datetime.now() - self.stats['start_time']}")
        report.append("\n=== System Information ===")
        report.append(f"Python Version: {sys.version}")
        report.append(f"OS: {sys.platform}")
        report.append(f"CPU Usage: {psutil.cpu_percent()}%")
        report.append(f"Memory Usage: {psutil.Process().memory_info().rss / 1024 / 1024:.1f} MB")
        report.append(f"Available Disk Space: {psutil.disk_usage('.').free / 1024 / 1024 / 1024:.1f} GB")
        
        report.append("\n=== Application Statistics ===")
        report.append(f"Total Downloads: {self.stats['downloads']}")
        report.append(f"Total Updates: {self.stats['updates']}")
        report.append(f"Failed Operations: {self.stats['failures']}")
        report.append(f"Total Data Transferred: {self.stats['total_size'] / 1024 / 1024:.1f} MB")
        
        report.append("\n=== Configuration ===")
        report.append(f"Current Theme: {self.config['theme']}")
        report.append(f"Auto-Check Updates: {self.config['auto_check_updates']}")
        report.append(f"Backup Count: {self.config['backup_count']}")
        report.append(f"Download Retries: {self.config['download_retries']}")
        
        report.append("\n=== Database Status ===")
        report.append(f"Total Mods: {len(self.mod_db.get('mods', {}))}")
        report.append(f"Total Profiles: {len(self.profiles)}")
        report.append(f"Database Size: {os.path.getsize(self.db_file) / 1024:.1f} KB")
        
        report.append("\n=== Recent Logs ===")
        try:
            log_dir = Path("logs")
            recent_logs = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
            if recent_logs:
                with open(recent_logs[0], 'r') as f:
                    last_lines = f.readlines()[-10:]  # Last 10 lines
                report.append("Last 10 log entries:")
                report.extend(last_lines)
        except Exception as e:
            report.append(f"Failed to read logs: {e}")
        
        # Save report
        report_text = "\n".join(report)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = Path("logs") / f"diagnostic_report_{timestamp}.txt"
        report_file.write_text(report_text)
        
        return report_text

    def show_diagnostic_report(self):
        """Show diagnostic report in a dialog"""
        report = self.generate_diagnostic_report()
        dialog = QDialog(self)
        dialog.setWindowTitle("Diagnostic Report")
        dialog.resize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(report)
        layout.addWidget(text_edit)
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Save
        )
        button_box.accepted.connect(dialog.accept)
        button_box.button(QDialogButtonBox.Save).clicked.connect(
            lambda: self.save_diagnostic_report(report)
        )
        layout.addWidget(button_box)
        
        dialog.exec_()

    def save_diagnostic_report(self, report):
        """Save diagnostic report to a file"""
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Diagnostic Report",
            str(Path.home() / "diagnostic_report.txt"),
            "Text Files (*.txt)"
        )
        if file_name:
            try:
                Path(file_name).write_text(report)
                QMessageBox.information(self, "Success", "Diagnostic report saved successfully!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save report: {e}")

    def show_api_key_setup_dialog(self):
        """Show API key setup dialog with mod.io link"""
        dialog = QDialog(self)
        dialog.setWindowTitle("API Key Setup")
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)

        # Instructions
        instructions = QLabel(
            "To use this application, you need a mod.io API key.\n\n"
            "To get your API key:\n"
            "1. Go to mod.io and create an account\n"
            "2. Visit mod.io/me/access\n"
            "3. Under 'API Access', click 'Get API key'\n"
            "4. Copy and paste your API key below"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Open Website button
        open_website_btn = QPushButton("Open mod.io/me/access")
        open_website_btn.clicked.connect(lambda: webbrowser.open('https://mod.io/me/access'))
        layout.addWidget(open_website_btn)

        # API Key input
        key_layout = QHBoxLayout()
        key_label = QLabel("API Key:")
        key_input = QLineEdit()
        key_layout.addWidget(key_label)
        key_layout.addWidget(key_input)
        layout.addLayout(key_layout)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        while True:
            if dialog.exec_() == QDialog.Accepted:
                api_key = key_input.text().strip()
                if not api_key:
                    QMessageBox.warning(dialog, "Error", "Please enter an API key.")
                    continue
                
                if not Config.validate_api_key(api_key):
                    QMessageBox.warning(dialog, "Error", 
                        "Invalid API key format. Please check your key and try again.")
                    continue
                
                # Save the API key
                self.current_api_key = api_key
                self.save_api_key_to_env(api_key)
                break
            else:
                # User clicked Cancel
                sys.exit(0)

def main():
    # Create QApplication first
    app = QApplication(sys.argv)

    # Initialize application
    try:
        logger = initialize_application(gui_mode=True)
    except Exception as e:
        QMessageBox.critical(None, "Startup Error", 
            f"Failed to initialize application: {e}\n\nPlease check the logs for details.")
        sys.exit(1)

    window = ModDownloaderGUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
