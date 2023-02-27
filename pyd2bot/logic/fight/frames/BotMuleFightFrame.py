

from pyd2bot.logic.managers.BotConfig import BotConfig
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.network.messages.game.actions.fight.GameActionFightNoSpellCastMessage import GameActionFightNoSpellCastMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.basic.TextInformationMessage import TextInformationMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameContextReadyMessage import GameContextReadyMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameMapMovementMessage import GameMapMovementMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameMapNoMovementMessage import GameMapNoMovementMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnReadyMessage import GameFightTurnReadyMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnReadyRequestMessage import GameFightTurnReadyRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnStartPlayingMessage import GameFightTurnStartPlayingMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.CurrentMapMessage import CurrentMapMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority


class BotMuleFightFrame(Frame):
    
    def __init__(self):
        super().__init__()
        
    @property
    def priority(self) -> int:
        return Priority.VERY_LOW

    def pushed(self) -> bool:
        Logger().info("BotMuleFightFrame pushed")
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
            Kernel.getInstance(BotConfig().leader.login).worker.process(msg)
            return True