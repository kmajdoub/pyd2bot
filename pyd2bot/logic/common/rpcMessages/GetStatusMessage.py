from pyd2bot.logic.common.rpcMessages.RPCMessage import RPCMessage


class GetStatusMessage(RPCMessage):
    
    def __init__(self, dst: str):
        super().__init__(dst)
        self.oneway = False
        