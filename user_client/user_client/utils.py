import os
import zipfile
import shutil
from typing import List, Union
import re


def atoi(text: str) -> Union[int, str]:
    return int(text) if text.isdigit() else text


def natural_keys(text: str) -> List[Union[int, str]]:
    """
    Key function for sorting strings with numbers.
    Source: https://stackoverflow.com/a/5967539
    """
    return [atoi(c) for c in re.split(r'(\d+)', text)]


def zipdir(path: str, ziph: zipfile.ZipFile):
    """
    Zip a directory.
    Source: https://stackoverflow.com/a/1855118
    """
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(
                os.path.join(root, file),
                os.path.relpath(
                    os.path.join(root, file),
                    os.path.join(path, '..')
                )
            )


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
