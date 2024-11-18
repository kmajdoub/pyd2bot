from typing import TYPE_CHECKING, Optional, List
from pyd2bot.data.models import Character, Session
from pydofus2.com.ankamagames.dofus.internalDatacenter.spells.SpellWrapper import SpellWrapper
from pydofus2.com.ankamagames.dofus.internalDatacenter.stats.EntityStats import EntityStats
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.frames.SpellInventoryManagementFrame import SpellInventoryManagementFrame
from pydofus2.com.ankamagames.dofus.logic.game.fight.managers.BuffManager import BuffManager
from pydofus2.com.ankamagames.dofus.logic.game.fight.managers.CurrentPlayedFighterManager import CurrentPlayedFighterManager
from pydofus2.com.ankamagames.dofus.logic.common.managers.StatsManager import StatsManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.atouin.managers.EntitiesManager import EntitiesManager
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnResumeMessage import GameFightTurnResumeMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnStartMessage import GameFightTurnStartMessage
from pydofus2.com.ankamagames.jerakine.metaclass.Singleton import Singleton
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from pydofus2.damageCalculation.tools.StatIds import StatIds
from pyd2bot.logic.fight.behaviors.fight_turn.spell_utils import get_player_spellw
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    from pyd2bot.logic.fight.frames.FightAIFrame import FightAIFrame
    from pydofus2.com.ankamagames.dofus.network.types.game.context.fight.GameFightFighterInformations import GameFightFighterInformations

