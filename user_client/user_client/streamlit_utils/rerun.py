"""
Utility functions allowing to force rerun Streamlit outside of the main thread.
"""


import datetime as dt
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from streamlit_utils import dummy


class Watchdog(FileSystemEventHandler):
    def __init__(self, hook: Callable):
        self.hook = hook

    def on_modified(self, event):
        self.hook()


def force_rerun():
    """
    Force Streamlit to rerun.
    Works only outside of the main thread.
    Uses a dummy source file to trigger the rerun.
    Possibly not the most elegant solution, but it works.
    """
    dummy_path = dummy.__file__
    with open(dummy_path, "w") as fp:
        fp.write(f'timestamp = "{dt.datetime.now()}"')


def create_directory_monitor(dir_path: str) -> Observer:
    """
    Create a directory monitor that will trigger a rerun of Streamlit app
    when directory content changes.
    """
    observer = Observer()
    observer.schedule(
        Watchdog(force_rerun),
        path=dir_path,
        recursive=False)
    return observer
