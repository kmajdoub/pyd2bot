import threading
from pyd2bot.apis.PlayerAPI import PlayerAPI
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager, KernelEvent
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import AStar
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import Edge
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pyd2bot.apis.MoveAPI import FollowTransitionError, MoveAPI
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.WorldPathFinder import (
    WorldPathFinder,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapChangeFailedMessage import (
    MapChangeFailedMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapComplementaryInformationsDataMessage import (
    MapComplementaryInformationsDataMessage,
)
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass
from pyd2bot.logic.roleplay.messages.AutoTripEndedMessage import AutoTripEndedMessage


class BotAutoTripFrame(Frame):
    def __init__(self, dstMapId: int, rpZone: int = 1):
        self.dstMapId = dstMapId
        self.dstRpZone = rpZone
        self.path = None
        self.changeMapFails = dict()
        self._computed = threading.Event()
        self._worker = Kernel().worker
        self._pulled = False
        super().__init__()

    @property
    def priority(self) -> int:
        return Priority.VERY_LOW

    def reset(self):
        self.dstMapId = None
        if self.path is not None:
            self.path.clear()
        self.changeMapFails.clear()
        self._computed.clear()

    def pushed(self) -> bool:
        Logger().debug("Auto trip frame pushed")
        self._worker = Kernel().worker
        self._computed = False
        self.changeMapFails.clear()
        self.path = None
        KernelEventsManager().onceFramePushed("BotAutoTripFrame", self.walkToNextStep)
        return True

    def pulled(self) -> bool:
        self.reset()
        Logger().debug("Auto trip frame pulled")
        self._pulled = True
        return True

    def process(self, msg: Message) -> bool:
        if self._pulled:
            return
        if isinstance(msg, MapComplementaryInformationsDataMessage):
            if self._computed:
                self.walkToNextStep()
            return True

        if isinstance(msg, MapChangeFailedMessage):
            raise Exception(f"Autotrip received map change failed for reason: {msg.reason}")

    @property
    def currentEdgeIndex(self):
        v = WorldPathFinder().currPlayerVertex
        i = 0
        while i < len(self.path):
            if self.path[i].src == v:
                break
            i += 1
        return i

    def walkToNextStep(self):
        if not PlayedCharacterManager().currentMap:
            KernelEventsManager().once(KernelEvent.MAPPROCESSED, self.walkToNextStep)
            return
        PlayerAPI().inAutoTrip.set()
        if self._computed.is_set():
            currMapId = WorldPathFinder().currPlayerVertex.mapId
            dstMapId = self.path[-1].dst.mapId
            Logger().debug(f"Player current mapId {currMapId} and dst mapId {dstMapId}")
            if currMapId == dstMapId:
                Logger().debug(f"Trip reached destination Map : {dstMapId}")
                Kernel().worker.removeFrame(self)
                Kernel().worker.process(AutoTripEndedMessage(self.dstMapId))
                PlayerAPI().inAutoTrip.clear()
                return True
            Logger().debug(f"Current step index: {self.currentEdgeIndex + 1}/{len(self.path)}")
            e = self.path[self.currentEdgeIndex]
            Logger().debug(f"Moving using next edge :")
            Logger().debug(f"\t|- src {e.src.mapId} -> dst {e.dst.mapId}")
            for tr in e.transitions:
                Logger().debug(f"\t\t|- direction : {tr.direction}, skill : {tr.skillId}, cell : {tr.cell}")
            try:
                MoveAPI.followEdge(e)
            except FollowTransitionError as e:
                Logger().debug(f"Follow transition error: {e}, will recompute path ignoring this edge.")
                self._computed.clear()
                AStar().addForbidenEdge(e)
                WorldPathFinder().findPath(self.dstMapId, self.onComputeOver, self.dstRpZone)
        else:
            WorldPathFinder().findPath(self.dstMapId, self.onComputeOver, self.dstRpZone)

    def onComputeOver(self, *args):
        path: list[Edge] = None
        for arg in args:
            if isinstance(arg, list):
                path = arg
                break
        if path is None:
            Kernel().worker.removeFrame(self)
            Kernel().worker.process(AutoTripEndedMessage(None))
            return True
        if len(path) == 0:
            Kernel().worker.removeFrame(self)
            Kernel().worker.process(AutoTripEndedMessage(self.dstMapId))
            return True
        Logger().debug(f"\nPath found: ")
        for e in path:
            print(f"\t|- src {e.src.mapId} -> dst {e.dst.mapId}")
            for tr in e.transitions:
                print(f"\t\t|- {tr}")
        self.path = path
        self._computed.set()
        self.walkToNextStep()
