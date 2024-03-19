import heapq

from prettytable import PrettyTable

from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.behaviors.AbstractFarmBehavior import \
    AbstractFarmBehavior
from pyd2bot.logic.roleplay.behaviors.fight.AttackMonsters import \
    AttackMonsters
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.datacenter.monsters.Monster import Monster
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.GameRolePlayGroupMonsterInformations import \
    GameRolePlayGroupMonsterInformations
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint


class SoloFarmFights(AbstractFarmBehavior):

    def __init__(self, timeout=None):
        super().__init__(timeout)
    
    def init(self):
        self.path = BotConfig().path
        self.path.init()
        Logger().debug(f"Solo farm fights started")
        return True

    def makeAction(self):
        all_monster_groups = self.getAvailableResources()
        if all_monster_groups:
            monster_group = all_monster_groups[0]
            self.attackMonsters(monster_group["id"], self.onFightStarted)
        else:
            Logger().debug("No monster group found!")
            self.moveToNextStep()
        
    def getAvailableResources(self):
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
        availableMonsterFights.sort(key=lambda r : r['distance'])
        self.logResourcesTable(availableMonsterFights)
        return availableMonsterFights
        
    def onFightStarted(self, code, error):        
        if not self.running.is_set():
            return
        if error:
            Logger().warning(error)
            if code in [AttackMonsters.ENTITY_VANISHED, AttackMonsters.FIGHT_REQ_TIMEDOUT, AttackMonsters.MAP_CHANGED]:
                self.main()
            else:
                return self.send(KernelEvent.ClientRestart, f"Error while attacking monsters: {error}")

    def logResourcesTable(self, resources):
        if resources:
            headers = ["mainMonsterName", "id", "cell", "distance"]
            summaryTable = PrettyTable(headers)
            for e in resources:
                summaryTable.add_row(
                    [
                        e["mainMonsterName"],
                        e["id"],
                        e["cell"],
                        e["distance"]
                    ]
                )
            Logger().debug(f"Available resources :\n{summaryTable}")
