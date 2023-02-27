from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.MapMove import MapMove
from pyd2bot.logic.roleplay.behaviors.UseSkill import UseSkill
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import (
    KernelEvent, KernelEventsManager)
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayInteractivesFrame import (
    InteractiveElementData, RoleplayInteractivesFrame)
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Edge import \
    Edge
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Transition import \
    Transition
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.TransitionTypeEnum import \
    TransitionTypeEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.ChangeMapMessage import \
    ChangeMapMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapInformationsRequestMessage import \
    MapInformationsRequestMessage
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import \
    BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint


class ChangeMap(AbstractBehavior):
    
    def __init__(self) -> None:
        super().__init__()
        self.requestTimer = None
        self.transition = None
        self.nbrFails = 0
        self.movementRejectListener = None

    def start(self, transition: Transition=None, edge: Edge=None, dstMapId=None, callback=None):
        if self.running.is_set():
            return self.finish(False, f"Already changing map to {self.dstMapId}!")
        self.running.set()
        self.callback = callback
        if transition:
            self.dstMapId = dstMapId
            self.transition = transition
            self.followTransition()
        elif edge:
            self.dstMapId = edge.dst.mapId
            self.edge = edge
            self.followEdge()
        else:
            self.finish(False, "No transition or edge provided")

    def onmapchange(self) -> None:
        if self.requestTimer:
            self.requestTimer.cancel()
            self.requestTimer = None
        if self.movementRejectListener:
            KernelEventsManager().remove_listener(KernelEvent.MOVEMENT_STOPPED, self.movementRejectListener)
            self.movementRejectListener = None
        self.finish(True, None)

    def requestMapChange(self):
        KernelEventsManager().onceMapProcessed(self.onmapchange, [], self.dstMapId)
        self.requestTimer = BenchmarkTimer(3, self.onRequestFailed, ["timeout"])
        cmmsg = ChangeMapMessage()
        cmmsg.init(int(self.transition.transitionMapId), False)
        self.movementRejectListener = KernelEventsManager().once(KernelEvent.MOVEMENT_STOPPED, self.onRequestRejectedByServer)
        self.requestTimer.start()
        ConnectionsHandler().send(cmmsg)

    def onRequestRejectedByServer(self, event, newPos: MapPoint):
        Logger().debug(f"[ChangeMap] server reject called by event {event.name}.")
        if self.requestTimer:
            self.requestTimer.cancel()
            self.requestTimer = None
        KernelEventsManager().onceMapProcessed(self.onRequestFailed, ["rejected by server"], MapDisplayManager().currentMapPoint.mapId)
        self.requestMapData()

    def requestMapData(self):
        mirmsg = MapInformationsRequestMessage()
        mirmsg.init(MapDisplayManager().currentMapPoint.mapId)
        ConnectionsHandler().send(mirmsg)

    def onRequestFailed(self, reason):
        Logger().warn(f"[ChangeMap] request failed for reason: {reason}")
        self.nbrFails += 1
        if self.nbrFails > 3:
            return self.finish(False, f"Change map request failed for reason: {reason}")
        self.requestMapChange()

    @property
    def rpiframe(cls) -> "RoleplayInteractivesFrame":
        return Kernel().worker.getFrameByName("RoleplayInteractivesFrame")
    
    def followEdge(self):
        for tr in self.edge.transitions:
            if tr.isValid:
                self.transition = tr
                return self.followTransition()
        self.finish(False, "No valid transition found!")

    def getTransitionIe(self, transition: Transition) -> "InteractiveElementData":
        if not self.rpiframe:
            return KernelEventsManager().onceFramePushed("RoleplayInteractivesFrame", self.getTransitionIe, [transition])
        return self.rpiframe.getInteractiveElement(transition.id, transition.skillId)

    def followTransition(self):
        if not self.transition.isValid:
            return self.finish(False, "Trying to follow a non valid transition")
        if self.dstMapId == PlayedCharacterManager().currentMap.mapId:
            return self.finish(True, None)
        if TransitionTypeEnum(self.transition.type) == TransitionTypeEnum.INTERACTIVE:
            Logger().info(f"[ChangeMap] interactive MAP change to '{self.dstMapId}'.")
            ie = self.getTransitionIe(self.transition)
            if not ie:
                return self.finish(False, f"InteractiveElement {self.transition.id} not found")
            self.interactiveMapChange(ie, self.transition.cell)
        else:
            Logger().info(f"[ChangeMap] Scroll MAP change to '{self.dstMapId}'.")
            self.scrollMapChange(self.transition.cell)
    
    def interactiveMapChange(self, ie, cellId):
        KernelEventsManager().onceMapProcessed(self.onmapchange, [], self.dstMapId)
        UseSkill().start(ie, self.finish, cellId, exactDistination=False)
    
    def onMoveToTransitionCell(self, errType, error=None):
        if error:
            return self.finish(errType, error)
        self.requestMapChange()
        
    def scrollMapChange(self, cellId: int) -> None:
        MapMove().start(cellId, self.onMoveToTransitionCell)
