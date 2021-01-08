from enum import auto, Enum
from typing import Tuple


class MessageStatus(Enum):
    SUCCESS = auto()
    INFO = auto()
    ERROR = auto()


def encode_message(status: MessageStatus, message: str) -> str:
    _, decoded_msg = decode_message(message)
    return f'[{status.name}] {decoded_msg}'


def decode_message(message: str) -> Tuple[MessageStatus, str]:
    for s in MessageStatus:
        repr: str = f'[{s.name}] '
        if repr in message:
            return s, message.replace(repr, '')
    return MessageStatus.INFO, message