class FightStateManager(metaclass=Singleton):
    """
    Centralized storage for fight state data and utilities
    """
    
    def __init__(self):
        self._current_player = None
        self._turn_preparation_done = False
        self.turn_playing = False

    @property
    def session(self) -> "Session":
        return self.fight_frame.session
    
    @property
    def fight_frame(self) -> "FightAIFrame":
        return Kernel().worker.getFrameByName("FightAIFrame")
    
    @property
    def current_player(self) -> Character:
        return self._current_player

    @current_player.setter
    def current_player(self, value):
        self._current_player = value
        self._turn_preparation_done = False  # Reset preparation state
        if value is not None:
            CurrentPlayedFighterManager().currentFighterId = value.id
            self._setup_player_manager()

    def prepare_turn_state(self) -> None:
        """
        Initialize all state for turn start.
        Handles:
        - Fighter state setup
        - Spell refresh and cooldowns
        - Fighting status
        """
        if not self.current_player or not self.player_manager:
            return
        CurrentPlayedFighterManager().playerManager = PlayedCharacterManager.getInstance(str(self.current_player.accountId))
        CurrentPlayedFighterManager().currentFighterId = self.current_player.id
        CurrentPlayedFighterManager().conn = self.connection
        CurrentPlayedFighterManager().resetPlayerSpellList()
        SpellWrapper.refreshAllPlayerSpellHolder(self.current_player.id)
        SpellInventoryManagementFrame().applySpellGlobalCoolDownInfo(self.current_player.id)
        CurrentPlayedFighterManager().playerManager.isFighting = True
        if Kernel().turnFrame:
            Kernel().turnFrame.myTurn = True
        CurrentPlayedFighterManager().resetPlayerSpellList()
        SpellWrapper.refreshAllPlayerSpellHolder(self.current_player.id)
        SpellInventoryManagementFrame().applySpellGlobalCoolDownInfo(self.current_player.id)
        # Mark as fighting
        self.player_manager.isFighting = True
        self._turn_preparation_done = True

    def cleanup_turn_state(self) -> None:
        """
        Cleanup state at turn end.
        Handles:
        - Buff cleanup
        - Spell holder refresh
        - Spell cast management
        """
        if not self.current_player:
            return

        # Update buffs and spells
        BuffManager().markFinishingBuffs(self.current_player.id)
        SpellWrapper.refreshAllPlayerSpellHolder(self.current_player.id)

        # Update spell cast states
        spell_cast_manager = CurrentPlayedFighterManager().getSpellCastManagerById(self.current_player.id)
        if spell_cast_manager:
            spell_cast_manager.nextTurn()

        self._turn_preparation_done = False
        self.current_player = None
        
    def validate_turn_state(self) -> bool:
        """
        Validate that all required state is properly initialized
        """
        return (
            self.current_player is not None and
            self.player_manager is not None and
            self._turn_preparation_done and
            self.fighter_infos is not None
        )

    @property
    def is_turn_prepared(self) -> bool:
        """Check if turn state has been properly prepared"""
        return self._turn_preparation_done

    def _setup_player_manager(self) -> None:
        """Set up player manager for current fighter"""
        player_manager = PlayedCharacterManager.getInstance(self.current_player.accountId)
        if player_manager:
            CurrentPlayedFighterManager().playerManager = player_manager
            self.prepare_turn_state()  # Prepare state when player manager is set up
        else:
            Logger().error(f"No player manager found for {self.current_player.name}")

    @property
    def spellId(self) -> int:
        """Get current spell ID based on session type"""
        if self.fight_frame.session.isTreasureHuntSession:
            return self.current_player.treasureHuntFightSpellId
        return self.current_player.primarySpellId

    @property
    def player_manager(self) -> "PlayedCharacterManager":
        if not self.current_player:
            Logger().warning("Asking for player manager for None current player")
            return None
        playerManager = PlayedCharacterManager.getInstance(str(self.current_player.accountId))
        if not playerManager:
            Logger().error("Unable to find the current player manager instance for accountId: " + str(self.current_player.accountId))
            Logger().info(PlayedCharacterManager.getInstances())
        return playerManager

    @property
    def spellw(self) -> SpellWrapper:
        """Get spell wrapper for current spell"""
        return get_player_spellw(
            self.player_manager,
            self.spellId,
            self.current_player
        )

    @property
    def player_stats(self) -> EntityStats:
        """Get current player stats"""
        return StatsManager().getStats(self.current_player.id)

    @property
    def hitpoints(self) -> int:
        """Get current health points"""
        return CurrentPlayedFighterManager().getStats().getHealthPoints()

    @property
    def action_points(self) -> int:
        """Get current action points"""
        return CurrentPlayedFighterManager().getStats().getStatTotalValue(StatIds.ACTION_POINTS)

    @property
    def movement_points(self) -> int:
        """Get current movement points"""
        return CurrentPlayedFighterManager().getStats().getStatTotalValue(StatIds.MOVEMENT_POINTS)

    @property
    def fighter_infos(self) -> "GameFightFighterInformations":
        """Get current fighter information"""
        return Kernel().fightEntitiesFrame.getEntityInfos(self.current_player.id)

    @property
    def fighter_pos(self) -> Optional[MapPoint]:
        """Get current fighter position"""
        entity = EntitiesManager().getEntity(self.current_player.id)
        return entity.position if entity else None

    @property
    def connection(self) -> ConnectionsHandler:
        """Get current connection handler"""
        return ConnectionsHandler.getInstance(self.current_player.accountId)

    def is_player_alive(self) -> bool:
        """Check if current player is alive"""
        return (
            self.current_player is not None 
            and self.current_player.id not in Kernel().battleFrame.deadFightersList
        )

    def get_enemies(self) -> List["GameFightFighterInformations"]:
        """Get list of enemy fighters"""
        if not self.fighter_infos:
            return []
        return [
            entity for entity in Kernel().fightEntitiesFrame.entities.values()
            if entity.spawnInfo.teamId != self.fighter_infos.spawnInfo.teamId
        ]

    def log_turn_stats(self) -> None:
        """Log current turn statistics"""
        Logger().info(
            f"MP: {self.movement_points}, "
            f"AP: {self.action_points}, "
            f"HP: {self.hitpoints}"
        )
        Logger().info(
            f"Current attack spell: {self.spellw.spell.name}, "
            f"range: {self.spellw.maxRange}"
        )

    def refresh_turn_state(self, msg: GameFightTurnStartMessage):
        """Update turn state and buffs"""
        player_id = msg.id

        if not isinstance(msg, GameFightTurnResumeMessage):
            BuffManager().decrementDuration(player_id)
            BuffManager().resetTriggerCount(player_id)

        # Clear previous positions
        if Kernel().battleFrame:
            Kernel().battleFrame.removeSavedPosition(player_id)
            if Kernel().fightEntitiesFrame:
                for entity_id, info in Kernel().fightEntitiesFrame.entities.items():
                    if info and info.stats.summoner == player_id:
                        Kernel().battleFrame.removeSavedPosition(entity_id)