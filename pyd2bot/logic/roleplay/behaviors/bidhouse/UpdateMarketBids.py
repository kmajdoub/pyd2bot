from enum import Enum
from typing import Optional

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

class UpdateMarketBids(AbstractBehavior):
    """Updates multiple old listings to stay competitive"""
    
    MIN_UPDATE_AGE_HOURS = 3
    DEFAULT_MIN_PRICE_RATIO = 0.25 
    
    class ERROR_CODES(Enum):
        OBJECT_NOT_FOUND = 999999901
        INVALID_ITEMS = 999999902
        PRICE_ERROR = 999999903
        MARKET_ERROR = 999999904
    
    def __init__(self, market_type, min_update_age_hours: float = MIN_UPDATE_AGE_HOURS,
                 min_price_ratio: float = DEFAULT_MIN_PRICE_RATIO):
        super().__init__()
        self._logger = Logger()
        
        # Validate and filter items
        self.min_update_age_hours = min_update_age_hours
        self.min_price_ratio = min_price_ratio
        self._market_type = market_type
        self._market_frame = Kernel().marketFrame
        self._bids_manager = self._market_frame._bids_manager
        self._bids_to_update = None
        self._current_bid = None

    def run(self) -> bool:
        self.open_market(from_type=self._market_type, mode="sell", callback=self._on_market_open)

    def _on_market_open(self, code: int, error: Optional[str]) -> None:
        if error:
            return self.finish(code, f"Failed to open market: {error}")
        self._bids_to_update = self._bids_manager.get_all_updatable_bids(self.min_update_age_hours)
        self._check_bids_can_update()
    
    def _check_bids_can_update(self):
        if not self._bids_to_update:
            return self.close_market(lambda *_: self.finish(0))
        self._current_bid = self._bids_to_update.pop(0)
        Kernel().marketFrame.check_price(self._current_bid.item_gid, lambda *_: self._on_price_infos())
        
    def _on_price_infos(self):
        target_price, error = self._bids_manager.get_sell_price(self._current_bid.item_gid, self._current_bid.quantity, self.min_price_ratio)
        
        if error:
            self._logger.warning(f"Cannot get sell price for bid {self._current_bid.uid}: {error}")
            return self._check_bids_can_update()
        
        self.edit_bid_price(self._current_bid, target_price, self._on_update_complete)

    def _on_update_complete(self, code: int, error: Optional[str]) -> None:
        if error:
            self._logger.error(
                f"[{code}] Update failed for bid {self._current_bid.uid}: {error}"
            )
        return self._check_bids_can_update()
