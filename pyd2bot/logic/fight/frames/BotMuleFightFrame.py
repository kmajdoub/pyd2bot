from Grinder.models import Character
from pyd2bot.logic.fight.messages.MuleSwitchedToCombatContext import \
    MuleSwitchedToCombatContext
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.fight.GameActionFightNoSpellCastMessage import \
    GameActionFightNoSpellCastMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.basic.TextInformationMessage import \
    TextInformationMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnReadyMessage import \
    GameFightTurnReadyMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnReadyRequestMessage import \
    GameFightTurnReadyRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnStartPlayingMessage import \
    GameFightTurnStartPlayingMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameContextReadyMessage import \
    GameContextReadyMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameMapNoMovementMessage import \
    GameMapNoMovementMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.CurrentMapMessage import \
    CurrentMapMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority


class BotMuleFightFrame(Frame):
    
    def __init__(self, leader: Character):
        super().__init__()
        self.leader = leader
        
    @property
    def priority(self) -> int:
        return Priority.VERY_LOW

    def pushed(self) -> bool:
        Logger().info("BotMuleFightFrame pushed")
        Kernel.getInstance(self.leader.login).worker.process(MuleSwitchedToCombatContext(PlayedCharacterManager().id))
        return True

    def pulled(self) -> bool:
        Logger().info("BotMuleFightFrame pulled")
        return True

    def process(self, msg: Message) -> bool:
        
        if isinstance(msg, GameFightTurnReadyRequestMessage):     
            turnEnd = GameFightTurnReadyMessage()
            turnEnd.init(True)
            ConnectionsHandler().send(turnEnd)
            return True

        elif isinstance(msg, CurrentMapMessage):
            gcrmsg = GameContextReadyMessage()
            gcrmsg.init(int(msg.mapId))
            ConnectionsHandler().send(gcrmsg)
            return True
        
        elif isinstance(msg, (GameMapNoMovementMessage, GameActionFightNoSpellCastMessage, GameFightTurnStartPlayingMessage, TextInformationMessage)):
            Kernel.getInstance(self.leader.login).worker.process(msg)
            return True