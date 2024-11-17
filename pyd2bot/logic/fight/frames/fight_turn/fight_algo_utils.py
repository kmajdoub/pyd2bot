from queue import PriorityQueue

from prettytable import PrettyTable
from pyd2bot.logic.fight.frames.fight_turn.spell_utils import getSpellZone
from pydofus2.com.ankamagames.atouin.utils.DataMapProvider import DataMapProvider
from pydofus2.com.ankamagames.dofus.datacenter.monsters.Monster import Monster
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.StatsManager import StatsManager
from pydofus2.com.ankamagames.dofus.logic.game.fight.managers.CurrentPlayedFighterManager import CurrentPlayedFighterManager
from pydofus2.com.ankamagames.dofus.logic.game.fight.managers.FightersStateManager import FightersStateManager
from pydofus2.com.ankamagames.dofus.logic.game.fight.miscs.FightReachableCellsMaker import FightReachableCellsMaker
from pydofus2.com.ankamagames.dofus.logic.game.fight.miscs.TackleUtil import TackleUtil
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from typing import TYPE_CHECKING, Tuple
from pydofus2.com.ankamagames.dofus.network.types.game.context.fight.GameFightMonsterInformations import (
        GameFightMonsterInformations,
    )
from pydofus2.mapTools import MapTools

if TYPE_CHECKING:
    
    from pydofus2.com.ankamagames.dofus.internalDatacenter.spells.SpellWrapper import SpellWrapper
    from pydofus2.com.ankamagames.dofus.network.types.game.context.fight.GameFightFighterInformations import GameFightFighterInformations


class Target:
    def __init__(self, entity: "GameFightMonsterInformations", cellId: int) -> None:
        self.entity = entity
        self.pos = MapPoint.fromCellId(entity.disposition.cellId)
        self.entityId = entity.contextualId
        self.distFromPlayer = self.pos.distanceToCellId(cellId)

    def __str__(self) -> str:
        return f"({self.entity.contextualId}, { self.entity.disposition.cellId}, {self.distFromPlayer})"


def find_cells_with_los_to_targets(spellw: "SpellWrapper", targets: list["Target"], fighterCell: int) -> list[int]:
    """Find cells that have line of sight to targets for a given spell.

    Args:
        spellw: Spell wrapper containing spell info
        targets: List of potential targets
        fighterCell: Current cell ID of the fighter

    Returns:
        Tuple of (max range from fighter, dict of cell IDs to list of visible targets)
    """
    Logger().debug("=" * 50)
    Logger().debug(f"findCellsWithLosToTargets for spell {spellw.spell.name}, with fighter cell {fighterCell}")

    hasLosToTargets = dict[int, list["Target"]]()
    spellZone = getSpellZone(spellw)
    maxRangeFromFighter = 0

    Logger().debug(f"Target positions: {[f'Target(cell={t.pos.cellId}, dist={t.distFromPlayer})' for t in targets]}")

    for target in targets:
        currSpellZone = spellZone.getCells(target.pos.cellId)

        for cell in currSpellZone:
            p = MapPoint.fromCellId(cell)
            
            # Get line between target and potential casting cell
            line = MapTools.getMpLine(target.pos.cellId, p.cellId)

            los = True
            if len(line) > 1:
                for mp in line[:-1]:
                    has_los = DataMapProvider().pointLos(mp.x, mp.y, False)
                    if not has_los:
                        los = False
                        break
            else:
                pass

            if los:
                # Special case - we can cast from current position
                if fighterCell == p.cellId:
                    Logger().debug("=> Can cast from current position - returning immediately")
                    return 0, {fighterCell: [target]}

                # Record this casting position
                if p.cellId not in hasLosToTargets:
                    hasLosToTargets[p.cellId] = list[Target]()
                hasLosToTargets[p.cellId].append(target)

                # Update max range
                maxRangeFromFighter = max(maxRangeFromFighter, target.distFromPlayer)


    # Final summary
    Logger().debug("\n" + "=" * 20 + " FINAL RESULTS " + "=" * 20)
    Logger().debug(f"Max range from fighter: {maxRangeFromFighter}")
    Logger().debug(f"Number of valid casting positions found: {len(hasLosToTargets)}")
    Logger().debug("=" * 50)

    return maxRangeFromFighter, hasLosToTargets


def find_path_to_target(
    spellw: "SpellWrapper",
    targets: list[Target],
    fighter_pos: "MapPoint",
    fighter_infos: "GameFightFighterInformations",
    forbidden_cells: list[int],
    movement_points: int,
) -> Tuple[Target, list[int]]:
    if not targets:
        return None, None

    maxRangeFromFighter, hasLosToTargets = find_cells_with_los_to_targets(spellw, targets, fighter_pos.cellId)
    if not hasLosToTargets:
        return None, None
    if fighter_pos.cellId in hasLosToTargets:
        return hasLosToTargets[fighter_pos.cellId][0], []
    if movement_points <= 0:
        return None, None
    reachableCells = set(FightReachableCellsMaker(fighter_infos, fighter_pos.cellId, maxRangeFromFighter).reachableCells)
    queue = PriorityQueue[Tuple[int, int, int]]()
    queue.put((0, 0, fighter_pos.cellId))
    visited = set()
    parentOfCell = {}
    bestAlternative = None
    BestAlternativeCost = float("inf")
    while not queue.empty():
        _, usedPms, currCellId = queue.get()
        if currCellId in visited:
            continue
        visited.add(currCellId)
        currPoint = MapPoint.fromCellId(currCellId)
        for nextMapPoint in currPoint.vicinity():
            nextCellId = nextMapPoint.cellId
            if nextCellId not in forbidden_cells and nextCellId not in visited and nextCellId in reachableCells:
                parentOfCell[nextCellId] = currCellId
                if nextCellId in hasLosToTargets:
                    path = buildPath(parentOfCell, nextCellId)
                    return hasLosToTargets[nextCellId][0], path
                heuristic = (
                    usedPms
                    + 1
                    + 10
                    * sum([MapTools.getDistance(nextCellId, cellId) for cellId in hasLosToTargets])
                    / len(hasLosToTargets)
                )
                if heuristic < BestAlternativeCost:
                    bestAlternative = nextCellId
                    BestAlternativeCost = heuristic
                queue.put((heuristic, usedPms + 1, nextCellId))
    if bestAlternative is not None:
        path = buildPath(parentOfCell, bestAlternative)
        return None, path
    return None, None

