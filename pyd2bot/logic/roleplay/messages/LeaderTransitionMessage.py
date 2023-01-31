from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import Transition
from pydofus2.com.ankamagames.jerakine.messages.Message import Message


class LeaderTransitionMessage(Message):
    def __init__(self, transition: Transition):
        self.transition = transition
