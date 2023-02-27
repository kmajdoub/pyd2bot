from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.MapMove import MapMove
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import (
    KernelEvent, KernelEventsManager)
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayEntitiesFrame import \
    RoleplayEntitiesFrame
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightJoinRequestMessage import \
    GameFightJoinRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.fight.GameRolePlayAttackMonsterRequestMessage import \
    GameRolePlayAttackMonsterRequestMessage
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import \
    BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from pydofus2.com.ankamagames.jerakine.types.positions.MovementPath import \
    MovementPath


class AttackMonsters(AbstractBehavior):
    
    def __init__(self) -> None:
        super().__init__()
        self.requestTimer = None
        self.entityInfo = None
        self.entityMapPoint = None
        self.entityMovedListener = None
        self.entityVanishedListener = None
        self.fightJoinAfterEntityVanishedTimer = None
        self.nbrFails = 0

    @property
    def entitiesFrame(self) -> "RoleplayEntitiesFrame":
        return Kernel().worker.getFrameByName("RoleplayEntitiesFrame")
    
    def start(self, entityId, callback):
        if self.running.is_set():
            return callback(False, f"Already attacking monsters {entityId}!")
        self.running.set()
        self.entityId = entityId
        self.callback = callback
        self.entityInfo = self.entitiesFrame.getEntityInfos(self.entityId)
        if not self.entityInfo:
            return callback(False, f"Can't find the entity {self.entityId}, maybe someone else is fighting it?")
        self.entityMapPoint = MapPoint.fromCellId(self.entityInfo.disposition.cellId)
        self.entityMovedListener = KernelEventsManager().onceEntityMoved(self.entityId, self.onEntityMoved)
        self.entityVanishedListener = KernelEventsManager().onceEntityVanished(self.entityId, self.onEntityVanished)
        Logger().info(f"[AttackMonsters] Attacking monster group {self.entityId} on cell {self.entityMapPoint.cellId}")
        MapMove().start(self.entityMapPoint, self.onEntityReached)

    def onEntityReached(self, status, error):
        if error:
            return self.finish(status, error)
        Logger().info(f"[AttackMonsters] Reached monster group cell")
        self.requestAttackMonsters()
        
    def onEntityMoved(self, movePath: MovementPath):
        Logger().warning(f"[AttackMonsters] Monster group {self.entityId} moved, changing move cell")
        if MapMove().isRunning():
            MapMove().stop()
        self.entityMovedListener = KernelEventsManager().onceEntityMoved(self.entityId, self.onEntityMoved)
        MapMove().start(movePath.end, self.onEntityReached)
        
    def onEntityVanished(self):
        if self.requestTimer:
            self.requestTimer.cancel()
        if MapMove().isRunning():
            MapMove().stop()
        if self.entityMovedListener:
            KernelEventsManager().remove_listener(KernelEvent.ENTITY_MOVED, self.entityMovedListener)
        if self.entityVanishedListener:
            KernelEventsManager().remove_listener(KernelEvent.ENTITY_VANISHED, self.entityVanishedListener)
        self.fightJoinAfterEntityVanishedTimer = BenchmarkTimer(1, self.onEntityVanishedButNoFightJoin)
        self.fightJoinAfterEntityVanishedTimer.start()

    def onEntityVanishedButNoFightJoin(self):
        self.finish(False, "Entity vanished")

    def onRequestTimeout(self):
        self.nbrFails += 1
        if self.nbrFails > 3:
            self.finish(False, "Attack monsters request timeout")
        else:
            KernelEventsManager().remove_listener(KernelEvent.FIGHT_STARTED, self.onfight)
            Logger().warning(f"[AttackMonsters] Attack monsters request timeout, retrying")
            self.requestAttackMonsters()

    def onfight(self, event_id) -> None:
        if self.fightJoinAfterEntityVanishedTimer:
            self.fightJoinAfterEntityVanishedTimer.cancel()     
        if self.entityMovedListener:
            KernelEventsManager().remove_listener(KernelEvent.ENTITY_MOVED, self.entityMovedListener)
        if self.entityVanishedListener:
            KernelEventsManager().remove_listener(KernelEvent.ENTITY_VANISHED, self.entityVanishedListener)
        if self.requestTimer:
            self.requestTimer.cancel()
        self.finish(True, None)

    def requestAttackMonsters(self) -> None:
        self.requestTimer = BenchmarkTimer(10, self.onRequestTimeout)
        KernelEventsManager().once(KernelEvent.FIGHT_STARTED, self.onfight)
        grpamrmsg = GameRolePlayAttackMonsterRequestMessage()
        grpamrmsg.init(self.entityId)
        self.requestTimer.start()
        ConnectionsHandler().send(grpamrmsg)
