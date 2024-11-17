from typing import Dict, Optional, TYPE_CHECKING
from pyd2bot.logic.fight.frames.fight_turn.CastSpell import CastSpell
from pyd2bot.logic.fight.frames.fight_turn.FightMove import FightMoveBehavior
from pyd2bot.logic.fight.frames.fight_turn.TurnResult import TurnResult
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
if TYPE_CHECKING:
    from pyd2bot.logic.fight.frames.fight_turn.FightPlayTurn import FightPlayTurn

def handle_move_result(behavior: "FightPlayTurn", error_code: int, error_msg: str, infos: Optional[Dict] = None) -> None:
    """Handle movement action results"""
    # Success
    if error_code == 0:
        behavior._current_retry_count = 0
        behavior.next_action()
        return

    # Handle blocked cells first if info available
    if infos and infos.get("blocked_cell"):
        behavior._forbidden_cells.add(infos['blocked_cell'])
        Logger().info(f"Marked cell {infos['blocked_cell']} as blocked")
        if infos.get("stopped_at"):
            Logger().info(f"Movement stopped at cell {infos['stopped_at']}")

    # Map error codes to retry decisions
    movement_retry_map = {
        FightMoveBehavior.errors.NO_FIGHTER_POS: (False, True),    # (can_retry, end_turn)
        FightMoveBehavior.errors.PATH_BLOCKED: (True, False),
        FightMoveBehavior.errors.INSUFFICIENT_MP: (False, True),
        FightMoveBehavior.errors.MOVEMENT_FAILED: (True, False),
        FightMoveBehavior.errors.INVALID_PATH: (False, True),
        FightMoveBehavior.errors.MAX_RETRIES_EXCEEDED: (False, True)
    }

    can_retry, should_end_turn = movement_retry_map.get(error_code, (False, True))

    # If we've exceeded max retries, force end turn
    if behavior._current_retry_count >= 3:
        should_end_turn = True
        can_retry = False

    if should_end_turn:
        Logger().warning(f"Movement failed with non-recoverable error: {error_msg}")
        behavior._end_turn(TurnResult.NO_PATH, error_msg)
        return

    # Restart turn planning with updated forbidden cells
    if can_retry:
        Logger().info(f"Retrying turn after movement error: {error_msg}")
        behavior._current_retry_count += 1
        behavior._action_queue.clear()
        behavior.main()

    else:
        Logger().warning(f"Movement failed after retries: {error_msg}")
        behavior._end_turn(TurnResult.NO_PATH, error_msg)

def handle_spell_result(behavior: "FightPlayTurn", error_code: int, error_msg: str, infos: Optional[Dict] = None) -> None:
    """Handle spell casting action results"""
    if error_code == 0:  # Success
        behavior.next_action()
        return

    # Map error codes to retry decisions
    spell_retry_map = {
        CastSpell.errors.NO_LOS.value: (True, False), # (can_retry, end_turn)
        CastSpell.errors.UNEXPECTED_SPELL_CAST.value: (False, True),
        CastSpell.errors.SPELL_CAST_FAILED.value: (True, False),
        CastSpell.errors.CANT_CAST_SPELL.value: (False, True),
        CastSpell.errors.NO_FIGHTER_POS.value: (False, True)
    }

    can_retry, should_end_turn = spell_retry_map.get(error_code, (False, True))

    if should_end_turn:
        Logger().warning(f"Spell cast failed with non-recoverable error: {error_msg}")
        behavior._end_turn(TurnResult.CANNOT_CAST.value, error_msg)
        return

    if can_retry and behavior._current_retry_count < 3:
        Logger().info(f"Retrying turn after spell cast error: {error_msg}")
        behavior._current_retry_count += 1
        behavior._action_queue.clear()
        behavior.main()
        # Restart turn planning
    else:
        Logger().warning(f"Spell cast failed after retries: {error_msg}")
        behavior._end_turn(TurnResult.CANNOT_CAST.value, error_msg)
