"""Small Windows adapter. No shell strings, arbitrary keystrokes or file reads."""
import ctypes
import os
from pathlib import Path
import subprocess
import uuid
import webbrowser
from urllib.parse import quote, urlsplit


def supported():
    return os.name == 'nt'


def _volume(percent=None, delta=None):
    """Set and read back default multimedia endpoint volume using Windows Core Audio COM."""
    class GUID(ctypes.Structure):
        _fields_ = [('a', ctypes.c_uint32), ('b', ctypes.c_uint16), ('c', ctypes.c_uint16), ('d', ctypes.c_ubyte*8)]

    def guid(value):
        return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)

    def method(pointer, index, *types):
        address = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0][index]
        return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *types)(address)

    def check(result):
        if result < 0:
            raise OSError('Windows Core Audio is unavailable.')

    ole = ctypes.OleDLL('ole32')
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ole.CoInitializeEx.restype = ctypes.c_long
    ole.CoCreateInstance.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
    ole.CoCreateInstance.restype = ctypes.c_long
    initialized = ole.CoInitializeEx(None, 2)
    check(initialized)
    enumerator, device, endpoint = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    try:
        check(ole.CoCreateInstance(ctypes.byref(guid('bcde0395-e52f-467c-8e3d-c4579291692e')), None, 1,
                                  ctypes.byref(guid('a95664d2-9614-4f35-a746-de8db63617e6')), ctypes.byref(enumerator)))
        check(method(enumerator, 4, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(enumerator, 0, 1, ctypes.byref(device)))
        check(method(device, 3, ctypes.POINTER(GUID), ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(
            device, ctypes.byref(guid('5cdf2c82-841e-4546-9722-0cf74078229a')), 23, None, ctypes.byref(endpoint)))
        if delta is not None:
            current = ctypes.c_float()
            check(method(endpoint, 9, ctypes.POINTER(ctypes.c_float))(endpoint, ctypes.byref(current)))
            percent = max(0,min(100,round(current.value*100)+delta))
        check(method(endpoint, 7, ctypes.c_float, ctypes.c_void_p)(endpoint, percent/100, None))
        actual = ctypes.c_float()
        check(method(endpoint, 9, ctypes.POINTER(ctypes.c_float))(endpoint, ctypes.byref(actual)))
        return round(actual.value*100)
    finally:
        for pointer in (endpoint, device, enumerator):
            if pointer:
                release = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0][2]
                ctypes.WINFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p)(release)(pointer)
        ole.CoUninitialize()


def _media(command):
    """Send a media key to the Windows active media session (not a verified Spotify result)."""
    from ctypes import wintypes as w
    class Keyboard(ctypes.Structure):
        _fields_ = [('vk', w.WORD), ('scan', w.WORD), ('flags', w.DWORD), ('time', w.DWORD), ('extra', ctypes.c_size_t)]
    class Mouse(ctypes.Structure):
        _fields_ = [('x', w.LONG), ('y', w.LONG), ('data', w.DWORD), ('flags', w.DWORD), ('time', w.DWORD), ('extra', ctypes.c_size_t)]
    class Hardware(ctypes.Structure):
        _fields_ = [('message', w.DWORD), ('low', w.WORD), ('high', w.WORD)]
    class Data(ctypes.Union):
        _fields_ = [('keyboard', Keyboard), ('mouse', Mouse), ('hardware', Hardware)]
    class Input(ctypes.Structure):
        _anonymous_ = ('data',)
        _fields_ = [('type', w.DWORD), ('data', Data)]
    codes = {'next':0xB0, 'previous':0xB1, 'play_pause':0xB3}
    events = (Input*2)()
    for index, flags in enumerate((0, 2)):
        events[index].type = 1
        events[index].keyboard = Keyboard(codes[command], 0, flags, 0, 0)
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.SendInput.argtypes = [w.UINT, ctypes.POINTER(Input), ctypes.c_int]
    user.SendInput.restype = w.UINT
    if user.SendInput(2, events, ctypes.sizeof(Input)) != 2:
        raise OSError('Windows did not accept the media command.')


SETTINGS_PAGES = {'themes':'ms-settings:themes', 'background':'ms-settings:personalization-background',
                  'display':'ms-settings:display', 'sound':'ms-settings:sound',
                  'bluetooth':'ms-settings:bluetooth', 'apps':'ms-settings:appsfeatures'}


def website(value):
    if not isinstance(value,str) or len(value)>2000 or any(ord(c)<33 for c in value) or '\\' in value:
        raise ValueError('Enter an HTTP or HTTPS website address without spaces.')
    try:
        parsed=urlsplit(value)
        if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Only HTTP/HTTPS websites without embedded credentials can be opened.')
        parsed.port
    except (ValueError,UnicodeError):
        raise ValueError('Enter a valid HTTP/HTTPS website address without embedded credentials.') from None
    return value


def execute(action, target=None):
    if not supported():
        raise OSError('Computer controls require the Windows copy of JARVIS.')
    kind = action['kind']
    if kind == 'volume':
        actual = _volume(action.get('percent'), action.get('delta'))
        return f'Windows master volume reads {actual} percent.'
    if kind == 'media':
        _media(action['command'])
        label = {'next':'Next track', 'previous':'Previous track', 'play_pause':'Play/pause'}[action['command']]
        return f'{label} sent to Windows’s active media player. Playback and song title are not verified.'
    if kind == 'navigate':
        if not webbrowser.open(website(action['url']),new=2):raise OSError('Windows could not open the browser.')
        return 'Windows accepted the website request. Page loading, clicks and signed-in account access are not verified.'
    if kind == 'settings':
        page=SETTINGS_PAGES.get(action.get('page'))
        if not page:raise ValueError('Unsupported Windows settings page.')
        os.startfile(page)
        return 'Windows settings page opened. No settings were changed automatically.'
    if kind == 'search':
        if not webbrowser.open('https://www.google.com/search?q='+quote(action['query'], safe=''), new=2):
            raise OSError('Windows could not open the default browser.')
        return 'Search opened in your default browser. I have not read the results.'
    if kind == 'open':
        alias = action['alias']
        if alias == 'spotify':
            os.startfile('spotify:')
        elif alias in ('calculator', 'notepad'):
            buffer = ctypes.create_unicode_buffer(32768)
            system = ctypes.WinDLL('kernel32')
            system.GetSystemDirectoryW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
            system.GetSystemDirectoryW.restype = ctypes.c_uint32
            length = system.GetSystemDirectoryW(buffer, len(buffer))
            if not 0 < length < len(buffer):
                raise OSError('Windows system directory is unavailable.')
            subprocess.Popen([str(Path(buffer.value)/{'calculator':'calc.exe','notepad':'notepad.exe'}[alias])], shell=False)
        elif target:
            # Recheck the approved exact path; never accept model-supplied executable arguments.
            path = Path(target['path'])
            if str(path.resolve(strict=True)) != str(path):
                raise OSError('The approved path has changed. Remove and approve it again.')
            if target['kind'] == 'app':
                subprocess.Popen([str(path)], shell=False)
            else:
                os.startfile(str(path))
        else:
            raise OSError('This target is no longer approved.')
        return f'Windows accepted the request to open {alias}. Application readiness is not verified.'
    raise OSError('Unsupported computer action.')
