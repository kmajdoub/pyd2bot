from pyd2bot.logic.common.rpcMessages.RPCMessage import RPCMessage

from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import Transition


class FollowTransitionMessage(RPCMessage):
    def __init__(self, dest, transition: Transition, dstMapId: int) -> None:
        super().__init__(dest)
        self.transition = transition
        self.dstMapId = dstMapId
        self.oneway = True
        
