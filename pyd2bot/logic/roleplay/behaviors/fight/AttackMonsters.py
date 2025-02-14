from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.movement.MapMove import MapMove

from pydofus2.com.ankamagames.berilia.managers.EventsHandler import (Event,
                                                                     Listener)
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InactivityManager import InactivityManager
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.fight.GameRolePlayAttackMonsterRequestMessage import \
    GameRolePlayAttackMonsterRequestMessage
from pydofus2.com.ankamagames.dofus.network.types.game.context.GameContextActorInformations import \
    GameContextActorInformations
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from pydofus2.com.ankamagames.jerakine.types.positions.MovementPath import \
    MovementPath

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
    ENTITY_VANISHED = 801
    ENTITY_MOVED = 802
    MAP_CHANGED = 803
    FIGHT_REQ_TIMED_OUT = 804
    FIGHT_REQ_TIMEOUT = 7

    def __init__(self) -> None:
        super().__init__()
        self.attackMonsterListener: Listener = None
        self.nbrFails = 0
        self._stop_message = None
        self._wanted_player_stop = False

    @property
    def entityInfo(self) -> "GameContextActorInformations":
        return Kernel().roleplayEntitiesFrame.getEntityInfos(self.entityId)
    
    def getEntityCellId(self) -> int:
        if not self.entityInfo:
            return None
        return self.entityInfo.disposition.cellId

    def run(self, entityId):
        self.entityId = entityId
        cellId = self.getEntityCellId()
        if not cellId:
            return self.finish(self.ENTITY_VANISHED, "Entity no more on the map")
        self.onEntityMoved(self.entityId, callback=self.onTargetMonsterMoved)
        self.onceFightSword(self.entityId, cellId, callback=self.onFightWithEntityTaken)
        self.on(KernelEvent.CurrentMap, self.onCurrentMap)
        self._start()

    def _start(self):
        if not Kernel().roleplayEntitiesFrame:
            return self.once_frame_pushed("RoleplayEntitiesFrame", self._start)
        cellId = self.getEntityCellId()
        if not cellId:
            return self.finish(self.ENTITY_VANISHED, "Fight with entity taken by another player!")
        Logger().info(f"Moving to monster {self.entityId} cell {cellId}")
        self.map_move_to_cell(MapPoint.fromCellId(cellId), callback=self.onTargetMonsterReached)

    def onFightWithEntityTaken(self):
        if MapMove.getInstance():
            error = "Entity vanished while moving towards it!"
            Logger().warning(error)
            self._wanted_player_stop = True
            self._stop_code = self.ENTITY_VANISHED
            self._stop_message = error
            MapMove.getInstance().stop()
        elif self.attackMonsterListener:
            return self.finish(self.ENTITY_VANISHED, "Entity vanished while attacking it!")

    def onTargetMonsterReached(self, status, error, landingcell=None):
        Logger().info(f"Reached monster group cell")
        if self._wanted_player_stop:
            self._wanted_player_stop = False
            if self._stop_code == self.ENTITY_MOVED:
                return self.restart()
            elif self._stop_code == self.ENTITY_VANISHED:
                return self.finish(self.ENTITY_VANISHED, self._stop_message)
        if error:
            return self.finish(status, error)
        self.attackMonsterListener = self.once(
            event_id=KernelEvent.FightStarted,
            callback=lambda event: self.finish(0), 
            timeout=self.FIGHT_REQ_TIMEOUT, 
            ontimeout=self.finish, 
            retry_nbr=3,
            retry_action=self.restart
        )
        self.requestAttackMonsters()

    def onTargetMonsterMoved(self, event: Event, movePath: MovementPath):
        Logger().warning(f"Entity moved to cell {movePath.end.cellId}")
        if MapMove.getInstance():
            self._wanted_player_stop = True
            self._stop_code = self.ENTITY_MOVED
            MapMove.getInstance().stop()
        elif self.attackMonsterListener:
            Logger().warning("Entity moved but we already asked server for attack")
            return
            
    def restart(self):
        KernelEventsManager().clear_all_by_origin(self)
        self.requestMapData(callback=lambda code, err: self._start())

    def requestAttackMonsters(self) -> None:
        message = GameRolePlayAttackMonsterRequestMessage()
        message.init(self.entityId)
        ConnectionsHandler().send(message)
        InactivityManager().activity()

    def onCurrentMap(self, event, mapId):
        Logger().warning("Monster moved and was on a Map action cell, we changed to a new map")
        self.finish(self.MAP_CHANGED, "Map changed after landing on entity cell")
