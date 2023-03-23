from enum import IntEnum
import streamlit as st


class MessageType(IntEnum):
    ERROR = 0
    SUCCESS = 1
    WARNING = 2
    INFO = 3
    DATA = 4


class Logger:
    """Streamlit widget for displaying log messages from different sources."""
    def __init__(self):
        self.__lines = {}

    def __call__(self):
        if not self.__lines:
            return
        sources = list(self.__lines.keys())
        tabs = st.tabs(sources)
        for source, tab in zip(sources, tabs):
            with tab:
                formated_lines = []
                for msg_type, msg in self.__lines[source][::-1]:
                    prefix = ''
                    if msg_type == MessageType.ERROR:
                        prefix = ':red[ERROR]'
                    elif msg_type == MessageType.SUCCESS:
                        prefix = ':green[SUCCESS]'
                    elif msg_type == MessageType.WARNING:
                        prefix = ':orange[WARNING]'
                    elif msg_type == MessageType.INFO:
                        prefix = ':blue[INFO]'
                    formated_lines.append(f'{prefix}: {msg}')
                st.markdown('  \n'.join(formated_lines))

    def log(self, source: str, msg_type: MessageType, msg: str):
        if source not in self.__lines:
            self.__lines[source] = []
        self.__lines[source].append((msg_type, msg))

    def error(self, source: str, msg: str):
        self.log(source, MessageType.ERROR, msg)

    def success(self, source: str, msg: str):
        self.log(source, MessageType.SUCCESS, msg)

    def warning(self, source: str, msg: str):
        self.log(source, MessageType.WARNING, msg)

    def info(self, source: str, msg: str):
        self.log(source, MessageType.INFO, msg)
