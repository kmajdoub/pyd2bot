from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightTurnStartMessage import (
    GameFightTurnStartMessage,
)
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority




class BotFightTurnFrame(Frame):
    def __init__(self):
        self._myTurn = False
        super().__init__()

    def pushed(self) -> bool:
        return True

    def pulled(self) -> bool:
        return True

    @property
    def priority(self) -> int:
        return Priority.ULTIMATE_HIGHEST_DEPTH_OF_DOOM

    def process(self, msg: Message) -> bool:

        if isinstance(msg, GameFightTurnStartMessage):
            turnStartMsg = msg
            self._myTurn = int(turnStartMsg.id) == int(PlayedCharacterManager().id)
