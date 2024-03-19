import heapq
from typing import TYPE_CHECKING

from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.fight.AttackMonsters import \
    AttackMonsters
from pyd2bot.logic.roleplay.behaviors.movement.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.behaviors.movement.AutoTripUseZaap import \
    AutoTripUseZaap
from pyd2bot.logic.roleplay.behaviors.movement.ChangeMap import ChangeMap
from pyd2bot.logic.roleplay.behaviors.movement.GetOutOfAnkarnam import \
    GetOutOfAnkarnam
from pyd2bot.logic.roleplay.behaviors.party.WaitForMembersIdle import \
    WaitForMembersIdle
from pyd2bot.logic.roleplay.behaviors.party.WaitForMembersToShow import \
    WaitForMembersToShow
from pyd2bot.logic.roleplay.messages.FollowTransitionMessage import \
    FollowTransitionMessage
from pyd2bot.logic.roleplay.messages.MoveToVertexMessage import \
    MoveToVertexMessage
from pyd2bot.thriftServer.pyd2botService.ttypes import Vertex
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.datacenter.monsters.Monster import Monster
from pydofus2.com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.TransitionTypeEnum import \
    TransitionTypeEnum
from pydofus2.com.ankamagames.dofus.network.enums.PlayerLifeStatusEnum import \
    PlayerLifeStatusEnum
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.GameRolePlayGroupMonsterInformations import \
    GameRolePlayGroupMonsterInformations
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint

if TYPE_CHECKING:
    pass

from enum import Enum


class FarmerStates(Enum):
    IDLE = 2
    WAITING_FOLLWERS_IDLE = 9
    WAITING_PARTY_MEMBERS_SHOW = 10

