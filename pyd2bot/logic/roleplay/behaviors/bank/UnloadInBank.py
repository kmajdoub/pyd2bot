from enum import Enum

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.misc.Localizer import Localizer
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.enums.ExchangeTypeEnum import \
    ExchangeTypeEnum
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class BankUnloadStates(Enum):
    WAITING_FOR_MAP = -1
    IDLE = 0
    WALKING_TO_BANK = 1
    INSIDE_BANK = 2
    INTERACTING_WITH_BANK_MAN = 3
    BANK_OPENED = 7
    BANK_OPEN_REQUESTED = 4
    UNLOAD_REQUEST_SENT = 6
    LEAVE_BANK_REQUESTED = 5
    RETURNING_TO_START_POINT = 8

class UnloadInBank(AbstractBehavior):
    TRANSFER_ITEMS_TIMED_OUT = 111111
    BANK_CLOSE_TIMED_OUT = 222222
    STORAGE_OPEN_TIMED_OUT = 9874521
    LEVEL_TOO_LOW = 909799
    
    def __init__(self):
        super().__init__()
        self.return_to_start = None
        self.callback = None
    
    def run(self, return_to_start=True, bankInfos=None) -> bool:
        if PlayedCharacterManager().limitedLevel < 10:
            return self.finish(self.LEVEL_TOO_LOW, "Character level is too low to use bank.")
        self.return_to_start = return_to_start
        if bankInfos is None:
            self.infos = Localizer.getBankInfos()
        else:
            self.infos = bankInfos
        Logger().debug("Bank infos: %s", self.infos.__dict__)
        self._startMapId = PlayedCharacterManager().currentMap.mapId
        self._startRpZone = PlayedCharacterManager().currentZoneRp
        self.state = BankUnloadStates.WALKING_TO_BANK
        self.npcDialog(
            self.infos.npcMapId, 
            self.infos.npcId, 
            self.infos.npcActionId, 
            self.infos.questionsReplies, 
            callback=self.onBankManDialogEnded,
        )
    
    def onBankManDialogEnded(self, code, error):
        if error:
            return self.finish(code, error)
        Logger().info("Ended bank man dialog waiting for storage to open...")
        self.once(
            event_id=KernelEvent.ExchangeBankStartedWithStorage, 
            callback=self.onStorageOpen,
            timeout=30,
            ontimeout=lambda: self.finish(self.STORAGE_OPEN_TIMED_OUT, "Dialog with Bank NPC ended correctly but storage didnt open on time!"),
        )
        
    def onStorageOpen(self, event, exchangeType, pods):
        if exchangeType == ExchangeTypeEnum.BANK:
            Logger().info("Bank storage open")
            self.once(
                event_id=KernelEvent.InventoryWeightUpdate, 
                callback=self.onInventoryWeightUpdate, 
                timeout=10,
                retryNbr=5,
                retryAction=Kernel().exchangeManagementFrame.exchangeObjectTransferAllFromInv,
                ontimeout=lambda: self.finish(self.TRANSFER_ITEMS_TIMED_OUT, "Transfer items to bank storage timeout."),
            )
            Kernel().exchangeManagementFrame.exchangeObjectTransferAllFromInv()
            Logger().info("Unload items in bank request sent.")
        else:
            raise Exception(f"Expected BANK storage to open but another type of exchange '{ExchangeTypeEnum.BANK}'!")

    def onStorageClose(self, event, success):
        Logger().info("Bank storage closed")
        self.state = BankUnloadStates.IDLE
        if self.return_to_start:
            Logger().info(f"Returning to start point")
            self.travel_using_zaap(self._startMapId, dstZoneId=self._startRpZone, callback=self.finish)
        else:
            self.finish(True, None)

    def onInventoryWeightUpdate(self, event, lastWeight, weight, max):
        Logger().info(f"Inventory Weight percent changed to : {round(100 * weight / max, 1)}%")
        self.once(
            event_id=KernelEvent.ExchangeClose, 
            callback=self.onStorageClose,
            timeout=10,
            retryNbr=5,
            retryAction=Kernel().exchangeManagementFrame.laveDialogRequest,
            ontimeout=lambda: self.finish(self.BANK_CLOSE_TIMED_OUT, "Bank close timed out!"),
        )
        Kernel().exchangeManagementFrame.laveDialogRequest()