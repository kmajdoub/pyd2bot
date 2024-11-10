from collections import defaultdict
from enum import Enum
from typing import Dict, List, Optional
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.data.enums import ServerNotificationEnum


class SellItemsFromBag(AbstractBehavior):
    MIN_PRICE_RATIO = 0.5  # Minimum acceptable price vs market average
    
    class ERROR_CODES(Enum):
        MISSING_INPUTS = 98754342
        NO_MORE_SELL_SLOTS = 98754343
        INSUFFICIENT_KAMAS = 98754344
        INSUFFICIENT_QUANTITY = 98754345
        ITEMS_NOT_FOUND = 98754346

    def __init__(self, gid_batch_size: Dict[int, int] = None, type_batch_size: Dict[int, int] = None):
        super().__init__()
        self.items_uids = list[int]()
        self.gid_batch_size = gid_batch_size
        self.type_batch_size = type_batch_size
        self._current_idx = 0
        self._market_frame = Kernel().marketFrame
        self.markets_excluded_for_items = defaultdict(list)
        self._tried_reopen_market = False
        
    def run(self) -> None:
        self._current_idx = 0
        self.items_uids = list[int]()
        
        if not self.gid_batch_size and not self.type_batch_size:
            return self._handle_error(self.ERROR_CODES.MISSING_INPUTS, "You need to provide either by type or gid the batch sizes")

        if not self._check_inventory():
            return
        
        self.on(KernelEvent.ServerTextInfo, self._on_server_notif)
        self._process_current_item()
    
    def get_item_batch_size(self, item: ItemWrapper):
        if self.gid_batch_size:
            return self.gid_batch_size[item.objectGID]
        elif self.type_batch_size:
            return self.type_batch_size[item.typeId]
        return 100

    def _check_inventory(self):
        self.items_uids = list[int]()
        inventory_items = InventoryManager().inventory.getView("storage").content
        for item in inventory_items:
            if (self.type_batch_size and item.typeId in self.type_batch_size) or \
                (self.gid_batch_size and item.objectGID in self.gid_batch_size):
                    self.items_uids.append(item.objectUID)
        
        if not self.items_uids:
            self.finish(self.ERROR_CODES.ITEMS_NOT_FOUND, "No item found in inventory to sell!")
            return False

        Logger().debug(f"Found items to sell : {self.items_uids}")
        return True

    def _process_current_item(self) -> None:
        if self._current_idx >= len(self.items_uids):
            return self._ensure_market_closed(lambda: self.finish(0))
        
        item = self.current_item
    
        Logger().info(f"Processing {item.name} (gid={item.objectGID}, uid={item.objectUID}) x{item.quantity}")

        if not self._check_market_level():
            return

        self._ensure_market_open()

    def _ensure_market_open(self):
        item = self.current_item
        
        if self._market_frame._market_type_open == item.category:
            return self._on_market_open(0, None)
            
        self.open_market(
            from_type=item.category,
            exclude_market_at_maps=self.markets_excluded_for_items[item.objectGID],
            item_level=item.level,
            callback=self._on_market_open
        )
    
    def _check_market_level(self):        
        market_max_lvl = self._market_frame._bids_manager.max_item_level
        if market_max_lvl is None: # Market is not open yet
            return True
        if market_max_lvl < self.current_item.level:
            self.markets_excluded_for_items[self.current_item.objectGID].append(PlayedCharacterManager().currVertex.mapId)
            Logger().warning(f"Item has higher level {self.current_item.level}, than market max lvl {market_max_lvl}, trying to find another market ...")
            self.close_market(lambda *_: self._process_current_item())
            return False
        return True

    def _on_market_open(self, code: int, error: Optional[str]) -> None:
        if error:
            return self._handle_error(code, error)
        
        Logger().debug("Market is open now")
        self._ensure_sell_mode()

    def _ensure_sell_mode(self):
        if self._market_frame._current_mode == "sell":
            return self._on_sell_mode(None, None)

        self._market_frame.switch_mode("sell", self._on_sell_mode)

    def _on_sell_mode(self, event, mode) -> None:
        if not self._check_market_level():
            return
        
        self._market_frame.search_item(self.current_item.objectGID, self._on_search_result)

    def _on_search_result(self, code, error):
        if error:
            Logger().error(f"Error searching for item [{code}] : {error}")
            if code == 2222 and not self._tried_reopen_market: # timeout and didnt try solution of reopen the market
                self._tried_reopen_market = True
                self.close_market(lambda *_: self._process_current_item())
                return
            self._current_idx += 1
            self._process_current_item()
            return
        self._tried_reopen_market = False # clear this if no problem happened
        item = self.current_item
        if item:
            self._market_frame.check_price(item.objectGID, self._on_price_info)

    @property
    def current_item(self) -> ItemWrapper:
        if self._current_idx >= len(self.items_uids):
            return self._handle_error(1, f"{self._current_idx} is bigger than available list of items {len(self.items_uids)}!!")

        itemSet = InventoryManager().inventory.getItem(self.items_uids[self._current_idx])
        if itemSet:
            return itemSet.item
        return None


    def _on_price_info(self, event, msg) -> None:
        item = self.current_item
        qty = self.get_item_batch_size(item)

        # Get price with ratio validation
        target_price, error = self._market_frame._bids_manager.get_sell_price(
            item.objectGID, qty, self.MIN_PRICE_RATIO
        )
        
        if error:
            Logger().warning(f"Error while calculating best price for item {item.objectGID}: {error}")
            self._current_idx += 1
            return self._process_current_item()

        # Validate before selling, dont depend on the item but on the tax and the available slots
        if not self._validate_sale(target_price):
            return
            
        Logger().info(f"Placing the bid {item.objectGID} x{qty} at {target_price}")

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
            Logger().error(f"Couldn't open a market for item : {self.current_item.name} (gid={self.current_item.objectGID}, level={self.current_item.level}")
            self._current_idx += 1
            return self._process_current_item()

        if self._market_frame._bids_manager.get_remaining_sell_slots() <= 0:
            self._handle_error(self.ERROR_CODES.NO_MORE_SELL_SLOTS, "No sell slots")
            return False

        item = self.current_item
        if item:
            qty = self.get_item_batch_size(item)
            if item.quantity >= qty:
                Logger().info(f"Continuing to sell {item.objectGID} x{qty}")
                return self._market_frame.check_price(item.objectGID, self._on_price_info)
    
        Logger().info(f"No more instances to sell, Moving to next item")
        self._current_idx += 1
        self._process_current_item()

    def _on_server_notif(self, event, msgId, msgType, textId, msgContent, params):
        if textId == ServerNotificationEnum.CANT_SELL_ANYMORE_ITEMS:
            self._handle_error(self.ERROR_CODES.NO_MORE_SELL_SLOTS, "No sell slots")
            
    def _ensure_market_closed(self, callback) -> None:
        self.close_market(lambda *_: callback())
        
    def _handle_error(self, code: Optional[int], error: Optional[str]) -> None:
        Logger().warning(f"Error encountered [{code}]: {error}")
        self._ensure_market_closed(lambda: self.finish(code, error))
