from enum import Enum
from typing import Dict, List, Optional, Tuple
from pyd2bot.data.enums import ServerNotificationEnum
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.uiApi.PlayedCharacterApi import PlayedCharacterApi
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class RetrieveFromBank(AbstractBehavior):
    BANK_CLOSE_TIMEOUT = 89987
    RETRIEVE_ITEMS_TIMEOUT = 998877
    
    class ERROR_CODES(Enum):
        NO_ITEMS_TO_RETRIEVE = 87656454
        BANK_CLOSE_ERROR = 87656455
        RETRIEVAL_ERROR = 87656456
        STORAGE_OPEN_ERROR = 87656457
        TRAVEL_ERROR = 87656458
        WAIT_REQUIRED = 87656459

    def __init__(self, type_batch_size: Dict[int, int]=None, gid_batch_size: Dict[int, int]=None, return_to_start=False, bank_infos=None):
        super().__init__()
        self._logger = Logger()
        self._start_map_id = None
        self._start_zone = None
        self._return_to_start = return_to_start
        self.gid_batch_size = gid_batch_size
        self.bank_info = bank_infos
        self._items_uids = []
        self._quantities = []
        self.type_batch_size = type_batch_size
        
    def _safe_finish(self, code: ERROR_CODES, error: Optional[Exception] = None) -> None:
        """Ensures bank is closed before finishing with error"""
        def on_bank_closed(close_code: int, close_error: Optional[Exception]) -> None:
            if close_error:
                self._logger.error(f"Error closing bank: {close_error}")
                # Still finish with original error if there was one
                self.finish(self.ERROR_CODES.BANK_CLOSE_ERROR if not error else code, 
                          close_error if not error else error)
            else:
                self.finish(code, error)

        self._logger.error(f"Operation failed with code {code}: {error if error else 'No error details'}")
        self.close_dialog(on_bank_closed)

    def run(self) -> bool:
        self.characterApi = PlayedCharacterApi()
        self._start_map_id = PlayedCharacterManager().currentMap.mapId
        self._start_zone = PlayedCharacterManager().currentZoneRp
        
        # Register server notification listener
        self.on(KernelEvent.ServerTextInfo, self._on_server_notif)
        
        # Start by unloading in bank without closing it
        self.unload_in_bank(
            bankInfos=self.bank_info, 
            return_to_start=False, 
            leave_bank_open=True,
            callback=self._on_storage_open
        )

    def _on_server_notif(self, event, msgId, msgType, textId, msgContent, params: List[str]) -> None:
        if textId == ServerNotificationEnum.WAIT_REQUIRED:
            try:
                wait_time = int(params[0])
                self._logger.info(f"Server requested wait time of {wait_time} seconds")
                self._retry_retrieval = True
                
                # Schedule retry after wait time
                BenchmarkTimer(
                    wait_time,
                    self._retrieve_items
                ).start()
            except (IndexError, ValueError) as e:
                self._logger.error(f"Error parsing wait time from params {params}: {e}")
                self._safe_finish(self.ERROR_CODES.WAIT_REQUIRED, f"Invalid wait time parameters: {params}")

    def filter_item(self, item_stack: ItemWrapper):
        if self.type_batch_size:
            return item_stack.typeId in self.type_batch_size and item_stack.quantity >= self.type_batch_size[item_stack.typeId]
        elif self.gid_batch_size:
            return item_stack.objectGID in self.gid_batch_size and item_stack.quantity>= self.gid_batch_size[item_stack.objectGID]
        else:
            return True

    def _find_items_to_retrieve(self) -> List[Tuple[int, int]]:
        self._has_remaining = False
        self.items_to_retrieve = list[tuple[int, int]]()
        bank_item_stacks = InventoryManager().bankInventory.getView("bank").content
        candidate_item_stacks = [item for item in bank_item_stacks if not item.linked and self.filter_item(item)]
        # Sort by value density (price/weight) in descending order
        candidate_item_stacks.sort(key=lambda item: Kernel().averagePricesFrame.getItemAveragePrice(item.objectGID) / item.weight, reverse=True)
        
        remaining_pods = self.characterApi.inventoryWeightMax() - self.characterApi.inventoryWeight()
        
        for item in candidate_item_stacks:
            if remaining_pods <= 0:
                break
            
            batch_size = self.type_batch_size.get(item.typeId, 100) if self.type_batch_size else self.gid_batch_size.get(item.objectGID, 100)
            available_batches = (item.quantity // batch_size) * batch_size
            
            # Calculate how many complete batches we can carry
            max_quantity = min(
                item.quantity,  # Don't take more than what's available
                remaining_pods // item.weight  # Don't exceed weight limit
            )
            # Round down to nearest complete batch
            batches_can_carry = (max_quantity // batch_size) * batch_size
            
            if batches_can_carry > 0:
                # If we couldn't carry all available batches, mark as having remainder
                if max_quantity < available_batches:
                   self._has_remaining = True
    
                # Add the item and quantity to our result
                self.items_to_retrieve.append((item.objectUID, batches_can_carry))
                # Update remaining weight capacity
                remaining_pods -= max_quantity * item.weight
                
    def _on_storage_open(self, code: int, err: Optional[Exception]) -> None:
        if err:
            return self._safe_finish(self.ERROR_CODES.STORAGE_OPEN_ERROR, err)

        # Get bank resources and available pods
        self._find_items_to_retrieve()
        # Proceed with retrieval
        self._retrieve_items()
    
    def _retrieve_items(self) -> None:
        """Send item retrieval request with error handling"""
        if not self.items_to_retrieve:
            self._logger.info("No items to retrieve within pod limits")
            return self._safe_finish(self.ERROR_CODES.NO_ITEMS_TO_RETRIEVE)

        items_uids, quantities = zip(*self.items_to_retrieve)
        self.pull_bank_items(items_uids, quantities, lambda: self.close_dialog(self._on_storage_closed))

    def _on_storage_closed(self, code: int, error: Optional[Exception]) -> None:
        if error:
            return self._safe_finish(self.ERROR_CODES.BANK_CLOSE_ERROR, error)
        
        callback = lambda *_: self.finish(0, None, self._has_remaining)
        self._logger.info("Bank storage closed")
        
        if self._return_to_start:
            self._logger.info(f"Returning to start point")
            self.travel_using_zaap(self._start_map_id, self._start_zone, callback=callback)
        else:
            callback()