class FarmFights(AbstractBehavior):

    def __init__(self, timeout=None):
        super().__init__(timeout)
        self.state = FarmerStates.IDLE

    def onMapChanged(self, code, error):
        if error:
            Logger().error(f"Error while moving to next step: {error}")
            return KernelEventsManager().send(KernelEvent.ClientRestart, "Error while moving to next step: %s" % error)
        self.run()

    def moveToNextStep(self):
        if not self.running.is_set():
            return
        self._currTransition, edge = next(BotConfig().path)
        ChangeMap().start(transition=self._currTransition, dstMapId=edge.dst.mapId, callback=self.onMapChanged, parent=self)
        if BotConfig().followers:
            self.askMembersFollow(self._currTransition, edge.dst.mapId)

    def getAvailableMonstersTable(self, availableMonsterFights) -> str:
        headers = ["mainMonsterName", "id", "cell", "distance"]
        data = [[e[h] for h in headers] for e in availableMonsterFights]
        col_widths = [max(len(str(row[i])) for row in data + [headers]) for i in range(len(headers))]
        format_string = "  ".join(["{{:<{}}}".format(width) for width in col_widths])
        tablestr = "\n" + format_string.format(*headers) + "\n"
        tablestr += '-' * (sum(col_widths) + (len(col_widths) - 1) * 2) + "\n"  # Add extra spaces for column separators
        for row in data:
            tablestr += format_string.format(*row) + "\n"
        return tablestr

    def findMonstersToAttack(self):
        if not Kernel().roleplayEntitiesFrame._monstersIds:
            return []
        availableMonsterFights = []
        visited = set()
        queue = list[int, MapPoint]()
        currCellId = PlayedCharacterManager().currentCellId
        teamLvl = sum(PlayedCharacterManager.getInstance(c.login).limitedLevel for c in BotConfig().fightPartyMembers)
        monsterByCellId = dict[int, GameRolePlayGroupMonsterInformations]()
        for entityId in Kernel().roleplayEntitiesFrame._monstersIds:
            infos: GameRolePlayGroupMonsterInformations = Kernel().roleplayEntitiesFrame.getEntityInfos(entityId)
            if infos:
                totalGrpLvl = infos.staticInfos.mainCreatureLightInfos.level + sum(
                    ul.level for ul in infos.staticInfos.underlings
                )
                if totalGrpLvl < BotConfig().monsterLvlCoefDiff * teamLvl:
                    monsterByCellId[infos.disposition.cellId] = infos
        if not monsterByCellId:
            return []
        heapq.heappush(queue, (0, currCellId))
        while queue:
            distance, currCellId = heapq.heappop(queue)
            if currCellId in visited:
                continue
            visited.add(currCellId)
            if currCellId in monsterByCellId:
                infos = monsterByCellId[currCellId]
                mainMonster = Monster.getMonsterById(infos.staticInfos.mainCreatureLightInfos.genericId)
                availableMonsterFights.append({
                    "mainMonsterName": mainMonster.name,
                    "id": infos.contextualId,
                    "cell": currCellId,
                    "distance": distance
                })
            for x, y in MapPoint.fromCellId(currCellId).iterChilds():
                adjacentPos = MapPoint.fromCoords(x, y)
                if adjacentPos.cellId in visited:
                    continue
                heapq.heappush(queue, (distance + 1, adjacentPos.cellId))
        Logger().info(self.getAvailableMonstersTable(availableMonsterFights))
        return availableMonsterFights

    def attackMonsterGroup(self):
        Logger().info("Searching monsters to attack ...")
        availableMonsterFights = self.findMonstersToAttack()
        availableMonsterFights = iter(availableMonsterFights)
        try:
            def onResp(code, error):
                if error:
                    Logger().warning(error)
                    if code == AttackMonsters.MAP_CHANGED:
                        return self.attackMonsterGroup()
                    elif code == AttackMonsters.ENTITY_VANISHED:
                        try:
                            monster = next(availableMonsterFights)
                        except StopIteration:
                            return self.moveToNextStep()
                        AttackMonsters().start(monster["id"], callback=onResp, parent=self)
                    else:
                        return KernelEventsManager().send(KernelEvent.ClientRestart, f"Error while attacking monsters: {error}")
            monster = next(availableMonsterFights)
            Logger().info(monster)
            AttackMonsters().start(monster["id"], callback=onResp, parent=self)
        except StopIteration:
            Logger().debug("No monster to farm")
            self.moveToNextStep()
        
    def run(self, event_id=None, error=None):
        if not self.running.is_set():
            return
        self.path = BotConfig().path
        Logger().info("run called")
        if BotConfig().followers:
            self.state = FarmerStates.WAITING_FOLLWERS_IDLE
            Logger().info("Waiting for party members to be idle.")
            return WaitForMembersIdle().start(BotConfig().followers, callback=self.onMembersIdle, parent=self)
        self.doFarm()

    def onMembersIdle(self, code, error):
        if error:
            return KernelEventsManager().send(KernelEvent.ClientRestart, f"Wait members idle failed for reason : {error}")
        self.doFarm()

    def onFarmPathMapReached(self, code, error):
        if error:
            return KernelEventsManager().send(KernelEvent.ClientRestart, f"Go to path first map failed for reason : {error}")
        self.run()
        
    def onBotOutOfFarmPath(self):
        srcSubArea = SubArea.getSubAreaByMapId(PlayedCharacterManager().currentMap.mapId)
        srcAreaId = srcSubArea._area.id
        dstSubArea = SubArea.getSubAreaByMapId(self.path.startVertex.mapId)
        dstAreaId = dstSubArea._area.id
        if dstAreaId != GetOutOfAnkarnam.ankarnamAreaId and srcAreaId == GetOutOfAnkarnam.ankarnamAreaId:
            Logger().info(f"Auto trip to an Area ({dstSubArea._area.name}) out of {srcSubArea._area.name}.")
            def onPosReached(code, error):
                if error:
                    return KernelEventsManager().send(KernelEvent.ClientShutdown, message=error)
                AutoTripUseZaap().start(
                    self.path.startVertex.mapId, self.path.startVertex.zoneId, callback=self.onFarmPathMapReached, parent=self
                )
            def onGotOutOfAnkarnam(code, error):
                if error:
                    return KernelEventsManager().send(KernelEvent.ClientShutdown, message=error)
                AutoTripUseZaap().start(self.path.startVertex.mapId, self.path.startVertex.zoneId, parent=self, callback=onPosReached)
            return GetOutOfAnkarnam().start(callback=onGotOutOfAnkarnam, parent=self)
        AutoTripUseZaap().start(
            self.path.startVertex.mapId, self.path.startVertex.zoneId, callback=self.onFarmPathMapReached, parent=self
        )

    def onMembersShowed(self, code, errorInfo):
        if errorInfo:
            if code == WaitForMembersToShow.MEMBER_DISCONNECTED:
                Logger().warning(f"Member {errorInfo} disconnected while waiting for them to show up")
            else:
                return KernelEventsManager().send(KernelEvent.ClientRestart, f"Error while waiting for members to show up: {errorInfo}")
        self.run()

    def doFarm(self, event=None):
        Logger().info("do farm called")
        if PlayerLifeStatusEnum(PlayedCharacterManager().state) in [PlayerLifeStatusEnum.STATUS_TOMBSTONE, PlayerLifeStatusEnum.STATUS_PHANTOM]:
            Logger().debug(f"Can't farm fights when player is dead")
            return self.stop()
        if PlayedCharacterManager().currentMap is None:
            Logger().info("Waiting for map to be processed...")
            return KernelEventsManager().onceMapProcessed(self.run, originator=self)
        if PlayedCharacterManager().currVertex not in BotConfig().path:
            Logger().warning("Player out of farm path")
            return self.onBotOutOfFarmPath()
        if not self.allMembersOnSameMap():
            Logger().warning("Followers are not all on same map")
            self.state = FarmerStates.WAITING_PARTY_MEMBERS_SHOW
            self.askFollowersMoveToVertex(BotConfig().path.currentVertex)
            return WaitForMembersToShow().start(BotConfig().followers, callback=self.onMembersShowed, parent=self)
        self.attackMonsterGroup()
 
    def askMembersFollow(self, transition: TransitionTypeEnum, dstMapId):
        for follower in BotConfig().followers:
            Kernel.getInstance(follower.login).worker.process(FollowTransitionMessage(transition, dstMapId))

    def askFollowersMoveToVertex(self, vertex: Vertex):
        for follower in BotConfig().followers:
            entity = Kernel().roleplayEntitiesFrame.getEntityInfos(follower.id)
            if not entity:
                Kernel.getInstance(follower.login).worker.process(MoveToVertexMessage(vertex))                
                Logger().debug(f"Asked follower {follower.login} to go to farm start vertex")
            
    def allMembersOnSameMap(self):
        for follower in BotConfig().followers:
            if Kernel().roleplayEntitiesFrame is None:
                return False
            entity = Kernel().roleplayEntitiesFrame.getEntityInfos(follower.id)
            if not entity:
                return False
        return True
