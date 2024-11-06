from enum import Enum
from typing import List, Optional, Callable, Tuple
from pyd2bot.data.enums import ServerNotificationEnum
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.bank.CarryOptimizer import ItemInfo, optimize_carry
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
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

    def __init__(self, items_gids: List[int], items_batch_sizes: List[int], return_to_start=False, bank_infos=None):
        super().__init__()
        self._logger = Logger()
        self._start_map_id = None
        self._start_zone = None
        self._return_to_start = return_to_start
        self._item_gids = items_gids
        self.items_batch_sizes = items_batch_sizes
        self.bank_info = bank_infos
        self._items_uids = []
        self._quantities = []
        
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

    @classmethod
    def get_existing_bank_items(cls, items_gids: List[int]) -> dict:
        details = {}
        try:
            resourceItems = InventoryManager().bankInventory.getView("bank").content
            for item in resourceItems:
                if item.objectGID not in items_gids:
                    continue
                if not item.linked:
                    if item.objectGID not in details:
                        details[item.objectGID] = {
                            "totalQuantity": item.quantity,
                            "stackUidList": [item.objectUID],
                            "stackQtyList": [item.quantity],
                            "storageTotalQuantity": item.quantity,
                            "weight": item.weight,
                            "averagePrice": Kernel().averagePricesFrame.getItemAveragePrice(item.objectGID)
                        }
                    else:
                        details[item.objectGID]["totalQuantity"] += item.quantity
                        details[item.objectGID]["stackUidList"].append(item.objectUID)
                        details[item.objectGID]["stackQtyList"].append(item.quantity)
                        details[item.objectGID]["storageTotalQuantity"] += item.quantity
        except Exception as e:
            Logger().error(f"Error getting bank items: {e}")
            raise
        return details

    def _on_storage_open(self, code: int, err: Optional[Exception]) -> None:
        if err:
            return self._safe_finish(self.ERROR_CODES.STORAGE_OPEN_ERROR, err)
        
        try:
            # Get bank resources and available pods
            bank_resources = self.get_existing_bank_items(self._item_gids)
            available_player_pods = self.characterApi.inventoryWeightMax() - self.characterApi.inventoryWeight()
            
            if not bank_resources:
                self._logger.info("There are no items to retrieve from bank")
                return self._safe_finish(self.ERROR_CODES.NO_ITEMS_TO_RETRIEVE)

            # Convert bank resources to ItemInfo objects
            items_info = {}
            for gid, details in bank_resources.items():
                items_info[gid] = ItemInfo(
                    gid=gid,
                    weight=details["weight"],
                    market_value=details["averagePrice"],
                    stack_uids=details["stackUidList"],
                    stack_quantities=details["stackQtyList"],
                    batch_size=self.items_batch_sizes[self._item_gids.index(gid)] if gid in self._item_gids else 1
                )
                
            # Calculate optimal retrieval plan
            self._items_uids, self._quantities = optimize_carry(items_info, available_player_pods)
            
            # Proceed with retrieval
            self._retrieve_items()
            
        except Exception as e:
            self._safe_finish(self.ERROR_CODES.RETRIEVAL_ERROR, e)
    
    def _retrieve_items(self) -> None:
        """Send item retrieval request with error handling"""
        try:
            if not self._items_uids or not self._quantities:
                self._logger.info("No items to retrieve within pod limits")
                return self._safe_finish(self.ERROR_CODES.NO_ITEMS_TO_RETRIEVE)

            self.once(
                KernelEvent.InventoryWeightUpdate, 
                self._on_inventory_weight_changed
            )
            
            self._logger.debug(f"Retrieving items: UIDs={self._items_uids}, Quantities={self._quantities}")
            Kernel().exchangeManagementFrame.exchangeObjectTransferListWithQuantityToInv(
                self._items_uids,
                self._quantities
            )
        except Exception as e:
            self._safe_finish(self.ERROR_CODES.RETRIEVAL_ERROR, e)

    def _on_inventory_weight_changed(self, event: KernelEvent, last_weight: int, new_weight: int, max_weight: int) -> None:
        self._logger.info(f"Inventory weight percent changed to : {round(100 * new_weight / max_weight, 1)}%")
        self.close_dialog(self._on_storage_closed)

    def _on_storage_closed(self, code: int, error: Optional[Exception]) -> None:
        if error:
            return self._safe_finish(self.ERROR_CODES.BANK_CLOSE_ERROR, error)
            
        self._logger.info("Bank storage closed")
        
        if self._return_to_start:
            self._logger.info(f"Returning to start point")
            try:
                self.travel_using_zaap(self._start_map_id, self._start_zone, callback=self.finish)
            except Exception as e:
                self.finish(self.ERROR_CODES.TRAVEL_ERROR, e)
        else:
            self.finish(0, None, self._items_uids, self._quantities)
