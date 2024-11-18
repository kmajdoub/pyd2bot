from enum import Enum, auto
import random
from pyd2bot.logic.fight.behaviors.FightStateManager import FightStateManager
from pyd2bot.logic.fight.behaviors.fight_turn.spell_utils import can_cast_spell_on_cell, check_line_of_sight
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.atouin.HaapiEventsManager import HaapiEventsManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InactivityManager import InactivityManager
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.fight.GameActionFightCastRequestMessage import GameActionFightCastRequestMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class CastSpell(AbstractBehavior):
    
    class errors(Enum):
        NO_LOS = auto()
        UNEXPECTED_SPELL_CAST = auto()
        SPELL_CAST_FAILED = auto()
        CANT_CAST_SPELL = auto()
        NO_FIGHTER_POS = auto()

    def __init__(self, target_cellId):
        super().__init__()
        self.target_cellId = target_cellId
        self._cast_spell_request_sent = False
        self.state_manager = FightStateManager()

    def run(self) -> bool:
        """Start travel to marketplace"""
        self.once(KernelEvent.SpellCastFailed, self.on_spell_cast_failed)
        self.on(KernelEvent.FighterCastedSpell, self.on_spell_casted)
        self.castSpell()

    def castSpell(self) -> None:
        Logger().info(f"Casting spell {self.state_manager.spellId} on cell {self.target_cellId}")
        fighterPos = self.state_manager.fighter_pos
        if not fighterPos:
            self.finish(self.errors.NO_FIGHTER_POS, "Couldn't find fighter position!")
            return

        if not self._cast_spell_request_sent:
            canCast, reason = can_cast_spell_on_cell(self.state_manager.spellId, self.state_manager.spellw.spellLevel, self.target_cellId)
            if canCast:
                has_los, los_reason = check_line_of_sight(fighterPos.cellId, self.target_cellId)
                if not has_los:
                    Logger().error(f"Can't cast spell {self.state_manager.spellId} on cell {self.target_cellId}: {los_reason}")
                    self.finish(self.errors.NO_LOS, "Cast spell no LOS")
                    return
                self.send_cast_spell_request()
            else:
                self.finish(self.errors.CANT_CAST_SPELL, f"Cant cast spell for reason : {reason}")

    def _handle_server_info(self, event, msgId, msgType, textId, text, params):
        """Handle server info messages"""
        if textId == 144451:  # Line of sight blocked
            Logger().warning("Line of sight blocked")
            self.finish(self.errors.NO_LOS, "Cast spell no LOS")
  
    def send_cast_spell_request(self):
        self._cast_spell_request_sent = True
        message = GameActionFightCastRequestMessage()
        message.init(self.state_manager.spellId, self.target_cellId)
        self.state_manager.connection.send(message)
        InactivityManager().activity()
        if random.random() < 0.9:
            HaapiEventsManager().registerShortcutUse('useSpellLine1')

    def on_spell_casted(self, event, sourceId, destinationCellId, sourceCellId, spellId):
        if sourceId == self.state_manager.current_player.id and self.target_cellId == destinationCellId:
            event.listener.delete()
            if self._cast_spell_request_sent:
                Logger().info(f"Spell casted successfully!")
                self.finish(0)
            else:
                self.finish(self.errors.UNEXPECTED_SPELL_CAST, f"A Spell was casted but the player didn't request any!")

    def on_spell_cast_failed(self, event):
        if not self.state_manager.current_player :
            return self.finish(0)

        if self._cast_spell_request_sent:
            self.finish(self.errors.SPELL_CAST_FAILED, "Failed to cast spell!")
