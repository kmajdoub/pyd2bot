import threading
from time import perf_counter
import uuid

class RPCMessage:
    
    def __init__(self, dst: str, data=None) -> None:
        self.oneway = None
        self.uid = uuid.uuid1()
        self.creationTime = perf_counter()
        self.reqUid = None
        self.sender = threading.current_thread().name
        self.dest = dst
        self.data = data