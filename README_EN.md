# my_file_browser - Dual Pane File Browser

A macOS Finder-inspired dual pane file browser application built with Python and Tkinter, supporting both local file systems and SFTP remote file access.

## Features

- 🖼️ **Dual Pane Interface**: macOS Finder-style dual pane design with independent left/right panel browsing
- 📁 **Complete File Operations**: Support for copy, move, delete, rename, and other file/folder operations
- 🌐 **SFTP Support**: Integrated paramiko library for remote SFTP server file access
- 🔍 **Smart Search**: File name search and filtering capabilities
- 📊 **Multiple View Modes**: Icon view, list view, and detailed information view
- 🎨 **Modern UI**: macOS-inspired interface design, beautiful and user-friendly
- ⚡ **High Performance**: Support for large file operations and batch processing

## System Requirements

- **Operating System**: macOS 10.12+, Windows 10+, or Linux
- **Python Version**: Python 3.6 or higher
- **Dependencies**:
  - tkinter (Python standard library)
  - paramiko (optional, for SFTP functionality)

## Installation

### 1. Clone or Download the Project
```bash
git clone <repository-url>
cd my_file_browser
```

### 2. Install Dependencies
```bash
pip install paramiko
```

### 3. Run the Application
```bash
python3 "my_file_browser 1.5.5.py"
```

### 4. Add Execute Permissions (Optional)
```bash
chmod +x "my_file_browser 1.5.5.py"
./"my_file_browser 1.5.5.py"
```

## Usage Guide

### Basic Operations

1. **Navigation**: Use sidebar for quick access to devices and important directories
2. **File Operations**: Right-click menu provides complete file operation functions
3. **Drag & Drop**: Support for drag and drop file operations
4. **Keyboard Shortcuts**:
   - `Ctrl+C` / `Ctrl+V`: Copy/Paste
   - `Delete`: Delete files
   - `F5`: Refresh current directory

### SFTP Connection

1. Click the SFTP button in the toolbar
2. Enter server information: host, port, username, password
3. After successful connection, SFTP device will appear in the sidebar

### View Modes

- **Icon View**: Display file icons with large thumbnails
- **List View**: Compact file list display
- **Details View**: Show file size, modification time, and other detailed information

## Configuration File

The application uses `my_file_browser.ini` file to save settings:

```ini
{
    "window_geometry": "1200x700+100+100",
    "left_browser_path": "/",
    "right_browser_path": "/",
    "sftp_info": {
        "host": "",
        "port": "22",
        "username": "",
        "password": "",
        "path": "/"
    }
}
```

## Project Structure

```
my_file_browser/
├── my_file_browser 1.5.5.py    # Main application file
├── my_file_browser.ini         # Configuration file
└── README_EN.md                # Project documentation (English)
```

## Core Classes

### Sidebar Class
- Sidebar component displaying devices and locations
- Supports automatic device list refresh
- Provides quick navigation functionality

### FileBrowser Class
- Main file browser interface
- Handles file operations and view management
- Integrates SFTP functionality

### SftpFileSystem Class
- SFTP file system wrapper
- Provides local file system-like interface
- Handles remote file operations

## Development Notes

### Code Features
- Object-oriented design with modular structure
- Comprehensive error handling and exception catching
- Support for multi-threaded operations
- Internationalization support (Chinese/English interface)

### Extensible Features
Easily extendable with the following features:
- Plugin system
- Theme switching
- More file format previews
- Cloud storage integration

## Troubleshooting

### Common Issues

1. **SFTP Connection Failure**
   - Check network connection
   - Verify server information is correct
   - Check if paramiko library is installed

2. **File Operation Permission Errors**
   - Check file/folder permissions
   - Ensure sufficient operation privileges

3. **Interface Display Issues**
   - Check Python and tkinter versions
   - Try resetting configuration file

### Debug Mode

Start with debug parameter:
```bash
python3 "my_file_browser 1.5.5.py" --debug
```

## Version Information

- **Current Version**: 1.5.5
- **Release Date**: 2025/10/27
- **Developer**: Shylock Wolf

## License

This project uses the MIT open source license, free to use and modify.

## Contributing

Welcome to submit Issues and Pull Requests to improve the project.

## Contact

For questions or suggestions, please contact the developer.

---

*Making file management simpler and more efficient!*