from enum import Enum
from typing import List, Optional
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.datacenter.items.Item import Item
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.data.enums import ServerNotificationEnum


class SellItemsFromBag(AbstractBehavior):
    MIN_PRICE_RATIO = 0.5  # Minimum acceptable price vs market average
    
    class ERROR_CODES(Enum):
        NO_MORE_SELL_SLOTS = 98754343
        INSUFFICIENT_KAMAS = 98754344
        INSUFFICIENT_QUANTITY = 98754345

    def __init__(self, items_to_sell: List[int], items_batch_sizes: List[int]):
        super().__init__()
        self._logger = Logger()
        self._items_to_sell = items_to_sell
        self._items_batch_sizes = items_batch_sizes
        self._current_idx = 0
        self._market_frame = Kernel().marketFrame
        self._items = list[tuple[ItemWrapper, int]]()
        
    def run(self) -> None:
        if not self._check_inventory():
            return
        
        self.on(KernelEvent.ServerTextInfo, self._on_server_notif)
        self._process_current_item()
    
    def _check_inventory(self):
        items_in_inventory = []
        for gid, batch_size in zip(self._items_to_sell, self._items_batch_sizes):
            item = self.get_item_from_inventory(gid)
            if item and item.quantity >= batch_size:
                items_in_inventory.append((item, batch_size))
        if not items_in_inventory:
            self.finish(1, "No item found in inventory from items to sell!")
            return None
        self._items = items_in_inventory
        return items_in_inventory

    def _process_current_item(self) -> None:
        if self._current_idx >= len(self._items):
            return self._ensure_market_closed(lambda: self.finish(0))
        
        item, qty = self._items[self._current_idx]
    
        self._logger.info(f"Processing {item.name}({item.objectGID}) x{qty}")

        if self._market_frame._market_type_open == item.category:
            return self._on_market_open(0, None)
        
        self.open_market(
            from_type=item.category,
            callback=self._on_market_open
        )

    def _on_market_open(self, code: int, error: Optional[str]) -> None:
        if error:
            return self._handle_error(code, error)

        if self._market_frame._current_mode == "sell":
            return self._handle_sell_mode(None, None)

        self._market_frame.switch_mode("sell", self._handle_sell_mode)
    
    @property
    def current_item(self) -> ItemWrapper:
        return self._items[self._current_idx][0]

    def _handle_sell_mode(self, event, mode) -> None:
        gid = self.current_item.objectGID
        self._market_frame.search_item(gid, lambda *_: self._market_frame.check_price(gid, self._on_price_info))
            
    def _on_price_info(self, event, msg) -> None:
        item, qty = self._items[self._current_idx]

        # Get price with ratio validation
        target_price, error = self._market_frame._bids_manager.get_sell_price(
            item.objectGID, qty, self.MIN_PRICE_RATIO
        )
        
        if error:
            self._logger.warning(f"Error while calculating best price for item {item.objectGID}: {error}")
            self._current_idx += 1
            return self._process_current_item()

        # Validate before selling
        if not self._validate_sale(target_price):
            return
            
        self._logger.info(f"Listing {item.objectGID} x{qty} at {target_price}")
        self.place_bid(item.objectUID, qty, target_price, self._on_bid_placed)

    def _validate_sale(self, price: int) -> bool:
        if self._market_frame._bids_manager.get_remaining_sell_slots() <= 0:
            self._handle_error(self.ERROR_CODES.NO_MORE_SELL_SLOTS, "No sell slots")
            return False
            
        tax = self._market_frame._bids_manager.calculate_tax(price)
        if PlayedCharacterManager().characteristics.kamas < tax:
            self._handle_error(self.ERROR_CODES.INSUFFICIENT_KAMAS, f"Need {tax} kamas for tax")
            return False
            
        return True
        
    def _on_bid_placed(self, code: Optional[int], error: Optional[str]) -> None:
        if error:
            return self._handle_error(code, error)

        # Check if we should continue selling same item
        item, qty = self._items[self._current_idx]
        item = self.get_item_from_inventory(item.objectGID)
        
        if item and item.quantity >= qty and self._market_frame._bids_manager.get_remaining_sell_slots() > 0:
            self._logger.info(f"Continuing to sell {item.objectGID} x{qty}")
            return self._market_frame.check_price(item.objectGID, self._on_price_info)
        
        self._logger.info(f"No more instances to sell, Moving to next item")
        self._current_idx += 1
        self._process_current_item()

    def _on_server_notif(self, event, msgId, msgType, textId, msgContent, params):
        if textId == ServerNotificationEnum.CANT_SELL_ANYMORE_ITEMS:
            self._handle_error(self.ERROR_CODES.NO_MORE_SELL_SLOTS, "No sell slots")
            
    def _ensure_market_closed(self, callback) -> None:
        self.close_market(lambda *_: callback())
        
    def _handle_error(self, code: Optional[int], error: Optional[str]) -> None:
        self._logger.warning(f"Error encountered [{code}]: {error}")
        self._ensure_market_closed(lambda: self.finish(code, error))
        
    def get_item_from_inventory(self, gid: int):
        return InventoryManager().inventory.getFirstItemByGID(gid)