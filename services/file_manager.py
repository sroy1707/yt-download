import os
import re
import string
import platform

def get_system_info_service():
    """Detect operating system (Windows, macOS, Linux) and return system details."""
    system_name = platform.system()
    
    if system_name == 'Windows':
        os_type = 'windows'
        os_label = 'Windows'
        icon = '🪟'
    elif system_name == 'Darwin':
        os_type = 'mac'
        os_label = 'macOS'
        icon = '🍎'
    else:
        os_type = 'linux'
        os_label = 'Linux'
        icon = '🐧'

    return {
        'os_type': os_type,
        'os_label': os_label,
        'icon': icon,
        'platform_details': platform.platform(),
        'sep': os.sep
    }

def get_quick_dirs_service():
    """Returns standard system directories tailored for Windows, macOS, or Linux."""
    cwd = os.getcwd()
    home = os.path.expanduser('~')
    system_info = get_system_info_service()

    dirs = [
        {'name': '💻 Current Workspace', 'path': cwd},
        {'name': '📥 Downloads', 'path': os.path.join(home, 'Downloads')},
        {'name': '🎬 Videos', 'path': os.path.join(home, 'Movies' if system_info['os_type'] == 'mac' else 'Videos')},
        {'name': '🖥️ Desktop', 'path': os.path.join(home, 'Desktop')},
        {'name': '📁 Documents', 'path': os.path.join(home, 'Documents')},
        {'name': '🏠 Home', 'path': home}
    ]

    # OS-Specific External Mount Points & Drives
    if system_info['os_type'] == 'windows':
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                dirs.append({'name': f'💾 Drive ({letter}:)', 'path': drive})
    elif system_info['os_type'] == 'mac':
        if os.path.exists('/Volumes'):
            dirs.append({'name': '💾 Mounted Volumes', 'path': '/Volumes'})
    elif system_info['os_type'] == 'linux':
        username = os.path.basename(home)
        media_path = f'/media/{username}'
        if os.path.exists(media_path):
            dirs.append({'name': '💾 External Media', 'path': media_path})
        if os.path.exists('/mnt'):
            dirs.append({'name': '💾 Mnt Disks', 'path': '/mnt'})

    valid_dirs = [d for d in dirs if os.path.exists(d['path'])]
    return {
        'system': system_info,
        'directories': valid_dirs
    }

def list_folders_service(start_path):
    """List subdirectories inside start_path with robust Windows drive letter support."""
    if not start_path or not start_path.strip():
        start_path = os.getcwd()
    else:
        start_path = start_path.strip()

    # Normalize Windows drive letters like "C:" -> "C:\"
    if re.match(r'^[a-zA-Z]:$', start_path):
        start_path = start_path + '\\'
    
    start_path = os.path.expanduser(start_path)
    start_path = os.path.abspath(start_path)
    start_path = os.path.normpath(start_path)

    if not os.path.exists(start_path):
        return {'success': False, 'message': f'Path does not exist: {start_path}'}

    if not os.path.isdir(start_path):
        start_path = os.path.dirname(start_path)

    folders = []
    try:
        with os.scandir(start_path) as entries:
            for entry in entries:
                try:
                    if entry.is_dir() and not entry.name.startswith('.'):
                        folders.append({
                            'name': entry.name,
                            'path': os.path.normpath(entry.path)
                        })
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError) as e:
        return {'success': False, 'message': f'Cannot access directory: {str(e)}'}

    folders.sort(key=lambda x: x['name'].lower())

    parent_path = os.path.dirname(start_path)
    if parent_path == start_path:
        parent_path = None

    return {
        'success': True,
        'current_path': start_path,
        'parent_path': parent_path,
        'folders': folders
    }

def create_folder_service(parent_path, folder_name):
    """Creates a new folder inside parent_path with cross-platform normalization."""
    if not parent_path or not folder_name:
        return {'success': False, 'message': 'Parent path and folder name required.'}

    clean_name = folder_name.strip()
    if not clean_name:
        return {'success': False, 'message': 'Invalid folder name.'}

    parent_dir = os.path.normpath(os.path.abspath(parent_path.strip()))
    full_path = os.path.normpath(os.path.join(parent_dir, clean_name))

    try:
        os.makedirs(full_path, exist_ok=True)
        return {'success': True, 'path': full_path}
    except Exception as e:
        return {'success': False, 'message': str(e)}
