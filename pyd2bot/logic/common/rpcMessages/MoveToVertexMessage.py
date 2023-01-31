from pyd2bot.logic.common.rpcMessages.RPCMessage import RPCMessage

from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex


class MoveToVertexMessage(RPCMessage):
    def __init__(self, dest, vertex: Vertex) -> None:
        super().__init__(dest)
        self.vertex = vertex
        self.oneway = True
