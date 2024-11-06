from enum import Enum
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.enums.ExchangeTypeEnum import ExchangeTypeEnum
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class UnloadInBank(AbstractBehavior):
    TRANSFER_ITEMS_TIMED_OUT = 111111
    BANK_CLOSE_TIMED_OUT = 222222
    LEVEL_TOO_LOW = 909799
    
    def __init__(self):
        super().__init__()
        self._logger = Logger()
        self.return_to_start = None
        self._start_map_id = None
        self._start_zone = None
        self.leave_bank_open = False

    def run(self, return_to_start=True, bankInfos=None, leave_bank_open=False) -> bool:
        if PlayedCharacterManager().limitedLevel < 10:
            return self.finish(self.LEVEL_TOO_LOW, "Character level is too low to use bank.")
        
        self.return_to_start = return_to_start
        self.leave_bank_open = leave_bank_open
        self._start_map_id = PlayedCharacterManager().currentMap.mapId
        self._start_zone = PlayedCharacterManager().currentZoneRp
        
        # Use open_bank helper
        self.open_bank(bankInfos=bankInfos, callback=self._on_bank_opened)
        return True

    def _on_bank_opened(self, code, error):
        if error:
            return self.finish(code, error)
            
        # Check if there are items to transfer
        bag_items = InventoryManager().inventory.getView("storage").content
        has_items_to_transfer = False
        for item in bag_items:
            if not item.linked:
                has_items_to_transfer = True
                break
        
        if not has_items_to_transfer:
            self._logger.info("No items to unload in bank")
            if self.leave_bank_open:
                return self.finish(0, None)
            self.close_dialog(self._on_storage_close)
            return
            
        self.once(
            event_id=KernelEvent.InventoryWeightUpdate, 
            callback=self._on_inventory_weight_update, 
            timeout=10,
            retryNbr=5,
            retryAction=Kernel().exchangeManagementFrame.exchangeObjectTransferAllFromInv,
            ontimeout=lambda: self.finish(self.TRANSFER_ITEMS_TIMED_OUT, "Transfer items to bank storage timeout."),
        )
        
        Kernel().exchangeManagementFrame.exchangeObjectTransferAllFromInv()
        self._logger.info("Unload items in bank request sent.")

    def _on_storage_close(self, code, error):
        if error:
            return self.finish(code, f"Bank close failed with error : {error}")
        self._logger.info("Bank storage closed")
        
        if self.return_to_start:
            self._logger.info(f"Returning to start point")
            self.travel_using_zaap(self._start_map_id, dstZoneId=self._start_zone, callback=self.finish)
        else:
            self.finish(0, None)

    def _on_inventory_weight_update(self, event, lastWeight, weight, max):
        self._logger.info(f"Inventory Weight percent changed to : {round(100 * weight / max, 1)}%")
        if self.leave_bank_open:
            return self.finish(0, None)
        self.close_dialog(self._on_storage_close)