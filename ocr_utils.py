import os
import shutil


def _is_executable_path(candidate: str) -> bool:
    if not candidate:
        return False
    if os.path.isabs(candidate):
        return os.path.exists(candidate)
    return shutil.which(candidate) is not None


def resolve_tesseract_cmd() -> str:
    env_cmd = (os.getenv('TESSERACT_CMD') or '').strip().strip('"').strip("'")
    candidates = []

    if env_cmd:
        if os.name == 'nt' and env_cmd.startswith('/'):
            env_cmd = ''
        elif os.name != 'nt' and ':' in env_cmd and '\\' in env_cmd:
            env_cmd = ''

    if env_cmd:
        candidates.append(env_cmd)

    if os.name == 'nt':
        candidates.extend([
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            'tesseract.exe',
        ])
    else:
        candidates.extend([
            '/usr/bin/tesseract',
            '/usr/local/bin/tesseract',
            'tesseract',
        ])

    path_on_system = shutil.which('tesseract')
    if path_on_system:
        candidates.insert(0, path_on_system)

    for candidate in candidates:
        if _is_executable_path(candidate):
            return candidate

    return 'tesseract.exe' if os.name == 'nt' else 'tesseract'


def resolve_poppler_path() -> str | None:
    env_path = (os.getenv('POPPLER_PATH') or '').strip().strip('"').strip("'")
    candidates = []

    if env_path:
        if os.name == 'nt' and env_path.startswith('/'):
            env_path = ''
        elif os.name != 'nt' and ':' in env_path and '\\' in env_path:
            env_path = ''

    if env_path:
        candidates.append(env_path)

    if os.name == 'nt':
        candidates.extend([
            r'C:\Program Files\poppler\Library\bin',
            r'C:\Program Files (x86)\poppler\Library\bin',
            r'C:\Poppler\poppler-23.01.0\Library\bin',
            r'C:\Poppler\Library\bin',
        ])
    else:
        candidates.extend([
            '/usr/bin',
            '/usr/local/bin',
        ])

    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate

    return env_path or None