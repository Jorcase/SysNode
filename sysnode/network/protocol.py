from enum import Enum

class ProtocolVersion(Enum):
    V1 = 1

class ActionType(str, Enum):
    SHARE_TEXT = "SHARE_TEXT"
    REMOTE_CMD = "REMOTE_CMD"
    FILE_TRANSFER_META = "FILE_TRANSFER_META"
    FILE_TRANSFER_CHUNK = "FILE_TRANSFER_CHUNK"
    EDIT_MSG = "EDIT_MSG"
    REMOTE_BASH_CMD = "REMOTE_BASH_CMD"
    PING_NODE = "PING_NODE"
    
class PeerRole(str, Enum):
    SENDER = "SENDER"
    RECEIVER = "RECEIVER"
