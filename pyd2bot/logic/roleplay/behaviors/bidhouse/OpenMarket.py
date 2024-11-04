from collections import defaultdict
from typing import Optional

from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.types.enums.ItemCategoryEnum import ItemCategoryEnum
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior

class OpenMarket(AbstractBehavior):
    """
    Simple behavior to open a marketplace of specified type.
    Can determine type from item GID or direct category specification.
    """
    
    # Marketplace constants
    RESOURCE_MARKETPLACE_ELEMENT_TYPE_ID = 313
    RESOURCE_MARKET_GFX = 226
    _open_market_type = defaultdict(lambda: None)  # Tracks currently open market type per thread
    
    # Marketplace type mapping
    MARKETPLACE_TYPES = {
        ItemCategoryEnum.RESOURCES_CATEGORY: (RESOURCE_MARKETPLACE_ELEMENT_TYPE_ID, RESOURCE_MARKET_GFX), # (element_id, gfx_id)
    }
    
    # Error codes
    class ERROR_CODES:
        HDV_NOT_FOUND = 7676999,
        UNSUPPORTED_TYPE = 7676990
        MAP_ERROR = 7676991
        ITEM_NOT_FOUND = 77777778

    def __init__(self, from_gid: Optional[int] = None, from_object_category: Optional[int] = None):
        """
        Initialize market opener with either item GID or direct category type
        """
        super().__init__()
        if not from_gid and not from_object_category:
            return self.finish(1, "Must specify either from_gid or from_type")
        
        self.from_gid = from_gid
        self.from_type = from_object_category
        self._market_type = None

    def run(self) -> bool:
        """Start the marketplace opening process"""
        self._market_type = self._determine_market_type()
        if not self._market_type or self._market_type not in self.MARKETPLACE_TYPES:
            return self.finish(
                self.ERROR_CODES.UNSUPPORTED_TYPE,
                f"Unsupported marketplace type: {self._market_type}"
            )

        current_market = Kernel().marketFrame._market_type_open
        if current_market is not None:
            if current_market == self._market_type:
                Logger().warning(f"Market type {self._market_type} is already open, skipping open process")
                return self.finish(0)
            else:
                # Different market is open, need to close it first
                Logger().warning(f"Another market type {current_market} is open, closing before opening {self._market_type}")
                self.close_dialog(self._on_other_market_closed)
                return True

        # Get marketplace GFX ID and start travel
        market_gfx_id = self.MARKETPLACE_TYPES[self._market_type][1]
        self.goto_market(market_gfx_id, callback=self._on_market_map_reached)

    def _determine_market_type(self) -> Optional[int]:
        """
        Determine marketplace type from GID or direct type specification
        Returns: Market category or None if invalid
        """
        if self.from_type is not None:
            return self.from_type
            
        if self.from_gid is not None:
            from pydofus2.com.ankamagames.dofus.datacenter.items.Item import Item
            item = Item.getItemById(self.from_gid)
            if item is not None:
                return item.category
            else:
                return self.finish(self.ERROR_CODES.ITEM_NOT_FOUND, f"Couldn't find item with gid '{self.from_gid}'")
                
        return None

    def _open_marketplace(self) -> None:
        """Open the marketplace interface"""
        Logger().debug("Opening marketplace...")
        
        element = Kernel().interactiveFrame.getIeByTypeId(self.MARKETPLACE_TYPES[self._market_type][0])
        
        if not element:
            return self.finish(
                self.ERROR_CODES.HDV_NOT_FOUND,
                "Marketplace interactive element not found"
            )
                
        self.useSkill(
            ie=element,
            waitForSkillUsed=False,
            callback=self._on_market_open
        )

    def _on_market_map_reached(self, code: int, error: str) -> None:
        """Handle marketplace map reached"""
        if error:
            return self.finish(self.ERROR_CODES.MAP_ERROR, error)
        self._open_marketplace()
    
    def _on_market_open(self, code: int, error: str) -> None:
        """Handle marketplace interface opened"""
        if error:
            return self.finish(code, error)
        Kernel().marketFrame._market_type_open = self._market_type
        self.finish(0)

    def _on_other_market_closed(self, code: int, error: str) -> None:
        """Handle market close closed callback"""
        if error:
            return self.finish(code, f"Close market failed with error [{code}] {error}")
        Kernel().marketFrame._market_type_open = None
        self.goto_market(self.MARKETPLACE_TYPES[self._market_type][1], callback=self._on_market_map_reached)
