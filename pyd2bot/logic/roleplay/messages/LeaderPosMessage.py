from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
from pydofus2.com.ankamagames.jerakine.messages.Message import Message


class LeaderPosMessage(Message):
    def __init__(self, Vertex: Vertex):
        self.vertex = Vertex
