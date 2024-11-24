from typing import List, Tuple
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
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

    def run(self, return_to_start=True, bankInfos=None, leave_bank_open=False, items_gid_to_keep=None) -> bool:
        if PlayedCharacterManager().limitedLevel < 10:
            return self.finish(self.LEVEL_TOO_LOW, "Character level is too low to use bank.")
        
        self.return_to_start = return_to_start
        self.leave_bank_open = leave_bank_open
        self._start_map_id = PlayedCharacterManager().currentMap.mapId
        self._start_zone = PlayedCharacterManager().currentZoneRp
        self.items_gid_to_keep = items_gid_to_keep
        
        # Use open_bank helper
        self.open_bank(bankInfos=bankInfos, callback=self._on_bank_opened)
        return True

    def _find_items_to_retrieve(self) -> List[Tuple[int, int]]:
        if not self.items_gid_to_keep:
            return []
            
        items_to_retrieve = []
        bank_item_stacks = InventoryManager().bankInventory.getView("bank").content
        
        for stack in bank_item_stacks:
            if stack.objectGID in self.items_gid_to_keep:
                items_to_retrieve.append((stack.objectUID, stack.quantity))
                
        return items_to_retrieve

    def _on_bank_opened(self, code, error):
        if error:
            return self.finish(code, error)
            
        bag_items = InventoryManager().inventory.getView("storage").content
        has_items_to_transfer = any(not item.linked for item in bag_items)
        
        if not has_items_to_transfer:
            self._logger.info("No items to unload in bank")
            if self.items_gid_to_keep:
                items_to_retrieve = self._find_items_to_retrieve()
                if items_to_retrieve:
                    self.pull_bank_items(
                        [uid for uid, _ in items_to_retrieve],
                        [qty for _, qty in items_to_retrieve],
                        lambda: self.close_dialog(self._on_storage_close) if not self.leave_bank_open else self.finish(0)
                    )
                    return
            
            if self.leave_bank_open:
                return self.finish(0)
            self.close_dialog(self._on_storage_close)
            return
            
        self.once(
            event_id=KernelEvent.InventoryWeightUpdate, 
            callback=self._on_inventory_weight_update, 
            timeout=10,
            retry_nbr=5,
            retry_action=Kernel().exchangeManagementFrame.exchangeObjectTransferAllFromInv,
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
        
        if self.items_gid_to_keep:
            items_to_retrieve = self._find_items_to_retrieve()
            if items_to_retrieve:
                self.pull_bank_items(
                    [uid for uid, _ in items_to_retrieve],
                    [qty for _, qty in items_to_retrieve],
                    lambda: self.close_dialog(self._on_storage_close) if not self.leave_bank_open else self.finish(0, None)
                )
                return
                
        if self.leave_bank_open:
            return self.finish(0, None)
        self.close_dialog(self._on_storage_close)