from pyd2bot.logic.roleplay.behaviors.RequestMapData import RequestMapData
from pydofus2.com.ankamagames.dofus.network.types.game.context.GameContextActorInformations import (
    GameContextActorInformations,
)
from pydofus2.com.ankamagames.dofus.network.types.game.context.fight.FightCommonInformations import (
    FightCommonInformations,
)
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.MapMove import MapMove
from pydofus2.com.ankamagames.berilia.managers.EventsHandler import Event, Listener
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEvent, KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayEntitiesFrame import RoleplayEntitiesFrame
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.fight.GameRolePlayAttackMonsterRequestMessage import (
    GameRolePlayAttackMonsterRequestMessage,
)
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from pydofus2.com.ankamagames.jerakine.types.positions.MovementPath import MovementPath

""" 
A map is a grid, it contains special cells (MAP_ACTION cells), that allows to go to adjacent maps.
An Entity in the game can be in only one map and one cell at a time.
Monster Entities spawn and move around randomly in these maps, any player may attack them.
Once a player attacks a monster no other player can attack it.
This script automates the processed of attacking a monster.
As input of this script, we have the entityId of the monster, from its id at any point we can retrieve its data, that contains its current cell. 
If no data about monster is found, it means the monster vanished because another player attacked it.
Corner cases:
- Monster vanishes while moving towards it -> Stop movement and start and return monster vanished error
- Monster moves while moving towards it -> Stop movement and restart script
- Monster vanishes after sending attack request -> return monster vanished error
- Monster moves after sending attack request -> wait to see if server will still accept request, if timeout restart script
- Monster vanishes or moves and player lands on MAP_ACTION cell -> return player changed map error
"""


class AttackMonsters(AbstractBehavior):
    ENTITY_VANISHED = "Entity vanished"
    ENTITY_MOVED = "Entity moved"
    MAP_CHANGED = "Map changed unexpectedly"
    TIMEOUT = "attack entity timeout"
    FIGHT_REQ_TIMEOUT = 3

    def __init__(self) -> None:
        super().__init__()
        self.entityMovedListener: Listener = None
        self.fightShwordListener: Listener = None
        self.attackMonsterListener: Listener = None
        self.mapChangeListener: Listener = None
        self.nbrFails = 0

    @property
    def entitiesFrame(self) -> "RoleplayEntitiesFrame":
        return Kernel().worker.getFrameByName("RoleplayEntitiesFrame")

    @property
    def entityInfo(self) -> "GameContextActorInformations":
        return self.entitiesFrame.getEntityInfos(self.entityId)
    
    def getEntityCellId(self) -> int:
        if not self.entityInfo:
            self.tearDown(self.ENTITY_VANISHED, "Entity not found on map")
        return self.entityInfo.disposition.cellId

    def start(self, entityId, callback):
        if self.running.is_set():
            return callback(False, f"Already attacking monsters {entityId}!")
        self.running.set()
        self.entityId = entityId
        self.callback = callback
        cellId = self.getEntityCellId()
        self.entityMovedListener = KernelEventsManager().onEntityMoved(self.entityId, self.onEntityMoved)
        self.fightShwordListener = KernelEventsManager().onceFightSword(
            self.entityId, cellId, self.onFightWithEntityTaken
        )
        self.mapChangeListener = KernelEventsManager().on(KernelEvent.CURRENT_MAP, self.onCurrentMap)
        self._start()

    def _start(self):
        if not self.entitiesFrame:
            return KernelEventsManager().onceFramePushed("RoleplayEntitiesFrame", self._start)
        cellId = self.getEntityCellId()
        Logger().info(f"[AttackMonsters] Moving to monster {self.entityId} cell {cellId}")
        MapMove().start(MapPoint.fromCellId(cellId), self.onEntityReached)

    def onFightWithEntityTaken(self):
        if MapMove().isRunning():
            error = "Entity vanished while moving towards it!"
            MapMove().stop()
        elif self.attackMonsterListener:
            error = "Entity vanished while attacking it"
        return self.tearDown(self.ENTITY_VANISHED, error)

    def onEntityReached(self, status, error):
        if error:
            return self.finish(status, error)
        Logger().info(f"[AttackMonsters] Reached monster group cell")
        self.attackMonsterListener = KernelEventsManager().onceFightStarted(
            lambda event: self.tearDown(True, None), self.FIGHT_REQ_TIMEOUT, self.onRequestTimeout
        )
        self.requestAttackMonsters()

    def onEntityMoved(self, event: Event, movePath: MovementPath):
        Logger().warning(f"[AttackMonsters] Entity moved to cell {movePath.end.cellId}")
        if MapMove().isRunning():
            MapMove().stop()
        elif self.attackMonsterListener:
            Logger().warning("Entity moved but we already asked server for attack")
            return
        self.restart()

    def onRequestTimeout(self, listener: Listener):
        self.nbrFails += 1
        if self.nbrFails > 3:
            self.tearDown(False, self.TIMEOUT)
        else:
            self.restart()

    def removeListeners(self):
        if self.attackMonsterListener:
            self.attackMonsterListener.delete()
        self.mapChangeListener.delete()        
        self.entityMovedListener.delete()
        self.fightShwordListener.delete()
        
    def restart(self):
        self.removeListeners()
        RequestMapData().start(lambda code, err: self._start())

    def tearDown(self, status, error) -> None:
        self.removeListeners()
        self.finish(status, error)

    def requestAttackMonsters(self) -> None:
        grpamrmsg = GameRolePlayAttackMonsterRequestMessage()
        grpamrmsg.init(self.entityId)
        ConnectionsHandler().send(grpamrmsg)

    def onCurrentMap(self):
        self.tearDown(self.MAP_CHANGED, "Map changed after landing on entity cell")
