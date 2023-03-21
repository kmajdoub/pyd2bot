from typing import TYPE_CHECKING

from pyd2bot.apis.PlayerAPI import PlayerAPI
from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.AttackMonsters import AttackMonsters
from pyd2bot.logic.roleplay.behaviors.AutoRevive import AutoRevive
from pyd2bot.logic.roleplay.behaviors.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.behaviors.ChangeMap import ChangeMap
from pyd2bot.logic.roleplay.behaviors.UseSkill import UseSkill
from pyd2bot.logic.roleplay.behaviors.WaitForMembersIdle import \
    WaitForMembersIdle
from pyd2bot.logic.roleplay.behaviors.WaitForMembersToShow import \
    WaitForMembersToShow
from pyd2bot.misc.BotEventsmanager import BotEventsManager
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import (
    KernelEvent, KernelEventsManager)
from pydofus2.com.ankamagames.dofus.datacenter.monsters.Monster import Monster
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
    pass

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
    NO_RESOUCE = 701

    def __init__(self):
        super().__init__()
        self.state = FarmerStates.IDLE
        self.entityMovedListener = None
        
    @property
    def farmPath(self):
        return BotConfig().path

    def stop(self):
        self.finish(True, None)

    def moveToNextStep(self, callback):
        if not self.running.is_set():
            return
        self._currTransition, edge = next(self.farmPath)
        def onMapChanged(success, error):
            if error:
                Logger().error("[FarmPath] Error while moving to next step: %s" % error)
                return KernelEventsManager().send(KernelEvent.RESTART, "[FarmPath] Error while moving to next step: %s" % error)
            callback()
        ChangeMap().start(transition=self._currTransition, dstMapId=edge.dst.mapId, callback=onMapChanged)
        if Kernel().partyFrame:
            Kernel().partyFrame.askMembersToFollowTransit(self._currTransition, edge.dst.mapId)

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
                mainMonster = Monster.getMonsterById(infos.staticInfos.mainCreatureLightInfos.genericId)
                teamLvl = sum(PlayedCharacterManager.getInstance(c.login).limitedLevel for c in BotConfig().fightPartyMembers)
                if totalGrpLvl < BotConfig().monsterLvlCoefDiff * teamLvl:
                    availableMonsterFights.append(
                        {"id": infos.contextualId, "distance": len(movePath), "totalLvl": totalGrpLvl, "mainMonsterName": mainMonster.name, "cell": infos.disposition.cellId}
                    )
        if len(availableMonsterFights) > 0:
            headers = ["mainMonsterName", "id", "cell", "totalLvl", "distance"]
            format_row = f"{{:<15}} {{:<15}} {{:<15}} {{:<15}} {{:<15}}"
            row_delimiter = "-" * 65
            Logger().info(format_row.format(*headers))
            Logger().info(row_delimiter)
            for e in availableMonsterFights:
                Logger().info(format_row.format(*[e[h] for h in headers]))
        return availableMonsterFights

    def attackMonsterGroup(self, callback):
        availableMonsterFights = self.findMonstersToAttack()
        if availableMonsterFights:
            availableMonsterFights.sort(key=lambda x: x["distance"])
            def onResp(code, error):
                if code == AttackMonsters.ENTITY_VANISHED:
                    if len(availableMonsterFights) == 0:
                        return callback(self.NO_RESOUCE, "No resource to farm in the current map")
                    AttackMonsters().start(availableMonsterFights.pop()['id'], onResp)
                else:
                    callback(code, error)
            AttackMonsters().start(availableMonsterFights.pop()['id'], onResp)
        else:
            callback(self.NO_RESOUCE, "Map with no reachable monster group")

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
            return
        self.state = FarmerStates.IDLE
        Logger().info("[FarmPath] doFarm called")
        if AutoRevive().isRunning():
            Logger().warning("Cant farm if player is dead")
            return self.stop()
        if PlayerAPI().isProcessingMapData():
            KernelEventsManager().onceMapProcessed(self._start, originator=self)
            Logger().info("[FarmPath] Waiting for map to be processed...")
            self.state = FarmerStates.WAITING_MAP
            return
        if Kernel().partyFrame:
            if not Kernel().partyFrame.allMembersJoinedParty:
                return self.onPartyNotComplete()
            else:
                self.state = FarmerStates.WAITING_PARTY_MEMBERS_IDLE
                Logger().info("[BotEventsManager] Waiting for party members to be idle.")
                def onMembersIdleResult(code, error):
                    if code == WaitForMembersIdle.MEMBER_LEFT_PARTY:
                        return self.onPartyNotComplete()
                    if error:
                        return KernelEventsManager().send(KernelEvent.RESTART, f"[FarmPath] Wait members idle failed for reason : {error}")
                WaitForMembersIdle().start(Kernel().partyFrame.followers, callback=onMembersIdleResult, parent=self)
        self.doFarm()

    def onPartyNotComplete(self):
        self.state = FarmerStates.WAITING_PARTY_MEMBERS_JOIN
        Logger().info("[BotEventsManager] Waiting for party members to join party.")
        BotEventsManager().onceAllMembersJoinedParty(self._start, originator=self)
        Kernel().partyFrame.inviteAllFollowers()

    def onFarmPathMapReached(self, status, error):
        if error:
            return KernelEventsManager().send(KernelEvent.RESTART, f"[FarmPath] Go to farmPath first map failed for reason : {error}")
        self._start()
        
    def onBotOutOfFarmPath(self):
        AutoTrip().start(self.farmPath.startVertex.mapId, self.farmPath.startVertex.zoneId, self.onFarmPathMapReached)
        if Kernel().partyFrame:
            Kernel().partyFrame.askMembersToMoveToVertex(self.farmPath.startVertex)

    def onPartyMembersShowed(self, code, errorInfo):
        if errorInfo:
            if code == WaitForMembersToShow.MEMBER_LEFT_PARTY:
                Logger().warning(f"[FarmPath] Member {errorInfo} left party while waiting for them to show up!")
            else:
                return KernelEventsManager().send(KernelEvent.RESTART, f"[FarmPath] Error while waiting for members to show up: {errorInfo}")
        self._start()

    def doFarm(self, event=None):
        if PlayedCharacterManager().currentMap is None:
            Logger().info("[FarmPath] Waiting for map to be processed...")
            return KernelEventsManager().onceMapProcessed(self._start, originator=self)
        if PlayedCharacterManager().currVertex not in self.farmPath:
            return self.onBotOutOfFarmPath()
        if Kernel().partyFrame:
            if not Kernel().partyFrame.allMembersOnSameMap:
                self.state = FarmerStates.WAITING_PARTY_MEMBERS_SHOW
                Kernel().partyFrame.askMembersToMoveToVertex(self.farmPath.currentVertex)
                return WaitForMembersToShow().start(self.onPartyMembersShowed)
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
            
    def onAttackMonstersResult(self, code, error=None):
        if error is not None and code not in [AttackMonsters.MAP_CHANGED, self.NO_RESOUCE]:
            Logger().error(f"[FarmPath] Error while attacking monsters: {error}")
            return KernelEventsManager().send(KernelEvent.RESTART, f"[FarmPath] Error while attacking monsters: {error}")
        self.moveToNextStep(self._start)

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