def buildPath(parentOfCell: dict[int, int], endCellId):
    path = [endCellId]
    currCellId = endCellId
    while True:
        currCellId = parentOfCell.get(currCellId)
        if currCellId is None:
            break
        path.append(currCellId)
    path.reverse()
    return path

def get_targetable_entities(spellw: "SpellWrapper", fighter_infos: "GameFightFighterInformations", target_sums=False, target_boneId=None) -> list[Target]:
    result = list[Target]()
    infosTable = list[dict]()
    if not Kernel().fightEntitiesFrame or not Kernel().battleFrame:
        Logger().error("EntitiesFrame or BattleFrame is not found")
        return []
    if fighter_infos is None:
        Logger().warning(
            f"Fighter not found in entities frame!"
        )
        return []
    for entity in Kernel().fightEntitiesFrame.entities.values():
        if entity.contextualId < 0:
            monster = entity
            
            canCast, reason = CurrentPlayedFighterManager().canCastThisSpell(spellw.spellId, spellw.spellLevel, entity.contextualId)
            stats = StatsManager().getStats(entity.contextualId)
            hp = stats.getHealthPoints()
            stats.getMaxHealthPoints()
            is_monster = isinstance(entity, GameFightMonsterInformations)
            name = "unknown"
            level = "unknown"
            if isinstance(entity, GameFightMonsterInformations):
                monster = Monster.getMonsterById(entity.creatureGenericId)
                name = monster.name
                level = entity.creatureLevel
            status = FightersStateManager().getStatus(fighter_infos.contextualId)
            entry = {
                "name": name,
                "level": level,
                "teamId": entity.spawnInfo.teamId,
                "dead": entity.contextualId in Kernel().battleFrame.deadFightersList,
                "hidden": entity.contextualId in Kernel().fightContextFrame.hiddenEntities,
                "summoned": entity.stats.summoned,
                "canhit": canCast,
                "cell": entity.disposition.cellId,
                "id": entity.contextualId,
                "reason": reason,
                "hitpoints": hp,
                "isMonster": is_monster,
                "state": status.getActiveStatuses(),
                "boneId": entity.look.bonesId,
            }
            infosTable.append(entry)
            if (
                entry["teamId"] != fighter_infos.spawnInfo.teamId
                and not entry["dead"]
                and not entry["hidden"]
                and (target_sums or not entry["summoned"])
                and entry["canhit"]
                and entry["cell"] != -1
                and (target_boneId is None or entity.look.bonesId == target_boneId)
            ):
                result.append(Target(entity, fighter_infos.disposition.cellId))
    summaryTable = PrettyTable(
        ["name", "id", "boneId", "level", "hitpoints", "hidden", "summoned", "state", "canhit", "reason"]
    )
    for e in infosTable:
        summaryTable.add_row([e[k] for k in summaryTable.field_names])
    Logger().info("\n" + str(summaryTable))
    return result

def analyze_tackle_path(
    path: list[int], 
    target,
    fighter_infos: "GameFightFighterInformations",
    total_mp: int,
    total_ap: int,
    spell_ap_cost: int
) -> tuple[bool, list[int], int]:
    """Analyze path considering tackle effects.
    
    Args:
        path: List of cell IDs for movement
        target: Target entity
        fighter_infos: Fighter information for tackle calculations
        total_mp: Total movement points available
        total_ap: Total action points available
        spell_ap_cost: AP cost of the spell to cast
        
    Returns:
        Tuple of:
        - can_hit_target (bool): Whether target can be hit after movement
        - usable_path (list[int]): Path truncated to what's actually usable
        - movement_points_used (int): Number of MP actually used in movement
    """
    mpCount = 0
    mpLost = 0
    apLost = 0
    movementPoints = total_mp
    actionPoints = total_ap
    canHitTarget = target is not None
    usable_path = []
    
    if len(path) > 1:
        lastCellId = path[0]
        for cellId in path[1:]:
            tackle = TackleUtil.getTackle(fighter_infos, MapPoint.fromCellId(lastCellId))
            mpLost += int((total_mp - mpCount) * (1 - tackle) + 0.5)
            apLost += int(actionPoints * (1 - tackle) + 0.5)
            
            if apLost < 0:
                apLost = 0
            if mpLost < 0:
                mpLost = 0
                
            movementPoints = total_mp - mpLost
            actionPoints = total_ap - apLost
            
            if mpCount < movementPoints:
                mpCount += 1
            else:
                break
            lastCellId = cellId
            
        canHitTarget = target and actionPoints >= spell_ap_cost and mpCount >= len(path) - 1
        usable_path = path[: mpCount + 1]
        
    return canHitTarget, usable_path, mpCount