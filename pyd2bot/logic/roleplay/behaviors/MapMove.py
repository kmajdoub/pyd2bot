from time import perf_counter

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.atouin.utils.DataMapProvider import \
    DataMapProvider
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import (
    KernelEvent, KernelEventsManager)
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.common.misc.DofusEntities import \
    DofusEntities
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayMovementFrame import \
    RoleplayMovementFrame
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.types.MovementFailReason import \
    MovementFailReason
from pydofus2.com.ankamagames.dofus.network.enums.PlayerLifeStatusEnum import \
    PlayerLifeStatusEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameMapMovementCancelMessage import \
    GameMapMovementCancelMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameMapMovementConfirmMessage import \
    GameMapMovementConfirmMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameMapMovementRequestMessage import \
    GameMapMovementRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapInformationsRequestMessage import \
    MapInformationsRequestMessage
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import \
    BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.pathfinding.Pathfinding import \
    Pathfinding
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from pydofus2.com.ankamagames.jerakine.types.positions.MovementPath import \
    MovementPath


class MapMove(AbstractBehavior):
    CONSECUTIVE_MOVEMENT_DELAY: int = 0.25
    LAST_MOVE_REQUEST = None

    def __init__(self) -> None:
        self.requestTimer = None
        self.movementAnimTimer = None
        self.entityMovedListener = None
        self.movementStoppedListener = None
        self.nbrFails = 0
        super().__init__()
    
    def start(self, destCell, callback=None, exactDistination=True) -> None:
        if self.running.is_set():
            if callback:
                callback(False, "Already running")
            return
        self.running.set()
        self.callback = callback
        self.exactDestination = exactDistination
        if isinstance(destCell, int):
            self.dstCell = MapPoint.fromCellId(destCell)
        elif isinstance(destCell, MapPoint):
            self.dstCell = destCell
        else:
            self.finish(False, "Invalid destination cell")
        self.move()

    def stop(self) -> None:
        if self.requestTimer:
            self.requestTimer.cancel()
        elif self.movementAnimTimer:
            self.movementAnimTimer.cancel()
        if self.movementStoppedListener:
            KernelEventsManager().remove_listener(KernelEvent.MOVEMENT_STOPPED, self.movementStoppedListener)
        if self.entityMovedListener:
            KernelEventsManager().remove_listener(KernelEvent.ENTITY_MOVED, self.entityMovedListener)
        canceledMoveMessage = GameMapMovementCancelMessage();
        canceledMoveMessage.init(PlayedCharacterManager().currentCellId);
        ConnectionsHandler().send(canceledMoveMessage)  
        self.running.clear()
        MapMove.clear()

    def move(self) -> bool:
        rpmframe: "RoleplayMovementFrame" = Kernel().worker.getFrameByName("RoleplayMovementFrame")
        if not rpmframe:
            return KernelEventsManager().onceFramePushed("RoleplayMovementFrame", self.move)
        playerEntity = DofusEntities().getEntity(PlayedCharacterManager().id)
        self.errMsg = f"Move to cell {self.dstCell} failed for reason %s"
        currentCellId = playerEntity.position.cellId
        if playerEntity is None:
            return self.fail(MovementFailReason.PLAYER_NOT_FOUND)
        if MapDisplayManager().dataMap is None:
            return self.fail(MovementFailReason.MAP_NOT_LOADED)
        if currentCellId == self.dstCell.cellId:
            Logger().info("[RPPlayMove] Destination cell is the same as the current player cell")
            return self.finish(True, None)
        if PlayerLifeStatusEnum(PlayedCharacterManager().state) == PlayerLifeStatusEnum.STATUS_TOMBSTONE:
            return self.fail(MovementFailReason.PLAYER_IS_DEAD)
        self.movePath = Pathfinding().findPath(playerEntity.position, self.dstCell)
        if self.exactDestination and self.movePath.end.cellId != self.dstCell.cellId:
            return self.fail(MovementFailReason.CANT_REACH_DEST_CELL)
        self.movementStoppedListener = KernelEventsManager().once(KernelEvent.MOVEMENT_STOPPED, self.onMovementRejected)
        self.requestMovement()
        return True
    
    def onMovementRejected(self, event, newpos) -> None:
        self.nbrFails += 1
        if self.nbrFails > 3:
            return self.fail(MovementFailReason.MOVE_REQUEST_REJECTED)
        Logger().debug(f"[MapMove] server reject called by event {event.name}.")
        if self.requestTimer:
            self.requestTimer.cancel()
            self.requestTimer = None
        KernelEventsManager().onceMapProcessed(self.move, [], MapDisplayManager().currentMapPoint.mapId)
        self.requestMapData()

    def requestMapData(self):
        mirmsg = MapInformationsRequestMessage()
        mirmsg.init(MapDisplayManager().currentMapPoint.mapId)
        ConnectionsHandler().send(mirmsg)
        
    def fail(self, reason: MovementFailReason) -> None:
        self.finish(reason, self.errMsg % reason.name)

    def onMovementAnimEnd(self) -> None:
        Logger().info(f"[MapMove] Movement animation ended")
        if self.movementAnimTimer:
            self.movementAnimTimer.cancel()
            self.movementAnimTimer = None
        self.isMoving = False
        gmmcmsg = GameMapMovementConfirmMessage()
        ConnectionsHandler().send(gmmcmsg)
        self.finish(True, None)
        
    def simulateMoveAnimation(self, clientMovePath: MovementPath):
        weightCoef = PlayedCharacterManager().inventoryWeight / PlayedCharacterManager().inventoryWeightMax
        canrun = weightCoef < 1.0
        pathDuration = max(1, clientMovePath.getCrossingDuration(canrun))
        if self.movementAnimTimer:
            self.movementAnimTimer.cancel()
        self.movementAnimTimer = BenchmarkTimer(pathDuration + 0.1, self.onMovementAnimEnd)
        self.isMoving = True
        self.movementAnimTimer.start()
        Logger().info("[MapMove] Movement anim started")
        
    def requestMovement(self) -> None:
        self.entityMovedListener = KernelEventsManager().onceEntityMoved(PlayedCharacterManager().id, self.onMovementRequestAccepted)
        gmmrmsg = GameMapMovementRequestMessage()
        gmmrmsg.init(self.movePath.keyMoves(), MapDisplayManager().currentMapPoint.mapId)
        Logger().info(f"[MapMove] Move request sent.")
        if self.LAST_MOVE_REQUEST is not None:
            nexPossibleMovementTime = self.LAST_MOVE_REQUEST + self.CONSECUTIVE_MOVEMENT_DELAY
            if perf_counter() < nexPossibleMovementTime:
                Kernel().worker.terminated.wait(nexPossibleMovementTime - perf_counter())
        def onTimeout():
            self.fail(MovementFailReason.MOVE_REQUEST_TIMEOUT)
        self.requestTimer = BenchmarkTimer(20, onTimeout)
        self.requestTimer.start()
        ConnectionsHandler().send(gmmrmsg)
        self.LAST_MOVE_REQUEST = perf_counter()
        
    def onMovementRequestAccepted(self, clientMovePath):
        if self.movementStoppedListener:
            KernelEventsManager().remove_listener(KernelEvent.MOVEMENT_STOPPED, self.movementStoppedListener)
            self.movementStoppedListener = None
        self.entityMovedListener = None
        Logger().info(f"[MapMove] Move request accepted.")
        if self.requestTimer:
            self.requestTimer.cancel()
            self.requestTimer = None
        self.simulateMoveAnimation(clientMovePath)