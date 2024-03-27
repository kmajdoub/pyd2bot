import heapq
import random
import time
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
        self.last_monster_attack_time = None
        self.fights_per_minute = 2
        Logger().debug(f"Solo farm fights started")
        return True

    def makeAction(self):
        all_monster_groups = self.getAvailableResources()
        if not all_monster_groups:
            Logger().debug("No monster group found!")
            self.moveToNextStep()
            return
        
        # Calculate wait time using Poisson distribution
        current_time = time.time()  # Assuming access to time module
        wait_time = self._calculate_wait_time(current_time) + abs(random.gauss(0, 10)) # Add some noise

        # Ensure wait time doesn't exceed a reasonable maximum
        max_wait_time = 60  # 1 minute (adjust as needed)
        wait_time = min(wait_time, max_wait_time)

        Logger().debug(f"Waiting for {wait_time:.2f} seconds to attack monsters")

        if Kernel().worker.terminated.wait(wait_time):
            return
        all_monster_groups = self.getAvailableResources()
        monster_group = all_monster_groups[0]
        self.attackMonsters(monster_group["id"], self.onFightStarted)
        self.last_monster_attack_time = current_time

    def _calculate_wait_time(self, current_time):
        if not self.last_monster_attack_time:
            # No previous attack, use a default initial wait or start immediately
            return 0
        time_since_last_attack = current_time - self.last_monster_attack_time
        desired_interval = 60 / self.fights_per_minute  # Seconds between fights
        # Calculate wait time to maintain desired rate, ensuring non-negative
        wait_time = max(desired_interval - time_since_last_attack, 0)
        return wait_time

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
