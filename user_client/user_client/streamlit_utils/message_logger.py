from enum import IntEnum
import time

import streamlit as st


class MessageType(IntEnum):
    ERROR = 0
    SUCCESS = 1
    WARNING = 2
    INFO = 3
    DATA = 4


COLORED_MESSAGE_TYPE = {
    MessageType.ERROR: ':red[ERROR]',
    MessageType.SUCCESS: ':green[SUCCESS]',
    MessageType.WARNING: ':orange[WARNING]',
    MessageType.INFO: ':blue[INFO]',
    MessageType.DATA: ':violet[DATA]',
}


class Logger:
    """Streamlit widget for displaying log messages from different sources."""
    def __init__(self):
        self.__lines = []
        self.__sources = []
        self.__source_max_len = 0
        self.__colored_sources = {}

    def __call__(self):
        if self.__lines:
            st.title('Messages')
            clear_button = st.button(
                label='Clear',
                use_container_width=True
            )
            if clear_button:
                self.clear()
        if self.__lines:
            st.markdown('  \n'.join(self.__lines[::-1]))

    def clear(self):
        self.__lines = []

    def format_line(self, t: str, source: str,
                    msg_type: MessageType, msg: str) -> str:
        msg_type = COLORED_MESSAGE_TYPE[msg_type]
        source = self.__colored_sources[source]
        return f'[{t}] [{source}] [{msg_type}] {msg}'

    def log(self, source: str, msg_type: MessageType, msg: str):
        if source not in self.__sources:
            self.__sources.append(source)
            self.__source_max_len = max(self.__source_max_len, len(source))
            colors = ['blue', 'orange', 'violet', 'red', 'green']
            colors = [colors[i % len(colors)] for i in range(len(self.__sources))]
            self.__colored_sources = {
                source: f':{color}[{source: <{self.__source_max_len}}]'
                for source, color in zip(self.__sources, colors)
            }
        line = self.format_line(time.strftime('%H:%M:%S'), source, msg_type, msg)
        self.__lines.append(line)

    def error(self, source: str, msg: str):
        self.log(source, MessageType.ERROR, msg)

    def success(self, source: str, msg: str):
        self.log(source, MessageType.SUCCESS, msg)

    def warning(self, source: str, msg: str):
        self.log(source, MessageType.WARNING, msg)

    def info(self, source: str, msg: str):
        self.log(source, MessageType.INFO, msg)
