# Mod.io Mod Manager

A modern GUI application to download and manage mods from mod.io. Features automatic download, extraction, and profile management.

## Features

- 🖥️ Modern GUI interface with customizable themes
- 📂 Multiple profile support for different games/directories
- 🔄 Automatic mod updates and version tracking
- 🎮 Mod enable/disable functionality
- 🔍 Search and filter mods
- 🎨 Six carefully designed themes:
- 📊 Built-in diagnostics and error reporting
- ⌨️ Keyboard shortcuts for common operations

## Requirements

- [Python 3.10+](https://www.python.org/downloads/)
- mod.io account and [API key](https://mod.io/me/access)

## Installation

### Windows
```bash
# Clone the repository
git clone https://github.com/Sternenflame/modio-mod-manager.git

# Navigate to directory
cd modio-mod-manager

# Run the application
python gui.py
```

### Linux/MacOS
```bash
# Clone the repository
git clone https://github.com/Sternenflame/modio-mod-manager.git

# Navigate to directory
cd modio-mod-manager

# Make the script executable
chmod +x gui.py

# Run the application
./gui.py
```

The program will automatically check and install required dependencies on first run.

## Usage

### First Time Setup
1. Launch the application
2. Enter your mod.io API key when prompted (or later via Options → API Key)
3. Create a profile and select your mod directory

### Managing Mods
- **Download**: Paste a mod.io URL and click Download
- **Enable/Disable**: Use the checkbox in the "On" column
- **Update**: Click "Check for Updates" to update all mods
- **Delete**: Select mods and press Delete or use right-click menu
- **Search**: Use the search bar to filter mods
- **Multi-select**: Use Shift/Ctrl + Click to select multiple mods

### Profiles
- Create multiple profiles for different games
- Each profile has its own mod directory

### Themes
- Choose from six carefully designed themes
- Customize via Options → Preferences
  - White: Pure white theme for bright environments
  - Light Grey: Soft grey for reduced eye strain
  - Grey: Balanced medium grey
  - Dark Grey: Professional dark theme
  - Key: Modern slate grey theme (default)
  - Black: Classic dark theme

## Troubleshooting

Common issues:
- **Invalid API key**: Update your key via Options → API Key
- **Download fails**: Check your internet connection and mod URL
- **Extraction fails**: Ensure you have write permissions to the mod directory
- **Mod not found**: Verify the mod is public and the URL is correct

For detailed diagnostics:
1. Go to Help → Show Diagnostics
2. Review the information
3. Save the report if needed

## Bug Reports

When reporting issues:
1. Go to Help → Report a Bug
2. The report will automatically include:
   - System information
   - Application settings
   - Recent operations
   - Error logs (if any)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

The MIT License was chosen for this project because:
- It's simple and permissive
- Allows commercial use
- Allows modification and distribution
- Provides liability protection
- Compatible with most other licenses
- Widely used in open source

This means you can:
- Use the code commercially
- Modify the code
- Distribute the code
- Use it privately
- Sublicense the code

The only requirement is that you include the original copyright notice and license terms.
