from typing import TYPE_CHECKING, Callable, List, Optional
from pyd2bot.logic.fight.frames.FightStateManager import FightStateManager
from pyd2bot.logic.fight.frames.fight_turn.TurnResult import TurnResult
from pyd2bot.logic.fight.frames.fight_turn.fight_turn_errors_handling import handle_move_result, handle_spell_result
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.fight.frames.fight_turn.fight_algo_utils import (
    Target,
    analyze_tackle_path,
    find_path_to_target,
    get_targetable_entities,
)
from pyd2bot.logic.fight.frames.fight_turn.spell_utils import can_cast_spell_on_cell
from pyd2bot.misc.BotEventsManager import BotEventsManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InactivityManager import InactivityManager
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnFinishMessage import (
    GameFightTurnFinishMessage,
)
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.network.types.game.context.fight.GameFightFighterInformations import (
        GameFightFighterInformations,
    )


class FightPlayTurn(AbstractBehavior):
    """
    Handles the execution of a player's turn in combat.

    Responsible for:
    1. Turn initialization and validation
    2. Action planning and execution
    3. State management through FightStateBank
    4. Turn completion and cleanup
    """

    def __init__(self):
        super().__init__()
        self._action_queue: List[Callable] = []
        self._forbidden_cells = set()
        self.state_manager = FightStateManager()
        self._current_retry_count = 0
        self._end_turn_sent = False

    # === Turn Lifecycle ===
    def run(self) -> bool:
        """Start turn execution flow"""
        Logger().info(f"Starting turn execution for '{self.state_manager.current_player.name}'")
        if not self.state_manager.is_player_alive():
            Logger().info(f"Player {self.state_manager.current_player.name} is dead")
            return self.finish(TurnResult.PLAYER_DEAD)

        if Kernel().battleFrame.is_sequence_executing():
            Logger().info("Waiting for sequences to end before starting turn")
            self.once(KernelEvent.SequenceExecFinished, lambda *_: self.run())
            return True

        self._initialize_turn()
        return True

    def _initialize_turn(self) -> None:
        """Initialize turn state and start execution"""
        # Clear previous state
        self._action_queue.clear()
        self._forbidden_cells.clear()

        # Validate and prepare turn state
        if not self.state_manager.validate_turn_state():
            if not self.state_manager.player_manager:
                Logger().warning(f"{self.state_manager.current_player.name} seems to be disconnected")
                BotEventsManager().once_member_joined_fight_context(
                    self.state_manager.current_player.id, 
                    lambda *_: self._initialize_turn(), 
                    originator=self
                )
                return self.finish(TurnResult.DISCONNECTED, "Player disconnected")
            return self.finish(TurnResult.INVALID_STATE, "Invalid turn state")

        # Prepare fight state if not already done
        self.state_manager.prepare_turn_state()
        self.main()

    # === Main Turn Logic ===
    def main(self) -> None:
        """Core turn execution logic"""
        if not self.state_manager.is_player_alive():
            Logger().info(f"Player {self.state_manager.current_player.name} is dead")
            return self._end_turn()

        if not self.state_manager.get_enemies():
            Logger().debug("All enemies are dead, fight will end")
            return self._end_turn()

        if not self._can_cast_spells():
            return self._end_turn(TurnResult.CANNOT_CAST, "Unable to cast spells")

        filters = (
            [(True, 2672), (True, 91)]
            if self.state_manager.session.isTreasureHuntSession
            else [(False, None), (True, None)]
        )

        # Try each filter until we find valid targets and path
        for target_filter in filters:
            targets = get_targetable_entities(
                self.state_manager.spellw,
                self.state_manager.fighter_infos,
                *target_filter
            )
            if not targets:
                continue

            self.state_manager.log_turn_stats()
            target, path = find_path_to_target(
                self.state_manager.spellw,
                targets,
                self.state_manager.fighter_pos,
                self.state_manager.fighter_infos,
                self._forbidden_cells,
                self.state_manager.movement_points,
            )

            if path is not None:
                Logger().info(f"Found path {path} to target {target}")
                if not path:  # Empty path means we can hit from current position
                    Logger().info("Can hit target from current position")
                    self._queue_actions(True, [], target)
                    self.next_action()  # Call next_action() here too
                    return

                can_hit_target, current_path, _ = analyze_tackle_path(
                    path=path,
                    target=target,
                    fighter_infos=self.state_manager.fighter_infos,
                    total_mp=self.state_manager.movement_points,
                    total_ap=self.state_manager.action_points,
                    spell_ap_cost=self.state_manager.spellw["apCost"],
                )

                self._queue_actions(can_hit_target, current_path, target)
                self.next_action()
                return

        # No valid targets/paths found with any filter
        return self._end_turn(TurnResult.NO_TARGETS, "No valid targets found")

    def _queue_actions(self, can_hit_target: bool, path: List[int], target: "Target") -> None:
        """Queue movement and attack actions"""
        if len(path) > 1:
            self.add_action(lambda: self.fight_move(path, lambda *args: handle_move_result(self, *args)))

        if can_hit_target:
            self.add_action(lambda: self.cast_spell(target.pos.cellId, lambda *args: handle_spell_result(self, *args)))
            return  # Don't queue end_turn - let next_action() flow back to main()

        # Only queue end_turn if we found a path but can't hit target
        # This means we've used movement points but still can't reach
        self.add_action(lambda: self._end_turn())

    def next_action(self, event=None) -> None:
        """Execute next queued action"""
        if Kernel().battleFrame.is_sequence_executing():
            # Logger().warning("Waiting for sequences to end before trying next action ...")
            self.once(KernelEvent.SequenceExecFinished, lambda *_: self.next_action())
            return

        if self._action_queue:
            action = self._action_queue.pop(0)
            action()
        elif not self._end_turn_sent:  # Only try main() if we haven't sent end turn
            self.main()

    def add_action(self, action: Callable) -> None:
        """Add action to queue"""
        self._action_queue.append(action)

    # === Turn Completion ===
    def _end_turn(self, result_code: int = TurnResult.SUCCESS, error_msg: Optional[str] = None) -> None:
        """Complete turn execution with proper cleanup"""
        if self._end_turn_sent:
            raise Exception("Trying to send fight end turn two times !")

        self.state_manager.turn_playing = False
        if not self.state_manager.current_player:
            return self.finish(result_code, error_msg)

        # Check player state
        if not self.state_manager.is_player_alive():
            Logger().info(f"Player {self.state_manager.current_player.name} is dead")
            result_code = TurnResult.PLAYER_DEAD
            error_msg = "Player died during turn"

        if not self.state_manager.fighter_infos:
            Logger().error(f"Can't find fighter infos for player {self.state_manager.current_player.id}")
            result_code = TurnResult.NO_FIGHTER_INFO
            error_msg = "No fighter information available"

        # Send turn end message if possible
        if self.state_manager.connection and self.state_manager.connection.inGameServer():
            message = GameFightTurnFinishMessage()
            message.init(False)
            self.state_manager.connection.send(message)
            InactivityManager().activity()
            self._end_turn_sent = True
        else:
            Logger().error(f"Cannot end turn - player offline: {self.state_manager.current_player.name}")

        # Finish immediately with result code
        self.finish(result_code, error_msg)

    def _can_cast_spells(self) -> bool:
        """Check spell casting ability"""
        can_cast, reason = can_cast_spell_on_cell(self.state_manager.spellId, self.state_manager.spellw.spellLevel)
        if not can_cast:
            Logger().info(f"Unable to cast spells: {reason}")
        return can_cast