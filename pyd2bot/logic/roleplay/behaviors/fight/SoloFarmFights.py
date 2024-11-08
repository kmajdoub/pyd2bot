import heapq
import threading
import numpy as np
import time
from prettytable import PrettyTable

from pyd2bot.data.models import Character
from pyd2bot.logic.roleplay.behaviors.farm.AbstractFarmBehavior import \
    AbstractFarmBehavior
from pyd2bot.logic.roleplay.behaviors.fight.AttackMonsters import \
    AttackMonsters
from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
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

    def __init__(self, path: AbstractFarmPath, fightsPerMinute: int, fightPartyMembers: list[Character], monsterLvlCoefDiff=None, timeout=None):
        super().__init__(timeout)
        self.path = path
        self.fightsPerMinute = fightsPerMinute
        self.fightPartyMembers = fightPartyMembers
        self.monsterLvlCoefDiff = monsterLvlCoefDiff if monsterLvlCoefDiff else float("inf")

    def init(self):
        self.path.init()
        self.last_monster_attack_time = None
        Logger().debug(f"Solo farm fights started, {self.fightsPerMinute} fights per minute.")
        return True

    def makeAction(self):
        all_monster_groups = self.getAvailableResources()
        if not all_monster_groups:
            Logger().debug("No monster group found!")
            self._move_to_next_step()
            return
        
        # Calculate wait time using Poisson distribution
        current_time = time.time()  # Assuming access to time module
        wait_time = self._calculate_wait_time(current_time)

        # Ensure wait time doesn't exceed a reasonable maximum
        max_wait_time = 60  # 1 minute (adjust as needed)
        wait_time = min(wait_time, max_wait_time)

        Logger().debug(f"Waiting for {wait_time:.2f} seconds to attack monsters")

        if Kernel().worker.terminated.wait(wait_time):
            return
    
        all_monster_groups = self.getAvailableResources()
        if not all_monster_groups:
            Logger().debug("No monster group found!")
            self._move_to_next_step()
            return
        monster_group = all_monster_groups[0]
        self.attackMonsters(monster_group["id"], self.onFightStarted)
        self.last_monster_attack_time = current_time

    def _calculate_wait_time(self, current_time):
        if not self.last_monster_attack_time:
            # No previous attack, use full wait time based on rate
            return np.random.poisson(self.fightsPerMinute / 60)

        time_since_last_attack = current_time - self.last_monster_attack_time
        expected_attacks_since_last = self.fightsPerMinute * time_since_last_attack / 60

        # Adjust wait time based on expected attacks since last attack
        wait_time = max(0, np.random.poisson(expected_attacks_since_last))

        return wait_time

    def getAvailableResources(self):
        if not Kernel().roleplayEntitiesFrame._monstersIds:
            return []
        availableMonsterFights = []
        visited = set()
        queue = list[int, MapPoint]()
        currCellId = PlayedCharacterManager().currentCellId
        teamLvl = PlayedCharacterManager().limitedLevel
        monsterByCellId = dict[int, GameRolePlayGroupMonsterInformations]()
        for entityId in Kernel().roleplayEntitiesFrame._monstersIds:
            infos: GameRolePlayGroupMonsterInformations = Kernel().roleplayEntitiesFrame.getEntityInfos(entityId)
            if infos:
                totalGrpLvl = infos.staticInfos.mainCreatureLightInfos.level + sum(
                    ul.level for ul in infos.staticInfos.underlings
                )
                if totalGrpLvl < self.monsterLvlCoefDiff * teamLvl:
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
            for x, y in MapPoint.fromCellId(currCellId).iterChildren():
                adjacentPos = MapPoint.fromCoords(x, y)
                if adjacentPos.cellId in visited:
                    continue
                heapq.heappush(queue, (distance + 1, adjacentPos.cellId))
        availableMonsterFights.sort(key=lambda r : r['distance'])
        self.logResourcesTable(availableMonsterFights)
        return availableMonsterFights
        
    def onFightStarted(self, code, error):        
        if not self.running.is_set():
            Logger().warning("onFightStarted callback called but fight farmer is not running!")
            return
        if error:
            Logger().warning(error)
            if code in [AttackMonsters.ENTITY_VANISHED, AttackMonsters.FIGHT_REQ_TIMED_OUT, AttackMonsters.MAP_CHANGED]:
                self.main()
            else:
                self.send(KernelEvent.ClientRestart, f"Error while attacking monsters: {error}")
                return

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
