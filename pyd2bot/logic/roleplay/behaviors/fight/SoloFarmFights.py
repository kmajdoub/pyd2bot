import heapq
import numpy as np
import time
from prettytable import PrettyTable

from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.behaviors.AbstractFarmBehavior import \
    AbstractFarmBehavior
from pyd2bot.logic.roleplay.behaviors.fight.AttackMonsters import \
    AttackMonsters
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import MapDisplayManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.datacenter.monsters.Monster import Monster
from pydofus2.com.ankamagames.dofus.datacenter.spells.Spell import Spell
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.GameRolePlayGroupMonsterInformations import \
    GameRolePlayGroupMonsterInformations
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.pathfinding.Pathfinding import Pathfinding
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint


class SoloFarmFights(AbstractFarmBehavior):

    def __init__(self, timeout=None):
        super().__init__(timeout)
    
    def init(self):
        self.path = BotConfig().curr_path
        self.path.init()
        self.last_monster_attack_time = None
        self.fights_per_minute = 2
        Logger().debug(f"Solo farm fights started")
        return True
    
    def get_spells(self):
        header = ["ID", "Spell Name", "Spell Lvl", "Cout en PA", "Range"]
        data_spells = PrettyTable(header)
        for spell in PlayedCharacterManager().playerSpellList:
            data_spells.add_row(
                [
                    spell.id,
                    Spell.getSpellById(spell.id).name,
                    spell._spellLevel.minPlayerLevel,
                    spell._spellLevel.apCost,
                    f"{spell._spellLevel.minimalRange} - {spell._spellLevel.maximalRange}",
                ]
            )
        Logger().info(data_spells)

    def makeAction(self):
        self.get_spells()
        all_monster_groups = self.getAvailableResources()
        all_collectables_ressources = self.getCollectableResources()
        
        if not all_monster_groups and len(all_collectables_ressources) == 0:
            Logger().debug("No monster group or resources found!")
            self.moveToNextStep()
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
        if len(all_collectables_ressources):
            Logger().info("Collectable enter")
            all_collectables_ressources = self.getCollectableResources()
            if len(all_collectables_ressources) == 0:
                Logger().info("Collectable no more ressource")
                return self.main()
            movPath = Pathfinding().findPath(start=PlayedCharacterManager().playerMapPoint, end=MapDisplayManager().getIdentifiedElementPosition(all_collectables_ressources[0].id))
            Logger().info("Collectable movPath")
            self.useSkill(
                elementId=all_collectables_ressources[0].id,
                skilluid=all_collectables_ressources[0].interactiveSkill.skillInstanceUid,
                cell = movPath.end,
                callback=self.onFinishCollect
                )
            Logger().info("Collectable exit")
        elif all_monster_groups:
            Logger().info("Monster enter")
            all_monster_groups = self.getAvailableResources()
            Logger().info(f"all monster calculation done {all_monster_groups}")
            monster_group = all_monster_groups[0]
            self.attackMonsters(monster_group["id"], self.onFightStarted)
            Logger().info("Attack monster")
            self.last_monster_attack_time = current_time

    def onFinishCollect(self, code, error, iePostion=None):
        if not self.running.is_set():
            return
        if error:
            Logger().warning(f"Error during collection of resources. {error}")

        BenchmarkTimer(0.2, self.main).start()

    def _calculate_wait_time(self, current_time):
        if not self.last_monster_attack_time:
            # No previous attack, use full wait time based on rate
            return np.random.poisson(self.fights_per_minute / 60)

        time_since_last_attack = current_time - self.last_monster_attack_time
        expected_attacks_since_last = self.fights_per_minute * time_since_last_attack / 60

        # Adjust wait time based on expected attacks since last attack
        wait_time = max(0, np.random.poisson(expected_attacks_since_last))

        return wait_time
    
    def getCollectableResources(self):
        if not Kernel().interactivesFrame.collectables:
            return []
        availables_resources = []
        def log_table(e):
            headers = ["id", "skillName", "Enabled", "Name", "Level"]
            summaryTable = PrettyTable(headers)
            if isinstance(e, list):
                for i in e:
                    summaryTable.add_row(
                        [
                            i.id,
                            i.skillName,
                            i.enabled,
                            i.skill.gatheredRessource.name,
                            i.skill.levelMin,
                        ]
                    )
            Logger().debug(f"Available resources :\n{summaryTable}")

        for resources in Kernel().interactivesFrame.collectables.values():
            if resources.enabled and resources.skill.levelMin <= PlayedCharacterManager().joblevel(resources.skill.parentJob.id):
                availables_resources.append(resources)

        if len(availables_resources):
            log_table(availables_resources)

        return availables_resources

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
