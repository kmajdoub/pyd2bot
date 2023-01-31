from time import perf_counter
import uuid
from pyd2bot.logic.common.rpcMessages.RPCMessage import RPCMessage

class RPCResponseMessage(RPCMessage):
    
    def __init__(self, callerMsg: RPCMessage, data=None) -> None:
        super().__init__(callerMsg.sender, data)
        self.oneway = True
        self.reqUid = callerMsg.uid