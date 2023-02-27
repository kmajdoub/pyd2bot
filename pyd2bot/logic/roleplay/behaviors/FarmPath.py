from typing import TYPE_CHECKING

from pyd2bot.apis.PlayerAPI import PlayerAPI
from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.AttackMonsters import AttackMonsters
from pyd2bot.logic.roleplay.behaviors.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.behaviors.ChangeMap import ChangeMap
from pyd2bot.logic.roleplay.behaviors.UseSkill import UseSkill
from pyd2bot.logic.roleplay.frames.BotPartyFrame import BotPartyFrame
from pyd2bot.misc.BotEventsmanager import BotEventsManager
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import (
    KernelEvent, KernelEventsManager)
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayInteractivesFrame import \
    InteractiveElementData
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.GameRolePlayGroupMonsterInformations import \
    GameRolePlayGroupMonsterInformations
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.pathfinding.Pathfinding import \
    Pathfinding
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayEntitiesFrame import \
        RoleplayEntitiesFrame
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayInteractivesFrame import \
        RoleplayInteractivesFrame
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayMovementFrame import \
        RoleplayMovementFrame
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayWorldFrame import \
        RoleplayWorldFrame

from enum import Enum


class FarmerStates(Enum):
    FIGHTING = 5
    FOLLOWING_MONSTER_GROUP = 0
    FOLLOWING_INTERACTIVE = 1
    USING_INTRACTIVE = 1
    IDLE = 2
    WAITING_MAP = 3
    CHANGING_MAP = 4
    FOLLOWING_MAP_CHANGE_CELL = 6
    REQUESTED_FIGHT = 7
    WAITING_PARTY_MEMBERS_JOIN = 8
    WAITING_PARTY_MEMBERS_IDLE = 9
    WAITING_PARTY_MEMBERS_SHOW = 10

