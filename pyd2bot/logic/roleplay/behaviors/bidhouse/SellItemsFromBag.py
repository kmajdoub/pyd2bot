from enum import Enum
from pyd2bot.data.enums import ServerNotificationEnum
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent

from typing import Optional, Set, List, Tuple
from collections import deque

from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

class SellItemsFromBag(AbstractBehavior):
    """Sells multiple items from inventory in batches at competitive prices"""    
    MIN_PRICE_RATIO = 0.5 # Minimum acceptable price vs market average
    
    # Server response sequence for a sale
    REQUIRED_SEQUENCE = {
        "quantity",  # Inventory quantity update
        "kamas",     # Kamas update after tax
        "add",       # Listing confirmation
        "weight"     # Inventory weight update
    }

    class ERROR_CODES(Enum):
        NO_MORE_SELL_SLOTS = 98754343
        INSUFFICIENT_KAMAS = 98754344
        INSUFFICIENT_QUANTITY = 98754345
        

    def __init__(self, items_to_sell: List[Tuple[int, int]]):
        """
        Initialize with list of items to sell
        Args:
            items_to_sell: List of tuples (object_gid, quantity)
        """
        self._sell_queue = deque(items_to_sell)
        first_item = items_to_sell[0]
        super().__init__(first_item[0], first_item[1])
        self._quantity_in_inventory = 0
        self._received_sequence: Set[str] = set()

    def run(self) -> bool:
        """Start selling process for first item"""
        self._market_frame = Kernel().marketFrame
        self.on(KernelEvent.ServerTextInfo, self._on_server_notif)
        self._process_next_item()

    @property
    def bids_manager(self):
        return self._market_frame._bids_manager

    def _process_next_item(self) -> bool:
        """Prepare and start selling the next item in queue"""
        if not self._sell_queue:
            Logger().info("All items sold successfully")
            return self.finish(0)

        if not self._validate_next_item():
            return self._process_next_item()

        # Open market using the new abstracted method
        Logger().info(f"Opening market for item {self.object_gid}")
        self.open_market(
            from_gid=self.object_gid,
            callback=self._on_market_open
        )

    def _on_market_open(self, code: int, error: str) -> None:
        """Handle marketplace interface opened"""
        if error:
            return self.finish(code, error)
        self._market_frame.switch_mode("sell", self._handle_sell_mode)

    def _handle_sell_mode(self, event, mode) -> None:
        Logger().info("Market open - starting searching for item in bidhouse")
        self._market_frame.search_item(self.object_gid, self._handle_search_msg)

    def _handle_search_msg(self, event, msg) -> None:
        """Get current prices"""
        Logger().info("Received price search result")
        self._market_frame.check_price(self.object_gid, self._on_price_info)

    def _skip_current_item(self):
        """Skip current item and process next if available"""
        self._sell_queue.popleft()
        if self._sell_queue:
            self.object_gid, self.quantity = self._sell_queue[0]
            self._market_frame.check_price(self.object_gid, self._on_price_info)
        else:
            self._on_idle()
        
    def _on_price_info(self, event, msg) -> None:
        """Got prices - attempt sale if profitable and valid"""
        target_price, error = self.bids_manager.get_sell_price(
            self.object_gid, 
            self.quantity,
            self.MIN_PRICE_RATIO
        )
        
        if error:
            Logger().warning(f"Price error for {self.object_gid}: {error}")
            self._skip_current_item()
            return

        # Validate all conditions before selling
        code, error = self._validate_sale_conditions(target_price)
        if error:
            Logger().warning(f"Sale validation failed with error [{code}]: {error}")
            if code in [self.ERROR_CODES.INSUFFICIENT_KAMAS, self.ERROR_CODES.NO_MORE_SELL_SLOTS]:
                self.finish(code, error)
            else:
                self._skip_current_item()
            return
                
        # All validations passed - proceed with sale
        Logger().info(f"Selling {self.quantity}x {self.object_gid} at {target_price}")
        self.place_bid(self.object_gid, self.quantity, target_price, self._on_item_sold)

    def _validate_sale_conditions(self, target_price: int) -> Tuple[bool, Optional[str]]:
        """
        Validate all conditions before attempting a sale
        Args:
            target_price: Price to list item at
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check remaining sell slots
        if self.bids_manager.get_remaining_sell_slots() <= 0:
            return self.ERROR_CODES.NO_MORE_SELL_SLOTS, "No more sell slots available"
            
        # Recheck inventory quantity (could have changed)
        self._item = self.get_item_from_inventory(self.object_gid)
        if not self._item:
            return self.ERROR_CODES.INSUFFICIENT_QUANTITY, f"Item {self.object_gid} no longer in inventory"
            
        if self._item.quantity < self.quantity:
            return self.ERROR_CODES.INSUFFICIENT_QUANTITY, f"Insufficient quantity: need {self.quantity}, have {self._item.quantity}"
            
        # Check if we can afford tax
        tax = self.bids_manager.calculate_tax(target_price)
        if PlayedCharacterManager().characteristics.kamas < tax:
            return self.ERROR_CODES.INSUFFICIENT_KAMAS, f"Insufficient kamas to pay listing tax ({tax} required)"
            
        return True, None
    
    def get_item_from_inventory(self, object_gid: int) -> Optional[ItemWrapper]:
        """Get item wrapper from inventory by GID"""
        if object_gid in ItemWrapper._cacheGId:
            return ItemWrapper._cacheGId[object_gid]

        return InventoryManager().inventory.getFirstItemByGID(object_gid)

    def _validate_next_item(self) -> bool:
        """
        Validate next item in queue and prepare it for selling
        Returns: True if item is valid and ready to sell, False otherwise
        """
        if not self._sell_queue:
            return False
            
        self.object_gid, self.quantity = self._sell_queue[0]
        
        # Get item and validate quantity
        self._item = self.get_item_from_inventory(self.object_gid)
        if not self._item:
            Logger().warning(f"Item {self.object_gid} not found in inventory, skipping...")
            self._sell_queue.popleft()
            return False
        
        self.item_category = self._item.category
        self._quantity_in_inventory = self._item.quantity
        if self._quantity_in_inventory < self.quantity:
            Logger().warning(
                f"Need {self.quantity} of {self.object_gid}, only have {self._quantity_in_inventory}, skipping..."
            )
            self._sell_queue.popleft()
            return False
            
        return True

    def _on_item_sold(self):
        """Handle successful item sale and determine next action"""
        current_gid = self.object_gid
        
        self._item = self.get_item_from_inventory(self.object_gid)
        self._quantity_in_inventory = self._item.quantity
        
        if self._quantity_in_inventory >= self.quantity:
            if self.bids_manager.get_remaining_sell_slots() > 0:           
                # Continue selling current item
                Logger().info(f"Continuing to sell {self.quantity}x {current_gid}")
                self._market_frame.check_price()
                return
            else:
                self.finish(self.ERROR_CODES.NO_MORE_SELL_SLOTS, "There is no more sell slots")
                return
        # Current item batch complete
        Logger().info(f"Finished selling item {current_gid}")
        self._sell_queue.popleft()
        
        while self._sell_queue and not self._validate_next_item():
            # Keep trying until we find a valid item or run out of items
            pass
            
        if self._sell_queue:
            Logger().info(f"Moving to next item {self.object_gid}, {len(self._sell_queue)} items remaining")
            self._market_frame.check_price(self.object_gid, self._on_price_info)
        else:
            Logger().info("All items sold successfully")
            self._on_idle()

    def _on_idle(self):
        """Clean completion of selling process"""
        self.finish(0)

    def _on_server_notif(self, event, msgId, msgType, textId, msgContent, params):
        if textId == ServerNotificationEnum.CANT_SELL_ANYMORE_ITEMS:
            self.finish(self.ERROR_CODES.NO_MORE_SELL_SLOTS, "There is no more sell slots")
    
    def finish(self, code, error=None):
        def _on_market_close(code_, error_):
            if error_:
                Logger().error(f"Market close failed with error [{code_}] {error_}")
            super().finish(code, error)
        self.close_market(_on_market_close)

    def _can_afford_tax(self, price: int) -> bool:
        """Check if player can afford listing tax"""
        tax = self.bids_manager.calculate_tax(price)
        return PlayedCharacterManager().characteristics.kamas >= tax