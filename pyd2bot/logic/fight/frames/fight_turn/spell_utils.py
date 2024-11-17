from pydofus2.com.ankamagames.atouin.utils.DataMapProvider import DataMapProvider
from typing import TYPE_CHECKING

from pydofus2.com.ankamagames.dofus.datacenter.spells.Spell import Spell
from pydofus2.com.ankamagames.dofus.logic.game.fight.managers.CurrentPlayedFighterManager import CurrentPlayedFighterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.zones.Cross import Cross
from pydofus2.com.ankamagames.jerakine.types.zones.Lozenge import Lozenge
from pydofus2.com.ankamagames.jerakine.utils.display.spellZone.SpellShapeEnum import SpellShapeEnum
from pydofus2.mapTools import MapTools

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.internalDatacenter.spells.SpellWrapper import SpellWrapper
    from pydofus2.com.ankamagames.jerakine.types.zones.DisplayZone import DisplayZone
    from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
    from pyd2bot.data.models import Character


def getSpellShape(spellw: "SpellWrapper") -> int:
    for spellEffect in spellw["effects"]:
        if spellEffect.zoneShape != 0 and (
            spellEffect.zoneSize > 0
            or spellEffect.zoneSize == 0
            and (spellEffect.zoneShape == SpellShapeEnum.P or spellEffect.zoneMinSize < 0)
        ):
            return spellEffect.zoneShape
    return 0

def getSpellZone(spellw: "SpellWrapper") -> "DisplayZone":
    range = spellw["range"]
    minRange = spellw["minRange"]
    if range is None or minRange is None:
        raise Exception(f"Spell range is None, {minRange} {range}")
    if range < minRange:
        range = minRange;
    spellShape = getSpellShape(spellw)
    castInLine = spellw["castInLine"] or (spellShape == SpellShapeEnum.l)
    if castInLine:
        if spellw["castInDiagonal"]:
            return Cross(SpellShapeEnum.UNKNOWN, minRange, range, DataMapProvider(), False, True)
        return Cross(SpellShapeEnum.UNKNOWN, minRange, range, DataMapProvider(), False)
    elif spellw["castInDiagonal"]:
        return Cross(SpellShapeEnum.UNKNOWN, minRange, range, DataMapProvider(), True)
    else:
        return Lozenge(SpellShapeEnum.UNKNOWN, minRange, range, DataMapProvider())

def check_line_of_sight(start_cell_id: int, end_cell_id: int) -> tuple[bool, str]:
    """Check if there is line of sight between two cells.
    
    Args:
        start_cell_id: Starting cell ID
        end_cell_id: Target cell ID
        fighter_pos: Current fighter position (for logging)
        
    Returns:
        Tuple of (has_los, reason) where has_los is True if there is LOS,
        and reason explains why if there isn't
    """
    line = MapTools.getMpLine(start_cell_id, end_cell_id)
    if len(line) <= 1:
        return True, ""
        
    for mp in line[:-1]:
        if not DataMapProvider().pointLos(mp.x, mp.y, False):
            return False, f"Obstacle between cells {start_cell_id} and {end_cell_id}"
            
    return True, ""

def can_cast_spell_on_cell(spell_id: int, spell_level: int, target_cell: int=0) -> tuple[bool, str]:
    """Check if a spell can be cast on a specific cell.
    
    Args:
        spell_id: ID of the spell to cast
        spell_level: Level of the spell
        caster_id: ID of the casting entity
        target_cell: Target cell ID
        
    Returns:
        Tuple of (can_cast, reason) where can_cast is True if spell can be cast,
        and reason explains why if it cannot
    """
    return CurrentPlayedFighterManager().canCastThisSpell(spell_id, spell_level, target_cell)

def get_player_spellw(playerManager: "PlayedCharacterManager", spellId: int, player: "Character") -> "SpellWrapper":
    if not playerManager:
        Logger().error("Asking for spellw when there is no player manager!")
        return None
    res = playerManager.getSpellById(spellId)
    if not res:
        Logger().error(
            f"Player {player.name} doesn't have spell list {playerManager.playerSpellList}"
        )
        res = SpellWrapper.create(spellId)
        spell = Spell.getSpellById(spellId)
        currentCharacterLevel = playerManager.limitedLevel
        spellLevels = spell.spellLevelsInfo
        index = 0
        for i in range(len(spellLevels) - 1, -1, -1):
            if currentCharacterLevel >= spellLevels[i].minPlayerLevel:
                index = i
                break
        res._spellLevel = spellLevels[index]
        res.spellLevel = index + 1
        playerManager.playerSpellList.append(res)
    return res