class FarmPath(AbstractBehavior):
    
    def __init__(self):
        super().__init__()
        self.state = FarmerStates.IDLE
        self.entityMovedListener = None

    @property
    def farmPath(self):
        return BotConfig().path

    @property
    def entitiesFrame(self) -> "RoleplayEntitiesFrame":
        return Kernel().worker.getFrameByName("RoleplayEntitiesFrame")

    @property
    def interactivesFrame(self) -> "RoleplayInteractivesFrame":
        return Kernel().worker.getFrameByName("RoleplayInteractivesFrame")

    @property
    def movementFrame(self) -> "RoleplayMovementFrame":
        return Kernel().worker.getFrameByName("RoleplayMovementFrame")

    @property
    def partyFrame(self) -> "BotPartyFrame":
        return Kernel().worker.getFrameByName("BotPartyFrame")

    @property
    def worldFrame(self) -> "RoleplayWorldFrame":
        return Kernel().worker.getFrameByName("RoleplayWorldFrame")

    def finish(self, status, error) -> bool:
        if BotEventsManager().has_listeners(BotEventsManager.MEMBERS_READY):
            BotEventsManager().remove_listener(BotEventsManager.MEMBERS_READY, self._start)
        if KernelEventsManager().has_listeners(KernelEvent.MAPPROCESSED):
            KernelEventsManager().remove_listener(KernelEvent.MAPPROCESSED, self._start)
        super().finish(status, error)
        return True

    def stop(self):
        self.finish(True, None)

    def moveToNextStep(self, callback):
        if not self.running.is_set():
            return Logger().warning("[FarmPath] Not running")
        self._currTransition, edge = next(self.farmPath)
        def onMapChanged(success, error):
            if error:
                raise Exception("[FarmPath] Error while moving to next step: %s" % error)
            callback()
        ChangeMap().start(transition=self._currTransition, dstMapId=edge.dst.mapId, callback=onMapChanged)
        if self.partyFrame:
            self.partyFrame.askMembersToFollowTransit(self._currTransition, edge.dst.mapId)

    def findMonstersToAttack(self):
        availableMonsterFights = []
        currPlayerPos = PlayedCharacterManager().entity.position
        for entityId in self.entitiesFrame._monstersIds:
            infos: GameRolePlayGroupMonsterInformations = self.entitiesFrame.getEntityInfos(entityId)
            if self.insideCurrentPlayerZoneRp(infos.disposition.cellId):
                monsterGroupPos = MapPoint.fromCellId(infos.disposition.cellId)
                movePath = Pathfinding().findPath(currPlayerPos, monsterGroupPos)
                if movePath.end.cellId != monsterGroupPos.cellId:
                    continue
                totalGrpLvl = infos.staticInfos.mainCreatureLightInfos.level + sum(
                    [ul.level for ul in infos.staticInfos.underlings]
                )
                if totalGrpLvl < BotConfig().monsterLvlCoefDiff * PlayedCharacterManager().limitedLevel:
                    availableMonsterFights.append(
                        {"info": infos, "distance": len(movePath)}
                    )
        return availableMonsterFights

    def attackMonsterGroup(self, callback):
        availableMonsterFights = self.findMonstersToAttack()
        if availableMonsterFights:
            availableMonsterFights.sort(key=lambda x: x["distance"])
            def onResp(status, error):
                if error == "Entity vanished":
                    if len(availableMonsterFights) == 0:
                        return callback(False, "No resource")
                    AttackMonsters().start(availableMonsterFights.pop()["info"].contextualId, onResp)
                else:
                    callback(status, error)
            AttackMonsters().start(availableMonsterFights.pop()["info"].contextualId, onResp)
        else:
            callback(False, "No resource")

    def insideCurrentPlayerZoneRp(self, cellId):
        tgtRpZone = MapDisplayManager().dataMap.cells[cellId].linkedZoneRP
        return tgtRpZone == PlayedCharacterManager().currentZoneRp

    def start(self, callback=None):
        if self.running.is_set():
            return Logger().error("[FarmPath] Already running")
        self.callback = callback
        self.running.set()
        self._start()
        
    def _start(self, event_id=None, error=None):
        if not self.running.is_set():
            return Logger().warning("[FarmPath] Not running")
        self.state = FarmerStates.IDLE
        Logger().info("[FarmPath] doFarm called")
        if PlayerAPI().isProcessingMapData():
            KernelEventsManager().onceMapProcessed(self._start)
            Logger().info("[FarmPath] Waiting for map to be processed...")
            self.state = FarmerStates.WAITING_MAP
            return
        if self.partyFrame:
            if not self.partyFrame.allMembersJoinedParty:
                self.state = FarmerStates.WAITING_PARTY_MEMBERS_JOIN
                Logger().info("[BotEventsManager] Waiting for party members to join party.")
                BotEventsManager().onceAllMembersJoinedParty(self._start)
                self.partyFrame.inviteAllFollowers()
            else:
                self.state = FarmerStates.WAITING_PARTY_MEMBERS_IDLE
                Logger().info("[BotEventsManager] Waiting for party members to be idle.")
                BotEventsManager().onceAllPartyMembersIdle(self.doFarm)
                self.partyFrame.checkAllMembersIdle()
            return
        self.doFarm()

    def doFarm(self, event=None):
        if PlayedCharacterManager().currentMap is None:
            Logger().info("[FarmPath] Waiting for map to be processed...")
            return KernelEventsManager().onceMapProcessed(self._start)
        if PlayedCharacterManager().currVertex not in self.farmPath:
            AutoTrip().start(self.farmPath.startVertex.mapId, self.farmPath.startVertex.zoneId, self._start)
            if self.partyFrame:
                self.partyFrame.askMembersToMoveToVertex(self.farmPath.startVertex)
            return
        if self.partyFrame:
            if not self.partyFrame.allMembersOnSameMap:
                self.state = FarmerStates.WAITING_PARTY_MEMBERS_SHOW
                self.partyFrame.askMembersToMoveToVertex(self.farmPath.currentVertex)
                return BotEventsManager().onceAllPartyMembersShowed(self._start)
        if BotConfig().isFightSession:
            self.attackMonsterGroup(self.onAttackMonstersResult)
        elif BotConfig().isFarmSession:
            self.collectResource(self.onCollectRsourceResult)
            
    def onCollectRsourceResult(self, status, error=None):
        if error is not None:
            if error != "No resource":
                Logger().error(f"[FarmPath] Error while farming: {error}")
            self.moveToNextStep(self._start)
        self._start()
            
    def onAttackMonstersResult(self, status, error=None):
        if error is not None:
            if error != "No resource" and error != "Entity vanished":
                Logger().error(f"[FarmPath] Error while attacking monsters: {error}")
            return self.moveToNextStep(self._start)

    def findResourceToCollect(self) -> InteractiveElementData:
        target = None
        ie = None
        nearestCell = None
        minDist = float("inf")
        for it in self.interactivesFrame.collectables.values():
            if it.enabled:
                if BotConfig().jobIds:
                    if it.skill.parentJobId not in BotConfig().jobIds:
                        continue
                    if PlayedCharacterManager().jobs[it.skill.parentJobId].jobLevel < it.skill.levelMin:
                        continue
                    if BotConfig().resourceIds:
                        if it.skill.gatheredRessource.id not in BotConfig().resourceIds:
                            continue
                ie = self.interactivesFrame.interactives.get(it.id)
                if not (self.interactivesFrame and self.interactivesFrame.usingInteractive):
                    if not PlayedCharacterManager().entity:
                        return Logger().error("[FarmPath] Player entity not found")
                    nearestCell, _ = self.worldFrame.getNearestCellToIe(ie.element, ie.position)
                    if self.insideCurrentPlayerZoneRp(nearestCell.cellId):
                        dist = PlayedCharacterManager().entity.position.distanceToCell(ie.position)
                        if dist < minDist:
                            target = ie
                            minDist = dist
        return target, nearestCell

    def collectResource(self, callback) -> None:
        target, nearestCell = self.findResourceToCollect()
        if target:
            UseSkill().start(target, callback, nearestCell)
        else:
            callback(False, "No resource")
