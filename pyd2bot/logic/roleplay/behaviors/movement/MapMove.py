from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.common.misc.DofusEntities import \
    DofusEntities
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.types.MovementFailError import \
    MovementFailError
from pydofus2.com.ankamagames.dofus.network.enums.PlayerLifeStatusEnum import \
    PlayerLifeStatusEnum
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.pathfinding.Pathfinding import \
    PathFinding
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from pydofus2.com.ankamagames.jerakine.types.positions.MovementPath import \
    MovementPath


class MapMove(AbstractBehavior):
    CONSECUTIVE_MOVEMENT_DELAY = 0.25
    MOVE_REQ_TIMEOUT = 7
    ALREADY_ONCELL = 7001
    PLAYER_STOPPED = 7002

    def __init__(self) -> None:
        super().__init__()
        self._landingCell = None
        self.waiting_move_request_accept = False
        self.delayed_stop = False
        self.move_request_accepted = False

    def run(self, destCell, exactDestination=True, forMapChange=False, mapChangeDirection=-1, cellsblacklist=[]) -> None:
        Logger().info(f"Move from {PlayedCharacterManager().currentCellId} to {destCell} started")
        
        self.forMapChange = forMapChange
        self.mapChangeDirection = mapChangeDirection
        self.exactDestination = exactDestination
        self.cellsblacklist = cellsblacklist
        if isinstance(destCell, int):
            self.dstCell = MapPoint.fromCellId(destCell)
        elif isinstance(destCell, MapPoint):
            self.dstCell = destCell
        else:
            self.finish(False, f"Invalid destination cell param : {destCell}!")
        self.countMoveFail = 0
        self.move_request_accepted = False
        self.move()

    def tearDown(self):
        self.callback = None
        self.finish(None, None)
        
    def stop(self) -> None:
        if not PlayedCharacterManager().isFighting:
            player = PlayedCharacterManager().entity
            if player is None:
                Logger().warning("Player entity not found, can't stop movement.")
            else:
                if not player.isMoving:
                    Logger().warning("Player is not moving, can't stop movement.")
                if player.isMoving:
                    player.stop_move() # this is blocking until the player movement animation is stopped
                elif self.waiting_move_request_accept:
                    self.delayed_stop = True
                    Logger().warning("Player requested movement, but is not moving yet, will delay stop.")
                    return False
                elif self.move_request_accepted:
                    Logger().warning("Player not moving but its move request already executed nothing to stop.")
                    return False
        KernelEventsManager().clearAllByOrigin(self)
        # MapMove.clear()
        return True
        
    def move(self) -> bool:
        if PlayedCharacterManager().isFighting:
            self.tearDown()
            return

        rpmframe = Kernel().movementFrame
        
        if not rpmframe:
            return self.once_frame_pushed("RoleplayMovementFrame", self.move)
        
        playerEntity = DofusEntities().getEntity(PlayedCharacterManager().id)
        
        self.errMsg = f"Move to cell {self.dstCell} failed for reason %s"
        
        if playerEntity is None:
            return self.fail(MovementFailError.PLAYER_NOT_FOUND)
        
        currentCellId = playerEntity.position.cellId
        if MapDisplayManager().dataMap is None:
            return self.fail(MovementFailError.MAP_NOT_LOADED)
        
        if currentCellId == self.dstCell.cellId:
            Logger().info(f"Destination cell {self.dstCell.cellId} is the same as the current player cell")
            return self.finish(self.ALREADY_ONCELL, None, self.dstCell)
        
        if PlayerLifeStatusEnum(PlayedCharacterManager().state) == PlayerLifeStatusEnum.STATUS_TOMBSTONE:
            return self.fail(MovementFailError.PLAYER_IS_DEAD)
        
        self.movePath = PathFinding().findPath(playerEntity.position, self.dstCell, cellsBlacklist=self.cellsblacklist)
        if self.movePath is None:
            return self.fail(MovementFailError.NO_PATH_FOUND)
        
        if self.exactDestination and self.movePath.end.cellId != self.dstCell.cellId:
            return self.fail(MovementFailError.CANT_REACH_DEST_CELL)
        
        if len(self.movePath) == 0:
            return self.finish(True, None, self.dstCell)
        
        self.requestMovement()

    def fail(self, reason: MovementFailError) -> None:
        self.finish(reason, self.errMsg % reason.name, None)

    def requestMovement(self) -> None:
        if PlayedCharacterManager().isFighting:
            self.tearDown()
            return

        if len(self.movePath) == 0:
            return self.finish(True, None, self.dstCell)
        self.once(
            KernelEvent.MovementRequestRejected,
            callback=lambda event: self.onMoveRequestReject(MovementFailError.MOVE_REQUEST_REJECTED),
        )
        KernelEventsManager().onceEntityMoved(
            PlayedCharacterManager().id,
            callback=self.onPlayerMoving,
            timeout=15,
            ontimeout=lambda listener: self.onMoveRequestReject(MovementFailError.MOVE_REQUEST_TIMEOUT),
            originator=self, 
        )
        self.sendMoveRequest()

    def onMoveRequestReject(self, reason: MovementFailError) -> None:
        if PlayedCharacterManager().isFighting:
            self.tearDown()
            return

        self.waiting_move_request_accept = False
        self.countMoveFail += 1
        if self.countMoveFail > 3:
            return self.fail(reason)
        Logger().warning(f"Server rejected movement for reason {reason.name}")
        KernelEventsManager().clearAllByOrigin(self)
        self.requestMapData(callback=lambda code, error: self.move())

    def sendMoveRequest(self):
        if PlayedCharacterManager().isFighting:
            self.tearDown()
            return

        self.waiting_move_request_accept = True
        self.once(
            KernelEvent.PlayerMovementCompleted, callback=self.onMovementCompleted
        )
        Kernel().movementFrame.sendMovementRequest(self.movePath, self.dstCell)

    def onPlayerMoving(self, event, clientMovePath: MovementPath):
        if PlayedCharacterManager().isFighting:
            self.tearDown()
            return

        self.waiting_move_request_accept = False
        self.move_request_accepted = True
        Logger().info(f"Move request accepted : len={len(clientMovePath)}")
        self._landingCell = clientMovePath.end
        if clientMovePath.end.cellId != self.dstCell.cellId:
            Logger().warning(f"Heading to cell {clientMovePath.end.cellId} not the wanted destination {self.dstCell.cellId}!")
        if self.delayed_stop:
            self.delayed_stop = False
            Logger().warning("Scheduled player stop movement, will stop now.")
            BenchmarkTimer(0.4, self.stop).start()

    def onMovementCompleted(self, event, success):
        if PlayedCharacterManager().isFighting:
            self.tearDown()
            return

        if success:
            Logger().info("Player completed movement")
            self.finish(success, None, self._landingCell)
        else:
            self.finish(self.PLAYER_STOPPED, "Player movement was stopped", self._landingCell)
