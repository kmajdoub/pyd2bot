from enum import Enum
from typing import List, Optional, Dict
from collections import deque

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.dofus.datacenter.items.Item import Item
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.dofus.types.enums.ItemCategoryEnum import ItemCategoryEnum

class UpdateBidsBehavior(AbstractBehavior):
    """Updates multiple old listings to stay competitive"""
    
    MIN_UPDATE_AGE_HOURS = 0.25  # Only update listings older than this
    DEFAULT_MIN_PRICE_RATIO = 0.20
    
    # Market type mapping from frame
    ITEM_TYPE_TO_MARKETPLACE_GFX_ID = {
        ItemCategoryEnum.RESOURCES_CATEGORY: 226,  # RESOURCES_MARKETPLACE_GFX_ID
    }
    
    class ERROR_CODES(Enum):
        OBJECT_NOT_FOUND = 999999901
        INVALID_ITEMS = 999999902
        PRICE_ERROR = 999999903
        MARKET_ERROR = 999999904
    
    def __init__(self, object_gids: List[int], quantity: int, 
                 min_update_age_hours: float = None,
                 min_price_ratio: float = DEFAULT_MIN_PRICE_RATIO):
        """
        Initialize update behavior
        Args:
            object_gids: List of item GIDs to update listings for
            quantity: Quantity per listing to update
            min_update_age_hours: Minimum age of listings to update
            min_price_ratio: Minimum acceptable price vs market average
        """
        super().__init__()
        self._logger = Logger()
        
        # Validate and filter items
        self._update_queue = deque[Item]()
        self._category_items: Dict[int, List[Item]] = {}
        
        for gid in object_gids:
            item = Item.getItemById(gid, False)
            if item:
                self._update_queue.append(item)
                
                # Group items by category for efficient market access
                if item.category not in self._category_items:
                    self._category_items[item.category] = []
                self._category_items[item.category].append(item)
            else:
                self._logger.warning(f"Invalid item GID: {gid}, skipping")

        if not self._update_queue:
            raise ValueError("No valid items provided")

        # Store configuration
        self.quantity = quantity
        self.min_update_age_hours = min_update_age_hours or self.MIN_UPDATE_AGE_HOURS
        self.min_price_ratio = min_price_ratio
        self._updates_performed = 0
        self.current_item = None
        self._current_category = None
        self._market_frame = Kernel().marketFrame

    @property
    def bids_manager(self):
        return self._market_frame._bids_manager

    def run(self) -> bool:
        """Start the batch update process"""
        if not self._update_queue:
            return self.finish(self.ERROR_CODES.INVALID_ITEMS, "No valid items to process")
            
        return self._process_next_item()

    def _process_next_item(self) -> bool:
        """Process next item in the queue"""
        if not self._update_queue:
            self._logger.info("All items processed")
            return self.finish(0)

        self.current_item = self._update_queue.popleft()
        self._current_category = self.current_item .category
        
        self._logger.info(f"Processing updates for item {self.current_item.id}, category {self._current_category}")
        
        # Make sure the right market is open
        self._ensure_market_open()

    def _ensure_market_open(self) -> bool:
        """Ensure correct market category is open"""
        if self._market_frame._market_type_open != self._current_category:
            self._logger.info(f"Opening market for category {self._current_category}")
            self.open_market(
                from_type=self._current_category,
                callback=self._on_market_open
            )
            return True
        else:
            self._on_market_open(0, None)

    def _on_market_open(self, code: int, error: Optional[str]) -> None:
        """Handle market open completion"""
        if error:
            return self.finish(code, f"Failed to open market: {error}")

        if self._market_frame._current_mode != "sell":
            self._market_frame.switch_mode("sell", self._on_sell_mode)
            return True
        else:
            Logger().info("Market already in sell mode, skipping mode switch")
            self._on_sell_mode(None, None)

    def _on_sell_mode(self, event, mode) -> None:
        """Handle sell mode activation"""
        Kernel().marketFrame.check_price(self.current_item.id, self._on_price_infos)
        
    def _on_price_infos(self, event, msg):
        self._process_next_update()
    
    def _process_next_update(self) -> None:
        """Process next listing that needs update"""
        # Check if we have any listings for this item before proceeding
        current_listings = self.bids_manager.get_bids(self.current_item.id, self.quantity)
        if not current_listings:
            self._logger.info(f"No current listings for item {self.current_item.id}, skipping")
            return self._process_next_item()
        else:
            self._logger.info(f"Found {len(current_listings)} of item '{self.current_item.id}'")
        
        # Check market state
        if self._market_frame._state != "IDLE":
            self._logger.warning("Market not in IDLE state, waiting...")
            return
            
        updatable, target_price, error = self.bids_manager.get_updatable_bids(
            self.current_item.id,
            self.quantity, 
            self.min_update_age_hours,
            self.min_price_ratio
        )
        
        if error:
            self._logger.warning(f"Cannot update price for {self.current_item.id}: {error}")
            return self._process_next_item()
        
        if not updatable:
            self._logger.info(f"No listings need updating for {self.current_item.id}")
            return self._process_next_item()

        # Update next listing
        listing = updatable[0]
        self.update_bid(self.current_item.id, self.quantity, listing.uid, target_price, self._on_update_complete)

    def _on_update_complete(self, code: int, error: Optional[str]) -> None:
        """Handle update completion"""
        if error:
            self._logger.error(
                f"[{code}] Update failed for {self.current_item.id}: {error}"
            )
            return self._process_next_item()

        self._updates_performed += 1

        self._process_next_update()

    def _log_progress(self) -> None:
        """Log current progress"""
        remaining_items = len(self._update_queue)
        self._logger.info(
            f"Progress: {self._updates_performed} updates done, "
            f"{remaining_items} items remaining"
        )