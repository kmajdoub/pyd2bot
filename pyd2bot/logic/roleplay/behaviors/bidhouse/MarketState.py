from typing import List, Optional, Tuple
from collections import defaultdict

from pyd2bot.logic.roleplay.behaviors.bidhouse.MarketListing import MarketListing
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseInListUpdatedMessage import ExchangeBidHouseInListUpdatedMessage
    from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseItemAddOkMessage import ExchangeBidHouseItemAddOkMessage
    from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseItemRemoveOkMessage import ExchangeBidHouseItemRemoveOkMessage
    from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidPriceForSellerMessage import ExchangeBidPriceForSellerMessage
    from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeStartedBidSellerMessage import ExchangeStartedBidSellerMessage
    from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeTypesItemsExchangerDescriptionForUserMessage import ExchangeTypesItemsExchangerDescriptionForUserMessage


class MarketState:
    """Manages market state and rule tracking"""
    MAX_LISTING_DAYS = 28
    MAX_LISTING_HOURS = MAX_LISTING_DAYS * 24
    MAX_LISTING_SECONDS = MAX_LISTING_HOURS * 3600

    def __init__(self):
        self._logger = Logger()
        
        # Market rules from seller descriptor
        self.max_delay = self.MAX_LISTING_SECONDS
        self.tax_percentage: int = 0
        self.max_item_level: int = 0
        self.max_item_count: int = 0
        self.allowed_types: List[int] = []
        self.valid_quantities: List[int] = []
        
        self.npc_id: Optional[int] = None
        
        # Use defaultdict for nested dictionaries
        self.min_price = defaultdict(lambda: defaultdict(int))  # gid -> quantity -> price
        self.avg_prices = defaultdict(lambda: defaultdict(int))  # gid -> quantity -> avg price
        
        # Nested defaultdict for listings
        self._listings = defaultdict(lambda: defaultdict(list[MarketListing]))  # gid -> quantity -> listings

    def init_from_seller_descriptor(self, msg: "ExchangeStartedBidSellerMessage") -> None:
        """Initialize market rules and our listings from seller descriptor"""
        descriptor = msg.sellerDescriptor
        self.tax_percentage = descriptor.taxPercentage
        self.max_item_level = descriptor.maxItemLevel
        self.max_item_count = descriptor.maxItemPerAccount
        self.allowed_types = list(descriptor.types)
        self.valid_quantities = list(descriptor.quantities)
        
        self._listings.clear()
        
        for item in msg.objectsInfos:
            listing = MarketListing.from_message(item, self.max_delay)
            self._add_our_listing(listing)

    def _add_our_listing(self, listing: MarketListing) -> None:
        """Track one of our listings"""
        self._listings[listing.item_gid][listing.quantity].append(listing)
        self._listings[listing.item_gid][listing.quantity].sort()
        
        self._logger.info(
            f"Added listing: uid={listing.uid} "
            f"gid={listing.item_gid} qty={listing.quantity} "
            f"price={listing.price} age={60 * listing.age_hours:.1f}min"
        )

    def handle_type_description(self, msg: "ExchangeTypesItemsExchangerDescriptionForUserMessage") -> None:
        """Handle market price information from item search"""
        if not msg.itemTypeDescriptions:
            self._logger.debug(f"No price data for item {msg.objectGID}")
            return
                
        first_item = msg.itemTypeDescriptions[0]
            
        # Track initial market state
        for i, quantity in enumerate(self.valid_quantities):
            if i < len(first_item.prices):
                self.min_price[msg.objectGID][quantity] = first_item.prices[i]
                    
        self._logger.debug(
            f"Updated prices for item {msg.objectGID}: {self.min_price[msg.objectGID]}"
        )
    
    def get_listing_by_uid(self, uid: int) -> Optional[MarketListing]:
        """Find a listing by its unique identifier across all items"""
        for gid_listings in self._listings.values():
            for quantity_listings in gid_listings.values():
                for listing in quantity_listings:
                    if listing.uid == uid:
                        return listing
        return None

    def handle_market_update(self, msg: "ExchangeBidHouseInListUpdatedMessage") -> List[Tuple[int, int, int]]:
        """Track market price changes with ownership awareness"""
        changes = []
        
        for i, quantity in enumerate(self.valid_quantities):
            if i < len(msg.prices):
                old_price = self.min_price[msg.objectGID][quantity]
                new_price = msg.prices[i]
                
                if old_price != new_price:
                    KernelEventsManager().send(KernelEvent.AssetPriceChanged, msg.objectGID, quantity, old_price, new_price)
                    our_min = self.get_our_min_price(msg.objectGID, quantity)
                    if our_min and new_price < our_min:
                        KernelEventsManager().send(KernelEvent.NewMarketLow, msg.objectGID, quantity, old_price, new_price)
                    self.min_price[msg.objectGID][quantity] = new_price
                    changes.append((msg.objectGID, quantity, old_price, new_price))
                    self._logger.info(
                        f"Market price changed: gid={msg.objectGID} qty={quantity} "
                        f"old={old_price} new={new_price}"
                    )
                    
        return changes

    def handle_price_info(self, msg: "ExchangeBidPriceForSellerMessage") -> None:
        """Update current market prices"""
        for i, quantity in enumerate(self.valid_quantities):
            if i < len(msg.minimalPrices):
                self.min_price[msg.genericId][quantity] = msg.minimalPrices[i]
                self.avg_prices[msg.genericId][quantity] = msg.averagePrice * quantity
                

    def remove_listing(self, uid: int) -> Optional["MarketListing"]:
        """Remove one of our listings when sold/removed"""
        listing = self.get_listing_by_uid(uid)
        if not listing:
            return None
            
        quantity_listings = self._listings[listing.item_gid][listing.quantity]
        for i, l in enumerate(quantity_listings):
            if l.uid == uid:
                removed = quantity_listings.pop(i)
                self._logger.info(
                    f"Removed listing: uid={removed.uid} "
                    f"gid={removed.item_gid} qty={removed.quantity} "
                    f"price={removed.price} age={removed.age_hours:.1f}h"
                )
                
                # Clean up empty containers
                if not quantity_listings:
                    del self._listings[listing.item_gid][listing.quantity]
                    if not self._listings[listing.item_gid]:
                        del self._listings[listing.item_gid]
                        
                return removed
        return None
    
    def handle_listing_remove(self, msg: "ExchangeBidHouseItemRemoveOkMessage") -> Optional["MarketListing"]:
        """
        Process listing removal
        Returns removed listing if found
        """
        listing = self.remove_listing(msg.sellerId)
        if listing:
            self._logger.debug(
                f"Listing removed: {listing.uid} "
                f"({listing.quantity}x @ {listing.price}, "
                f"age={listing.age}s)"
            )
        return listing

    def handle_listing_add(self, msg: "ExchangeBidHouseItemAddOkMessage") -> "MarketListing":
        """Track when one of our listings is added"""
        listing = MarketListing.from_message(msg.itemInfo, self.max_delay)
        self._add_our_listing(listing)
            
        current_min = self.min_price[msg.itemInfo.objectGID][listing.quantity]
        if current_min == 0 or listing.price <= current_min:
            self.min_price[msg.itemInfo.objectGID][listing.quantity] = listing.price
            self._logger.debug(
                f"Our new listing is lowest price for item {msg.itemInfo.objectGID} "
                f"{listing.quantity}x at {listing.price}"
            )
    
        return listing
    
    def get_listings(self, item_gid: int, quantity: int) -> List[MarketListing]:
        """Get sorted listings for quantity"""
        return self._listings[item_gid][quantity]

    def calculate_tax(self, price: int) -> int:
        """Calculate tax amount for given price"""
        return (price * self.tax_percentage) // 100
        
    def get_listings_older_than(self, item_gid: int, quantity: int, hours: float) -> List[MarketListing]:
        """Get listings older than specified hours"""
        min_age = int(hours * 3600)
        listings = self.get_listings(item_gid, quantity)
            
        return sorted(
            [l for l in listings if l.age >= min_age],
            key=lambda x: x.age,
            reverse=True
        )

    def get_our_min_price(self, item_gid: int, quantity: int) -> Optional[int]:
        """Get our lowest listing price for given item and quantity"""
        listings = self.get_listings(item_gid, quantity)
        if not listings:
            return None
        return min(listing.price for listing in listings)

    def get_updatable_listings(
        self,
        item_gid: int,
        quantity: int,
        min_hours: float,
        min_price_ratio: float
    ) -> Tuple[List[MarketListing], Optional[int], Optional[str]]:
        """Get updatable listings sorted by highest price first, then oldest first"""
        target_price, error = self.get_optimal_price(item_gid, quantity, min_price_ratio)
        if error:
            self._logger.debug(f"Cannot get updatable listings: {error}")
            return [], target_price, error

        min_age = int(min_hours * 3600)
        listings = self.get_listings(item_gid, quantity)
        
        # Update any listings above the target price
        updatable = [
            listing for listing in listings
            if listing.age >= min_age and listing.price > target_price
        ]

        if updatable:
            updatable.sort()  # Sort by highest price first, then oldest
            self._logger.debug(
                f"Found updatable listings: gid={item_gid} qty={quantity} "
                f"count={len(updatable)} highest_price={updatable[0].price} "
                f"target_price={target_price} oldest_age={60 * updatable[0].age_hours:.1f}min"
            )

        return updatable, target_price, None
    
    def get_optimal_price(
        self,
        item_gid: int,
        quantity: int,
        min_price_ratio: float
    ) -> Tuple[Optional[int], Optional[str]]:
        """Calculate optimal price based on market conditions and minimum acceptable price"""
        market_price = self.min_price[item_gid][quantity]
        avg_price = self.avg_prices[item_gid][quantity]
        
        if not market_price or not avg_price:
            return None, "Unable to get market prices"

        min_acceptable = int(avg_price * min_price_ratio)
        our_min = self.get_our_min_price(item_gid, quantity)
        
        self._logger.debug(
            f"Market state: gid={item_gid} qty={quantity} "
            f"market={market_price} our_min={our_min}"
        )
        
        if market_price < min_acceptable:
            return None, f"Market price {market_price} below minimum {min_acceptable}"
        
        if our_min and our_min <= market_price:
            return our_min, None

        # We don't own minimum - try to beat it
        target_price = max(min_acceptable, market_price - 1)
        self._logger.debug(f"undercutting {market_price} to {target_price}")
        return target_price, None

    def count_listings_le_market(self, item_gid: int, quantity: int) -> int:
        market_price = self.min_price[item_gid][quantity]
        listings = self.get_listings(item_gid, quantity)
        return sum(1 for listing in listings if listing.price <= market_price)
