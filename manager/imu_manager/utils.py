import os
import shutil
import threading
import traceback
import logging
from typing import List, Union, Sequence, Callable


class Singleton(type):
    """Singleton metaclass"""

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            logging.info('Creating singleton instance of {}'.format(cls.__name__))
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class TempDir:
    """
    Context manager for temporary files and directories.
    Passed files and directories will be removed after context exit.
    """

    def __init__(self, paths: Union[str, List[str]]):
        if isinstance(paths, str):
            paths = [paths]
        self.paths = paths

    def __enter__(self):
        return self.paths

    def __exit__(self, exc_type, exc_value, traceback):
        for path in self.paths:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)


class CommandThread(threading.Thread):
    """Thread for executing commands outside of main thread"""

    def __init__(self, name):
        super().__init__()
        self.name = name
        self.__stop_event = threading.Event()
        self.__busy_event = threading.Event()
        self.__update_lock = threading.Lock()
        self.__command = None
        self.__args = None

    def run(self):
        while not self.__stop_event.is_set():
            self.__busy_event.wait()
            try:
                self.__command(*self.__args)
            except Exception as e:
                logging.error(f'Error while executing command: {e}')
                logging.error(traceback.format_exc())
            finally:
                self.__command = None
                self.__args = None
                self.__busy_event.clear()

    def stop(self):
        self.stop_event.set()

    @property
    def is_busy(self) -> bool:
        return self.__busy_event.is_set()

    def run_command(self, command: Callable, args: Sequence,
                    sync: bool = False):
        with self.__update_lock:
            if self.__busy_event.is_set():
                raise RuntimeError('Manager is busy')
            if sync:
                command(*args)
            else:
                self.__command = command
                self.__args = args
                self.__busy_event.set()
