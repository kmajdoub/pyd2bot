from enum import Enum, auto
from typing import Dict, List, Optional, Tuple
from pyd2bot.data.enums import ServerNotificationEnum
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.bank.scoring import MarketScorer
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.internalDatacenter.DataEnum import DataEnum
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.types.enums.ItemCategoryEnum import ItemCategoryEnum
from pydofus2.com.ankamagames.dofus.uiApi.PlayedCharacterApi import PlayedCharacterApi
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class RetrieveFromBank(AbstractBehavior):

    class ERROR_CODES(Enum):
        NO_ITEMS_TO_RETRIEVE = auto()
        BANK_CLOSE_ERROR = auto()
        RETRIEVAL_ERROR = auto()
        STORAGE_OPEN_ERROR = auto()
        TRAVEL_ERROR = auto()
        WAIT_REQUIRED = auto()
    
    MIN_STACK_VALUE_TO_CONSIDER = 1500

    def __init__(
        self,
        type_batch_size: Dict[int, int] = None,
        gid_batch_size: Dict[int, int] = None,
        return_to_start=False,
        bank_infos=None,
        item_max_level=200,
    ):
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
        self.item_max_level = item_max_level
        self.scorer = MarketScorer()

    def _safe_finish(self, code: ERROR_CODES, error: Optional[Exception] = None) -> None:
        """Ensures bank is closed before finishing with error"""

        def on_bank_closed(close_code: int, close_error: Optional[Exception]) -> None:
            if close_error:
                self._logger.error(f"Error closing bank: {close_error}")
                # Still finish with original error if there was one
                self.finish(
                    self.ERROR_CODES.BANK_CLOSE_ERROR if not error else code, close_error if not error else error
                )
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
            bankInfos=self.bank_info, return_to_start=False, leave_bank_open=True, callback=self._on_storage_open
        )

    def _on_server_notif(self, event, msgId, msgType, textId, msgContent, params: List[str]) -> None:
        if textId == ServerNotificationEnum.WAIT_REQUIRED:
            try:
                wait_time = int(params[0])
                self._logger.info(f"Server requested wait time of {wait_time} seconds")
                self._retry_retrieval = True

                # Schedule retry after wait time
                BenchmarkTimer(wait_time, self._retrieve_items).start()
            except (IndexError, ValueError) as e:
                self._logger.error(f"Error parsing wait time from params {params}: {e}")
                self._safe_finish(self.ERROR_CODES.WAIT_REQUIRED, f"Invalid wait time parameters: {params}")

    def _find_items_to_retrieve2(
        self,
    ) -> List[Tuple[int, int]]:
        max_pods = self.characterApi.inventoryWeightMax() - self.characterApi.inventoryWeight()
        bank_items = InventoryManager().bankInventory.getView("bank").content
        candidates = list()
        self._has_remaining = False

        for item in bank_items:
            avg_price = Kernel().averagePricesFrame.getItemAveragePrice(item.objectGID)
            
            if (
                item.linked
                or item.category != ItemCategoryEnum.RESOURCES_CATEGORY
                or item.typeId == DataEnum.RUNE_TYPE_ID
                or not avg_price
            ):
                continue

            for batch_size in [1, 10, 100]:
                if batch_size > item.quantity:
                    continue
                
                if avg_price * batch_size < self.MIN_STACK_VALUE_TO_CONSIDER:
                    continue

                score = self.scorer.score(PlayerManager().server.id, item.objectGID, batch_size)
                candidates.append({"item": item, "batch_size": batch_size, "score": score})

        # Sort candidates by score
        candidates.sort(key=lambda x: x["score"], reverse=True)

        # Take items until we run out of pods
        remaining_pods = max_pods
        combined_quantities = {}

        for candidate in candidates:
            if remaining_pods <= 0:
                break

            item: ItemWrapper = candidate["item"]
            batch_size = candidate["batch_size"]

            # Calculate how many complete batches we can carry
            # Handle items with zero weight
            if item.weight == 0:
                quantity = (item.quantity // batch_size) * batch_size
                if quantity > 0:
                    # Add to combined quantities
                    current_quantity = combined_quantities.get(item.objectUID, 0)
                    combined_quantities[item.objectUID] = current_quantity + quantity
            else:
                # Calculate how many complete batches we can carry
                max_batches = min(
                    item.quantity // batch_size,  # Complete batches available
                    remaining_pods // (item.weight * batch_size),  # Complete batches we can carry
                )

                if max_batches > 0:
                    quantity = max_batches * batch_size
                    weight = quantity * item.weight

                    if quantity < (item.quantity // batch_size) * batch_size:
                        self._has_remaining = True

                    current_quantity = combined_quantities.get(item.objectUID, 0)
                    combined_quantities[item.objectUID] = current_quantity + quantity
                    remaining_pods -= weight

        # Convert combined quantities to list of tuples
        self.items_to_retrieve = [(uid, quantity) for uid, quantity in combined_quantities.items()]

    def _on_storage_open(self, code: int, err: Optional[Exception]) -> None:
        if err:
            return self._safe_finish(self.ERROR_CODES.STORAGE_OPEN_ERROR, err)

        # Get bank resources and available pods
        self._find_items_to_retrieve2()

        # Proceed with retrieval
        self._retrieve_items()

    def _retrieve_items(self) -> None:
        """Send item retrieval request with error handling"""
        if not self.items_to_retrieve:
            self._logger.info("No items to retrieve within constraints")
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
