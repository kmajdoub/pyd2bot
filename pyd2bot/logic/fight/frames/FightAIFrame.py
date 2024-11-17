from pyd2bot.logic.fight.frames.fight_turn.FightPlayTurn import FightPlayTurn
from pyd2bot.data.models import Session
from pyd2bot.logic.fight.frames.FightPreparation import FightPreparation
from pyd2bot.logic.fight.frames.FightStateManager import FightStateManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightEndMessage import GameFightEndMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnReadyMessage import GameFightTurnReadyMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnReadyRequestMessage import GameFightTurnReadyRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnStartMessage import GameFightTurnStartMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnStartPlayingMessage import GameFightTurnStartPlayingMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority

class FightAIFrame(Frame):
    """
    Main fight manager frame handling:
    - Turn detection & synchronization
    - Ready state management
    - Delegating turn execution to FightPlayTurn
    """
    def __init__(self, session: Session):
        self.session = session
        self.state_manager = FightStateManager()
        
        super().__init__()

    def pushed(self) -> bool:
        Kernel().defer(FightPreparation().start)
        return True

    def pulled(self) -> bool:
        return True

    @property
    def priority(self) -> int:
        return Priority.VERY_LOW

    def process(self, msg: Message) -> bool:
        """Handle fight protocol messages"""
        if isinstance(msg, GameFightTurnStartMessage):
            return self._handle_turn_start(msg)
            
        elif isinstance(msg, GameFightTurnStartPlayingMessage):
            return self._handle_turn_playing()

        elif isinstance(msg, GameFightTurnReadyRequestMessage):
            return self._handle_ready_request()

        elif isinstance(msg, GameFightEndMessage):
            return self._handle_fight_end()

        return False

    def _handle_turn_start(self, msg: GameFightTurnStartMessage) -> bool:
        """Process turn start - identify if it's our turn"""
        self.state_manager.refresh_turn_state(msg)

        # Identify if it's our party member's turn
        player_infos = self.session.getPlayerById(msg.id)
        
        if player_infos:
            self.state_manager.current_player = player_infos
            Logger().info(f"It's our player's turn: {player_infos.name}")
            # If we already got play signal
            if self.state_manager.turn_playing:
                self._play_turn()
        else:
            Logger().info(f"Other player's turn: {msg.id}")
            
        return True

    def _handle_turn_playing(self) -> bool:
        """Handle turn play signal"""
        self.state_manager.turn_playing = True
        
        if self.state_manager.current_player:
            self._play_turn()
            
        return True

    def _handle_ready_request(self) -> bool:
        """Handle turn ready request"""
        if Kernel().battleFrame.is_sequence_executing():
            Logger().warning("Delaying turn end acknowledgement due to active sequence")
            KernelEventsManager().once(KernelEvent.SequenceExecFinished, lambda *_: self._send_ready(), originator=self)
            return True

        self._send_ready()
        return True

    def _handle_fight_end(self) -> bool:
        """Handle fight end cleanup"""
        if self.session.followers:
            for player in self.session.followers:
                player_manager = PlayedCharacterManager.getInstance(player.accountId)
                if player_manager:
                    player_manager.isFighting = False
        if FightPreparation().isRunning():   
            FightPreparation().stop()
        if FightPlayTurn().isRunning():
            FightPlayTurn().stop()
        Kernel().worker.removeFrame(self)
        return True

    def _play_turn(self):
        """Start turn execution if conditions met"""
        FightPlayTurn().start()

    def _send_ready(self):
        """Send turn ready acknowledgement"""
        self.state_manager.cleanup_turn_state()
        msg = GameFightTurnReadyMessage()
        msg.init(True)
        ConnectionsHandler().send(msg)
