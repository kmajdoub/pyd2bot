from typing import Optional, Tuple

from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InventoryManager import InventoryManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.npc.NpcGenericActionRequestMessage import NpcGenericActionRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseInListUpdatedMessage import ExchangeBidHouseInListUpdatedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseItemRemoveOkMessage import ExchangeBidHouseItemRemoveOkMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseSearchMessage import ExchangeBidHouseSearchMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHousePriceMessage import ExchangeBidHousePriceMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidPriceForSellerMessage import ExchangeBidPriceForSellerMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeObjectMovePricedMessage import ExchangeObjectMovePricedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeObjectModifyPricedMessage import ExchangeObjectModifyPricedMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeStartedBidSellerMessage import ExchangeStartedBidSellerMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeTypesItemsExchangerDescriptionForUserMessage import ExchangeTypesItemsExchangerDescriptionForUserMessage
from pydofus2.com.ankamagames.dofus.types.enums.ItemCategoryEnum import ItemCategoryEnum
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.bidhouse.MarketState import MarketListing, MarketState
from pyd2bot.misc.Localizer import Localizer

class AbstractMarketBehavior(AbstractBehavior):
    """
    Abstract base class for marketplace behaviors.
    Handles core market functionality using MarketState for state management.
    """
    
    # Marketplace constants
    SELL_MODE_ACTION_ID = 5
    RESOURCE_MARKETPLACE_ELEMENT_TYPE_ID = 313
    RESOURCES_MARKETPLACE_GFX_ID = 226
    
    # Market type mapping
    ITEM_TYPE_TO_MARKETPLACE_GFX_ID = {
        ItemCategoryEnum.RESOURCES_CATEGORY: RESOURCES_MARKETPLACE_GFX_ID,
    }
    
    # Error codes
    ERROR_CODES = {
        "INVALID_QUANTITY": 7676967,
        "OBJECT_NOT_FOUND": 7676966,
        "HDV_NOT_FOUND": 7676999,
        "INSUFFICIENT_KAMAS": 7676968
    }

    # States where we're actively selling/updating
    ACTIVE_STATES = {"SELLING", "UPDATING"}

    def __init__(self, object_gid: int, quantity: int):
        """Initialize market behavior with item and quantity"""
        super().__init__()
        self.object_gid = object_gid
        self.quantity = quantity
        self._state = "INIT"
        self._logger = Logger()
        self._market = MarketState()
        self._item: Optional[ItemWrapper] = None
        self.hdv_vertex = None
        self.path_to_hdv = None
        self.on(KernelEvent.MessageReceived, self._handle_message)

    def _validate_marketplace_access(self) -> bool:
        """
        Validate marketplace accessibility and setup paths
        Returns: bool indicating if access is valid
        """
        if not self._item:
            return self.finish(self.ERROR_CODES["OBJECT_NOT_FOUND"], "Item not found in inventory")
            
        # Get marketplace type for item category
        hdv_gfx_id = self.ITEM_TYPE_TO_MARKETPLACE_GFX_ID.get(self._item.category)
        if not hdv_gfx_id:
            return self.finish(
                self.ERROR_CODES["HDV_NOT_FOUND"], 
                f"Unsupported item category: {self._item.category}"
            )
            
        # Find path to nearest marketplace
        current_map = PlayedCharacterManager().currentMap.mapId
        self.path_to_hdv = Localizer.findClosestHintMapByGfx(current_map, hdv_gfx_id)
        
        if self.path_to_hdv is None:
            return self.finish(
                self.ERROR_CODES["HDV_NOT_FOUND"],
                "No accessible marketplace found"
            )
            
        # Set target vertex
        if len(self.path_to_hdv) == 0:
            self.hdv_vertex = PlayedCharacterManager().currVertex
        else:
            self.hdv_vertex = self.path_to_hdv[-1].dst
            
        return True
    def _travel_to_marketplace(self):
        # Validate market access
        if not self._validate_marketplace_access():
            return False

        # Travel if needed, otherwise start selling
        if self.hdv_vertex != PlayedCharacterManager().currVertex:
            self.travelUsingZaap(
                self.hdv_vertex.mapId, 
                self.hdv_vertex.zoneId,
                callback=self._on_marketplace_map_reached
            )
        else:
            self._on_marketplace_map_reached(None, None)

    def _handle_message(self, event, msg) -> None:
        """
        Central message handler for market operations
        Delegates to appropriate handlers based on message type and state
        """
        try:
            # Handle sell mode initialization first to set up market state
            if isinstance(msg, ExchangeStartedBidSellerMessage):
                if self._state == "SWITCHING_TO_SELL":
                    self._logger.info("Initialize market state with rules from seller descriptor")
                    self._market.init_from_seller_descriptor(msg)
                    self._handle_sell_mode_msg(msg)
                return

            # Handle item type descriptions
            if isinstance(msg, ExchangeTypesItemsExchangerDescriptionForUserMessage):
                self._logger.debug(f"Received item type description for GID {msg.objectGID}")
                if msg.objectGID == self.object_gid:
                    self._market.handle_type_description(msg)
                    self._handle_search_msg(msg)  # Continue the behavior chain
                return
        
            # Price check response - update market state
            if isinstance(msg, ExchangeBidPriceForSellerMessage):
                if msg.genericId == self.object_gid:
                    self._market.handle_price_info(msg)
                    self._handle_price_msg(msg)  # <-- This is key - continue the behavior chain
                return

            # Price updates (process in any state)
            if isinstance(msg, ExchangeBidHouseInListUpdatedMessage):
                if msg.objectGID == self.object_gid:
                    changes = self._market.handle_market_update(msg)
                    if changes:
                        for quantity, old_price, new_price in changes:
                            if quantity == self.quantity:
                                self._on_price_changed(old_price, new_price)
                return

            # Handle removals/sales
            if isinstance(msg, ExchangeBidHouseItemRemoveOkMessage):
                if msg.sellerId == PlayedCharacterManager().id:
                    listing = self._market.handle_listing_remove(msg)
                    if listing:
                        self._on_listing_removed(listing)
                return


            # Let subclasses handle other messages
            self._handle_behavior_specific(msg)
                
        except Exception as e:
            self._logger.error(f"Message handling error: {str(e)}")
            return self.finish(1, f"Market operation failed: {str(e)}")

    def _open_marketplace(self) -> None:
        """Open the marketplace interface"""
        self._logger.debug("Opening marketplace...")
        self._state = "OPENING_HDV"
        
        if self._item.category == ItemCategoryEnum.RESOURCES_CATEGORY:
            element = Kernel().interactiveFrame.getIeByTypeId(
                self.RESOURCE_MARKETPLACE_ELEMENT_TYPE_ID
            )
            if not element:
                return self.finish(
                    self.ERROR_CODES["HDV_NOT_FOUND"], 
                    "Marketplace element not found"
                )
                
            self.useSkill(
                ie=element,
                waitForSkillUsed=False,
                callback=self._on_marketplace_opened
            )
        else:
            return self.finish(
                self.ERROR_CODES["HDV_NOT_FOUND"],
                f"Unsupported marketplace type: {self._item.category}"
            )

    def _enter_sell_mode(self) -> None:
        """Switch to marketplace sell mode"""
        self._state = "SWITCHING_TO_SELL"
        self._logger.debug("Entering sell mode...")
        
        msg = NpcGenericActionRequestMessage()
        msg.init(-1, self.SELL_MODE_ACTION_ID, self.hdv_vertex.mapId)
        ConnectionsHandler().send(msg)

    def _validate_listing(self, price: int) -> Tuple[bool, str]:
        """
        Validate listing parameters against market rules
        Returns: (is_valid, error_message)
        """
        is_valid, error = self._market.validate_listing(
            quantity=self.quantity,
            price=price,
            item_level=self._item.level
        )
        
        if not is_valid:
            return False, error
            
        if not self._can_afford_tax(price):
            return False, "Insufficient kamas for listing tax"
            
        return True, ""

    def _can_afford_tax(self, price: int) -> bool:
        """Check if player can afford listing tax"""
        tax = self._market.calculate_tax(price)
        return PlayedCharacterManager().characteristics.kamas >= tax

    def get_item_from_inventory(self, object_gid: int) -> Optional[ItemWrapper]:
        """Get item wrapper from inventory by GID"""
        if object_gid in ItemWrapper._cacheGId:
            return ItemWrapper._cacheGId[object_gid]
            
        inventory = InventoryManager().inventory.getView("real").content
        for item in inventory:
            if item.objectGID == object_gid:
                return item
                
        return None

    # Market Operations
    def send_search_request(self) -> None:
        """Initiate item search"""
        self._state = "SEARCHING"
        msg = ExchangeBidHouseSearchMessage()
        msg.init(self.object_gid, True)  # Enable following
        ConnectionsHandler().send(msg)

    def send_price_check(self) -> None:
        """Request current prices"""
        self._state = "CHECKING_PRICE"
        msg = ExchangeBidHousePriceMessage()
        msg.init(self.object_gid)
        ConnectionsHandler().send(msg)

    def send_new_listing(self, price: int) -> None:
        """Create new listing"""
        self._state = "SELLING"
        msg = ExchangeObjectMovePricedMessage()
        msg.init(price, self._item.objectUID, self.quantity)
        ConnectionsHandler().send(msg)

    def send_price_update(self, new_price: int, object_uid: int) -> None:
        """Update existing listing price"""
        self._state = "UPDATING"
        msg = ExchangeObjectModifyPricedMessage()
        msg.init(new_price, object_uid, self.quantity)
        ConnectionsHandler().send(msg)

    # Callbacks
    def _on_marketplace_map_reached(self, code: int, error: str) -> None:
        """Handle marketplace map reached"""
        if error:
            return self.finish(code, error)
        self._open_marketplace()
    
    def _on_marketplace_opened(self, code: int, error: str) -> None:
        """Handle marketplace interface opened"""
        if error:
            return self.finish(code, error)
        self._enter_sell_mode()

    # Abstract methods for subclasses
    def _handle_behavior_specific(self, msg) -> None:
        """Handle behavior-specific messages"""
        pass

    def _handle_sell_mode_msg(self, msg) -> None:
        """Handle sell mode initialization"""
        pass

    def _handle_search_msg(self, msg) -> None:
        """Handle search response"""
        pass

    def _handle_price_msg(self, msg) -> None:
        """Handle price check response"""
        pass

    def _on_price_changed(self, old_price: Optional[int], new_price: int) -> None:
        """Handle price updates"""
        pass

    def _on_sale_completed(self, listing: MarketListing) -> None:
        """Handle completed sales"""
        pass

    def _on_listing_removed(self, listing: MarketListing) -> None:
        """Handle listing removals"""
        pass