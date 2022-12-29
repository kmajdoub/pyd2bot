from threading import Timer
from pyd2bot.logic.roleplay.messages.ExchangeConcludedMessage import ExchangeConcludedMessage
from pydofus2.com.ankamagames.dofus.datacenter.communication.InfoMessage import InfoMessage
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.actions.DeleteObjectAction import DeleteObjectAction
from pydofus2.com.ankamagames.dofus.network.messages.game.basic.TextInformationMessage import TextInformationMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeAcceptMessage import (
    ExchangeAcceptMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeIsReadyMessage import (
    ExchangeIsReadyMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeLeaveMessage import (
    ExchangeLeaveMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeObjectAddedMessage import (
    ExchangeObjectAddedMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeObjectMoveKamaMessage import ExchangeObjectMoveKamaMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeObjectMoveMessage import (
    ExchangeObjectMoveMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeObjectTransfertAllFromInvMessage import (
    ExchangeObjectTransfertAllFromInvMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeObjectsAddedMessage import ExchangeObjectsAddedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangePlayerRequestMessage import (
    ExchangePlayerRequestMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeReadyMessage import (
    ExchangeReadyMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeRequestedTradeMessage import (
    ExchangeRequestedTradeMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeStartedWithPodsMessage import (
    ExchangeStartedWithPodsMessage,
)
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.items.ExchangeKamaModifiedMessage import ExchangeKamaModifiedMessage
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority
from enum import Enum
logger = Logger()


class ExchangeDirectionEnum(Enum):
    GIVE = 0
    RECEIVE = 1
class ExchangeStateEnum(Enum):
    NOT_STARTED = -1
    IDLE = 0
    EXCHANGE_REQUEST_SENT = 1
    EXCHANGE_REQUEST_RECEIVED = 2
    EXCHANGE_REQUEST_ACCEPTED = 3
    EXCHANGE_OPEN = 4
    EXCHANGE_OBJECTS_ADDED = 5
    EXCHANGE_KAMAS_ADDED = 6
    EXCHANGE_READY_SENT = 7
    TERMINATED = 8

class BotExchangeFrame(Frame):
    PHENIX_MAPID = None
    state = ExchangeStateEnum.NOT_STARTED
    
    def __init__(self, direction: str, target: dict, items: list = None):
        self.direction = direction
        self.target = target
        self.items = items
        if items is None:
            self.giveAll = True
            self.step = 1
        else:
            self.giveAll = False
            self.step = len(items)
        self.wantsToMoveItemToExchange = set()
        self.acceptExchangeTimer : Timer = None
        self.openExchangeTimer : Timer = None
        super().__init__()

    def pushed(self) -> bool:
        logger.debug("BotExchangeFrame pushed")
        self.state = ExchangeStateEnum.IDLE
        if self.direction == ExchangeDirectionEnum.GIVE:
            self.sendExchangeRequest()
        return True

    def pulled(self) -> bool:
        logger.debug("BotExchangeFrame pulled")
        if self.acceptExchangeTimer is not None:
            self.acceptExchangeTimer.cancel()
        if self.openExchangeTimer:
            self.openExchangeTimer.cancel()
        return True

    @property
    def priority(self) -> int:
        return Priority.VERY_LOW

    def process(self, msg: Message) -> bool:
        
        if isinstance(msg, ExchangeRequestedTradeMessage):
            logger.debug(f"Exchange request received from {msg.source} to {msg.target}")
            if msg.source == self.target["id"]:
                self.state = ExchangeStateEnum.EXCHANGE_REQUEST_RECEIVED
                ConnectionsHandler.getConnection().send(ExchangeAcceptMessage())
                self.state = ExchangeStateEnum.EXCHANGE_REQUEST_ACCEPTED
            elif int(msg.source) == int(PlayedCharacterManager().id):
                if self.openExchangeTimer:
                    self.openExchangeTimer.cancel()
                self.state = ExchangeStateEnum.EXCHANGE_REQUEST_SENT

        elif isinstance(msg, TextInformationMessage):
            if InfoMessage.getInfoMessageById(msg.msgType * 10000 + msg.msgId):
                infoMsg = InfoMessage.getInfoMessageById(msg.msgType * 10000 + msg.msgId)
                logger.debug(f"info: {infoMsg.text}")
                if msg.msgId == 12: # inventory plein
                    for iw in InventoryManager().realInventory:
                        if not iw.isEquipment and iw.isDestructible:
                            logger.debug(f"delete {iw.name} x 1")
                            doa = DeleteObjectAction.create(iw.objectUID, 1)
                            Kernel().getWorker().process(doa)
                            return True
                
        elif isinstance(msg, ExchangeStartedWithPodsMessage):
            logger.debug("Exchange started.")
            self.state = ExchangeStateEnum.EXCHANGE_OPEN
            if self.direction == ExchangeDirectionEnum.GIVE:
                if self.giveAll:
                    ConnectionsHandler.getConnection().send(ExchangeObjectTransfertAllFromInvMessage())
                else:
                    for elem in self.items:
                        rmsg = ExchangeObjectMoveMessage()
                        rmsg.init(objectUID_=elem["uid"], quantity_=elem["quantity"])
                        ConnectionsHandler.getConnection().send(rmsg)
                        self.wantsToMoveItemToExchange.add(elem["uid"])
                logger.debug("Moved items to exchange.")
            return True

        elif isinstance(msg, ExchangeObjectsAddedMessage):
            logger.debug("All items moved to exchange.")
            self.state = ExchangeStateEnum.EXCHANGE_OBJECTS_ADDED
            if self.direction == ExchangeDirectionEnum.GIVE:
                if self.giveAll:
                    Timer(3, self.sendAllKamas).start()
                else:
                    Timer(3, self.sendExchangeReady).start()
            return True
        
        elif isinstance(msg, ExchangeKamaModifiedMessage):
            logger.debug(f"{msg.quantity} kamas added to exchange")
            self.state = ExchangeStateEnum.EXCHANGE_KAMAS_ADDED
            self.step += 1
            if self.direction == ExchangeDirectionEnum.GIVE:
                Timer(3, self.sendExchangeReady).start()
            return True
                
        elif isinstance(msg, ExchangeObjectAddedMessage):
            logger.debug("Item added to exchange.")
            if self.direction == ExchangeDirectionEnum.GIVE:
                self.wantsToMoveItemToExchange.remove(msg.object.objectUID)
                if len(self.wantsToMoveItemToExchange) == 0:
                    logger.debug("All items moved to exchange.")
                    self.state = ExchangeStateEnum.EXCHANGE_OBJECTS_ADDED
                    Timer(3, self.sendExchangeReady).start()
                    
        elif isinstance(msg, ExchangeIsReadyMessage):
            logger.debug(f"Exchange is ready received from target {int(msg.id)}")
            if self.acceptExchangeTimer is not None:
                self.acceptExchangeTimer.cancel()
            if self.direction == ExchangeDirectionEnum.RECEIVE and int(msg.id) == int(self.target["id"]) and msg.ready:
                Timer(3, self.sendExchangeReady).start()
                return True

        elif isinstance(msg, ExchangeLeaveMessage):
            logger.debug("ExchangeLeaveMessage received")
            if msg.success == True:
                logger.debug("Exchange ended successfully")
                self.state = ExchangeStateEnum.TERMINATED
                Kernel().getWorker().processImmediately(ExchangeConcludedMessage())
                Kernel().getWorker().removeFrame(self)
            else:
                raise Exception("Exchange failed")

    def sendExchangeRequest(self):
        msg = ExchangePlayerRequestMessage()
        msg.init(exchangeType_=1, target_=self.target["id"])
        ConnectionsHandler.getConnection().send(msg)
        self.openExchangeTimer = Timer(3, self.sendExchangeRequest)
        self.openExchangeTimer.start()
        logger.debug("Exchange open request sent")

    def sendExchangeReady(self):
        if self.state == ExchangeStateEnum.TERMINATED:
            return
        readymsg = ExchangeReadyMessage()
        readymsg.init(ready_=True, step_=self.step)
        ConnectionsHandler.getConnection().send(readymsg)
        self.acceptExchangeTimer = Timer(5, self.sendExchangeReady)
        self.acceptExchangeTimer.start()
        logger.debug("Exchange is ready sent.")
    
    def sendAllKamas(self):
        eomkm = ExchangeObjectMoveKamaMessage()
        kamas_quantity = InventoryManager().inventory.kamas
        logger.debug(f"There is {kamas_quantity} in bots inventory.") 
        eomkm.init(kamas_quantity)
        ConnectionsHandler.getConnection().send(eomkm)