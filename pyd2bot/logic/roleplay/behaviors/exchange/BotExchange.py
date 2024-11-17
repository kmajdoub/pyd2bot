from enum import Enum

from pyd2bot.data.enums import ServerNotificationEnum
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.data.models import Character
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.Listener import Listener
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import \
    ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import \
    InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.enums.ExchangeTypeEnum import \
    ExchangeTypeEnum
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import \
    BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


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

class BotExchange(AbstractBehavior):
    PHENIX_MAPID = None
    EXCHANGE_FAILED = 551
    INVENTORY_STILL_FULL = 551
    EXCHANGE_READY_TIMEOUT = 557
    TARGET_CANT_TAKE_ALL_ITEMS = 5023
    CANT_TAKE_ALL_SOURCE_ITEMS = 516493
    EXCHANGE_REQ_TIMEOUT = 7

    def __init__(self, ):
        super().__init__()
        self.wantsToMoveItemToExchange = set()
        self.acceptExchangeListener: Listener = None
        self.openExchangeListener: Listener = None
        self.exchangeLeaveListener = None
        self.nbrFails = 0

    def run(self, direction: str, target: Character, items: list = None) -> bool:
        self.direction = direction
        self.target = target
        self.items = items
        self.state = ExchangeStateEnum.NOT_STARTED
        self.giveAll = items is None
        self.state = ExchangeStateEnum.IDLE
        self.on_multiple(
            (KernelEvent.ExchangeRequestToMe, self.onExchangeRequestReceived),
            (KernelEvent.ExchangeRequestFromMe, self.onExchangeSent),
            (KernelEvent.ExchangeObjectListAdded, self.onExchangeObjectsAdded),
            (KernelEvent.ExchangeKamaModified, self.onKamasModified),
            (KernelEvent.ExchangeObjectAdded, self.onExchangeObjectAdded),
            (KernelEvent.ExchangeIsReady, self.onExchangeIsReady),
        )
        if self.direction == ExchangeDirectionEnum.GIVE:
            self.sendExchangeRequest()
        return True

    def onExchangeObjectAdded(self, event, iwAdded: ItemWrapper, remote):
        Logger().debug("Item added to exchange.")
        if self.direction == ExchangeDirectionEnum.GIVE:
            self.wantsToMoveItemToExchange.remove(iwAdded.objectUID)
            if len(self.wantsToMoveItemToExchange) == 0:
                Logger().debug("All items moved to exchange.")
                self.state = ExchangeStateEnum.EXCHANGE_OBJECTS_ADDED
                BenchmarkTimer(3, self.sendExchangeReady).start()

    def onExchangeIsReady(self, event, playerName, ready):
        Logger().debug(f"Exchange is ready received from target {playerName}.")
        if self.acceptExchangeListener is not None:
            self.acceptExchangeListener.cancelTimer()
        if self.direction == ExchangeDirectionEnum.RECEIVE and playerName == self.target.name and ready:
            BenchmarkTimer(3, self.sendExchangeReady).start()

    def onExchangeSent(self, event, source_name, target_name):
        if target_name == self.target.name:
                Logger().info("Exchange request success")
                self.state = ExchangeStateEnum.EXCHANGE_REQUEST_SENT

    def onExchangeRequestReceived(self, event, target_name, source_name):
        if source_name == self.target.name:
            self.state = ExchangeStateEnum.EXCHANGE_REQUEST_RECEIVED
            Kernel().commonExchangeManagementFrame.exchangeAccept()
            self.state = ExchangeStateEnum.EXCHANGE_REQUEST_ACCEPTED
        else:
            Kernel().commonExchangeManagementFrame.leaveShopStock()
            self.state = ExchangeStateEnum.IDLE

    def onExchangeOpen(self, event, exchangeType):
        Logger().debug("Exchange started.")
        if exchangeType == ExchangeTypeEnum.PLAYER_TRADE:
            self.state = ExchangeStateEnum.EXCHANGE_OPEN
            if self.direction == ExchangeDirectionEnum.GIVE:
                if self.giveAll:
                    Kernel().exchangeManagementFrame.exchangeObjectTransferAllFromInv()
                else:
                    for elem in self.items:
                        Kernel().commonExchangeManagementFrame.exchangeObjectMove(elem["uid"], elem["quantity"])
                        self.wantsToMoveItemToExchange.add(elem["uid"])
                Logger().debug("Moved items to exchange.")
        else:
            Logger().error(f"Expecting trade with player, received {exchangeType}")
            Kernel().commonExchangeManagementFrame.leaveShopStock()

    def onExchangeObjectsAdded(self, event, itemAddedArray: list[ItemWrapper], remote):
        Logger().debug("All items moved to exchange.")
        self.state = ExchangeStateEnum.EXCHANGE_OBJECTS_ADDED
        if self.direction == ExchangeDirectionEnum.GIVE:
            if self.giveAll:
                BenchmarkTimer(3, self.sendAllKamas).start()
            else:
                BenchmarkTimer(3, self.sendExchangeReady).start()
        return True
    
    def onKamasModified(self, event, quantity, remote):
        Logger().debug(f"{quantity} kamas added to exchange")
        self.state = ExchangeStateEnum.EXCHANGE_KAMAS_ADDED
        if self.direction == ExchangeDirectionEnum.GIVE:
            BenchmarkTimer(3, self.sendExchangeReady).start()
        return True

    def sendExchangeRequest(self):
        self.openExchangeListener = self.once(
            event_id=KernelEvent.ExchangeStartedType, 
            callback=self.onExchangeOpen, 
            timeout=self.EXCHANGE_REQ_TIMEOUT,
            retry_nbr=5,
            retry_action=lambda: Kernel().exchangeManagementFrame.exchangePlayerRequest(ExchangeTypeEnum.PLAYER_TRADE, self.target.id),
            ontimeout=lambda: self.finish(self.EXCHANGE_REQ_TIMEOUT, "send exchange timedout"), 
        )
        Kernel().exchangeManagementFrame.exchangePlayerRequest(ExchangeTypeEnum.PLAYER_TRADE, self.target.id)
        Logger().debug("Exchange open request sent")
        
    def onServerNotif(self, event, msgId, msgType, textId, text, params):
        self.exchangeLeaveListener.delete()
        if textId == 516493: # inventory full
            if self.acceptExchangeListener:
                self.acceptExchangeListener.cancelTimer()
            self.once(
                event_id=KernelEvent.ExchangeClose, 
                callback=lambda: self.finish(self.CANT_TAKE_ALL_SOURCE_ITEMS, "Space not enough to take guest items!"), 
            )
            Kernel().commonExchangeManagementFrame.leaveShopStock() 
        elif textId == ServerNotificationEnum.CANT_TAKE_ALL_OBJECTS: # the second player can't take all the load            
            timer = BenchmarkTimer(6, Kernel().commonExchangeManagementFrame.leaveShopStock)
            if self.acceptExchangeListener:
                self.acceptExchangeListener.cancelTimer()
            def onExchangeClose(event, msg):
                if timer:
                    timer.cancel()
                self.finish(self.TARGET_CANT_TAKE_ALL_ITEMS, "Space in target inventory not enough!")
            self.once(KernelEvent.ExchangeClose, onExchangeClose)
            timer.start()

    def onExchangeLeave(self, event, success):
        self.serverNotifListener.delete()
        self.state = ExchangeStateEnum.TERMINATED
        if success == True:
            if self.giveAll:
                if (PlayedCharacterManager().inventoryWeight / PlayedCharacterManager().inventoryWeightMax) > 0.9:
                    return self.finish(self.INVENTORY_STILL_FULL, "Inventory still full!")
            Logger().info("Exchange ended successfully.")
            self.finish(True, None)
        else:
            self.finish(self.EXCHANGE_FAILED, "Exchange failed")

    def sendExchangeReady(self):
        self.serverNotifListener = self.once(KernelEvent.ServerTextInfo, self.onServerNotif)
        self.exchangeLeaveListener = self.once(
            event_id=KernelEvent.ExchangeClose, 
            callback=self.onExchangeLeave, 
            timeout=5,
            retry_nbr=5,
            retry_action=lambda: Kernel().commonExchangeManagementFrame.exchangeReady(True),
            ontimeout=lambda: self.finish(self.EXCHANGE_READY_TIMEOUT, "Exchange ready timeout."), 
        )
        Kernel().commonExchangeManagementFrame.exchangeReady(True)
        Logger().debug("Exchange ready request sent.")

    def sendAllKamas(self):
        kamas_quantity = InventoryManager().inventory.kamas
        Logger().debug(f"There is {kamas_quantity} in bots inventory.")
        if kamas_quantity == 0:
            return BenchmarkTimer(3, self.sendExchangeReady).start()
        Kernel().exchangeManagementFrame.exchangeObjectMoveKama(kamas_quantity)

    def getState(self):
        return self.state.name