import threading
from pyd2bot.apis.PlayerAPI import PlayerAPI
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import MapDisplayManager
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager, KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.astar.AStar import AStar
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import Edge
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapInformationsRequestMessage import MapInformationsRequestMessage
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
        self._worker = Kernel().worker
        self._computed.clear()
        self.changeMapFails.clear()
        self.path = None
        KernelEventsManager().onceFramePushed("BotAutoTripFrame", self.walkToNextStep)
        Logger().info(f"[AutoTrip] Autotrip Frame pushed.")
        return True

    def pulled(self) -> bool:
        self.reset()
        KernelEventsManager().onceFramePulled("BotAutoTripFrame", self.onPulled)
        return True

    def onPulled(self):
        Logger().info(f"[AutoTrip] Autotrip Frame pulled.")
        PlayerAPI().inAutoTrip.clear()
        KernelEventsManager().send(KernelEvent.AUTO_TRIP_ENDED)
        
    def process(self, msg: Message) -> bool:
        
        if self._pulled:
            return
        
        if isinstance(msg, MapComplementaryInformationsDataMessage):
            if self._computed.is_set():
                self.walkToNextStep()
            return True

        if isinstance(msg, MapChangeFailedMessage):
            Logger.warning(f"[AutoTrip] Autotrip received map change failed for reason: {msg.reason}")
            if msg.reasonId == MapChangeFailedMessage.UNREACHABLE_TRANSIT_CELL:
                self._computed.clear()
                nextEdge = self.path[self.currentEdgeIndex]
                AStar().addForbidenEdge(nextEdge)
                WorldPathFinder().findPath(self.dstMapId, self.onComputeOver, self.dstRpZone)
            else:
                raise Exception(msg.reason)

    @property
    def currentEdgeIndex(self):
        v = WorldPathFinder().currPlayerVertex
        for i, step in enumerate(self.path):
            if step.src == v:
                return i
        raise Exception(f"[AutoTrip] Player '{v}' vertex is not in path")

    def walkToNextStep(self, *args, **kwargs):
        if PlayerAPI().isProcessingMapData():
            Logger().debug("[AutoTrip] Waiting for map to be processed")
            KernelEventsManager().once(KernelEvent.MAPPROCESSED, self.walkToNextStep)
            return
        PlayerAPI().inAutoTrip.set()
        if self._computed.is_set():
            currMapId = WorldPathFinder().currPlayerVertex.mapId
            dstMapId = self.path[-1].dst.mapId
            Logger().debug(f"[AutoTrip] Player current mapId {currMapId} and dst mapId {dstMapId}")
            if currMapId == dstMapId:
                Logger().info(f"[AutoTrip] Trip reached destination Map : {dstMapId}")
                Kernel().worker.removeFrame(self)
                self._pulled = True
                return True
            Logger().debug(f"[AutoTrip] Current step index: {self.currentEdgeIndex + 1}/{len(self.path)}")
            nextEdge = self.path[self.currentEdgeIndex]
            Logger().debug(f"[AutoTrip] Moving using next edge :")
            Logger().debug(f"\t|- src {nextEdge.src.mapId} -> dst {nextEdge.dst.mapId}")
            for tr in nextEdge.transitions:
                Logger().debug(f"\t\t|- direction : {tr.direction}, skill : {tr.skillId}, cell : {tr.cell}")
            try:
                MoveAPI.followEdge(nextEdge)
            except FollowTransitionError as ex:
                self._computed.clear()
                AStar().addForbidenEdge(nextEdge)
                WorldPathFinder().findPath(self.dstMapId, self.onComputeOver, self.dstRpZone)
        else:
            WorldPathFinder().findPath(self.dstMapId, self.onComputeOver, self.dstRpZone)

    def onComputeOver(self, *args):
        path: list[Edge] = None
        for arg in args:
            if isinstance(arg, list):
                path = arg
                break
        if path is None or len(path) == 0:
            Kernel().worker.removeFrame(self)
            self._pulled = True
            Logger().info(f"[AutoTrip] Start map and destination map are the same.")
            return True
        Logger().debug(f"\n[AutoTrip] Path found: ")
        for e in path:
            Logger().debug(f"\t|- src {e.src.mapId} -> dst {e.dst.mapId}")
            for tr in e.transitions:
                Logger().debug(f"\t\t|- {tr}")
        self.path = path
        self._computed.set()
        self.walkToNextStep()
