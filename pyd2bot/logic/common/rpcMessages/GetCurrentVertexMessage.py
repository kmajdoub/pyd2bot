from pyd2bot.logic.common.rpcMessages.RPCMessage import RPCMessage


class GetCurrentVertexMessage(RPCMessage):
    
    def __init__(self, dest):
        super().__init__(dest)
        self.oneway = False