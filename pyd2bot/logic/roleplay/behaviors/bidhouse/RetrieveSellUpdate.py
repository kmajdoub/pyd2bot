from typing import Dict, List, Optional
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.bank.RetrieveFromBank import RetrieveFromBank
from pyd2bot.logic.roleplay.behaviors.bidhouse.SellItemsFromBag import SellItemsFromBag
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.types.enums.ItemCategoryEnum import ItemCategoryEnum
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class RetrieveSellUpdate(AbstractBehavior):

    def __init__(self, gid_batch_size: Dict[int, int] = None, type_batch_size: Dict[int, int] = None, items_gid_to_keep: List[int] = None):
        super().__init__()
        self._logger = Logger()
        self.gid_batch_size = gid_batch_size
        self.type_batch_size = type_batch_size
        self.has_remaining = False
        self._finish_code: Optional[int] = None
        self._finish_error: Optional[str] = None
        self.items_gid_to_keep = items_gid_to_keep

    def run(self) -> bool:
        self._start_map_id = PlayedCharacterManager().currentMap.mapId
        self._start_zone = PlayedCharacterManager().currentZoneRp
        if PlayerManager().isBasicAccount():
            Logger().warning("played is not subscribed, max item lvl he can sell is 60")
            self._max_item_level = 60
        else:
            self._max_item_level = 200
        self._start_retrieve_cycle()
        return True

    def _start_retrieve_cycle(self):
        """Start a new cycle of retrieving and selling"""
        self._logger.info(f"Starting new retrieve cycle for item")

        self.retrieve_items_from_bank(
            type_batch_size=self.type_batch_size,
            gid_batch_size=self.gid_batch_size,
            return_to_start=False,
            max_item_level=self._max_item_level,
            callback=self._on_items_retrieved,
        )

    def _on_items_retrieved(self, code, err, has_remaining=None):
        """Handle completion of item retrieval"""
        if err:
            self.finish(code, f"Error retrieving items: {err}")
            return

        if code == RetrieveFromBank.ERROR_CODES.NO_ITEMS_TO_RETRIEVE:
            # No more items in bank - we're done
            self._logger.info("No more items in bank - updating market bids")
            return self.update_market_bids(ItemCategoryEnum.RESOURCES_CATEGORY, self._handle_finish)

        self.has_remaining = has_remaining

        # Start selling what we retrieved
        self.sell_items(
            gid_batch_size=self.gid_batch_size,
            type_batch_size=self.type_batch_size,
            callback=self._on_items_sold,
        )

    def _on_items_sold(self, code, error):
        """Handle completion of market sale"""
        if error:
            if code == SellItemsFromBag.ERROR_CODES.NO_MORE_SELL_SLOTS:
                return self.update_market_bids(ItemCategoryEnum.RESOURCES_CATEGORY, self._handle_finish)
            self._handle_finish(code, error)
            return

        # Check if we still have items in inventory
        if not self.has_remaining:
            self._logger.info("No more items in bank - updating market bids")
            return self.update_market_bids(ItemCategoryEnum.RESOURCES_CATEGORY, self._handle_finish)

        self._start_retrieve_cycle()

    def _handle_finish(self, code: Optional[int] = None, error: Optional[str] = None):
        """Store finish parameters and unload bank before completing"""
        self._finish_code = code
        self._finish_error = error
        
        # Unload in bank before finishing
        self.unload_in_bank(
            return_to_start=False,
            items_gid_to_keep=self.items_gid_to_keep,
            callback=self._on_storage_open
        )
        
    def has_items_in_bag(self):
        bag_items = InventoryManager().inventory.getView("storage").content
        for item in bag_items:
            if not item.linked:
                return True
        return False
    
    def _on_storage_open(self, code: int, error: Optional[str]) -> None:
        """Final callback after unloading bank"""
        if error:
            self._logger.warning(f"Error unloading bank: {error}")
        
        # Return to start point before finishing
        self._logger.info(f"Returning to start point")
        self.autoTrip(
            self._start_map_id, 
            dstZoneId=self._start_zone, 
            callback=lambda *_: self.finish(self._finish_code, self._finish_error)
        )