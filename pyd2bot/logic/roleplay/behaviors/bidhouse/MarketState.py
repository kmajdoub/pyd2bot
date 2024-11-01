from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseInListUpdatedMessage import ExchangeBidHouseInListUpdatedMessage
    from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseItemAddOkMessage import ExchangeBidHouseItemAddOkMessage
    from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidHouseItemRemoveOkMessage import ExchangeBidHouseItemRemoveOkMessage
    from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeBidPriceForSellerMessage import ExchangeBidPriceForSellerMessage
    from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeStartedBidSellerMessage import ExchangeStartedBidSellerMessage
    from pydofus2.com.ankamagames.dofus.network.messages.game.inventory.exchanges.ExchangeTypesItemsExchangerDescriptionForUserMessage import ExchangeTypesItemsExchangerDescriptionForUserMessage

@dataclass
class TypeObjectData:
    """Represents a type of item in the market with its GID listings"""
    type_id: int
    objects: Dict[int, List[Any]]  # GID -> list of listings

@dataclass
class MarketListing:
    """Represents one of our market listings with tracking data"""
    uid: int
    price: int
    quantity: int
    unsold_delay: int
    max_delay: int
    item_type: Optional[int] = None
    item_gid: Optional[int] = None
    
    @property
    def age(self) -> int:
        return max(0, self.max_delay - self.unsold_delay)

    @property
    def age_hours(self) -> int:
        return self.age // 3600
    
    def __lt__(self, other: "MarketListing"):
        """Sort by highest price first, then oldest first"""
        if self.price != other.price:
            return self.price > other.price  # Higher price first
        return self.unsold_delay > other.unsold_delay  # Lower delay = older listing

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
        
        # Current prices per quantity
        self.min_prices: Dict[int, int] = {}  # quantity -> price
        self.avg_prices: Dict[int, int] = {}  # quantity -> avg price
        
        # Current market state
        self.min_prices: Dict[int, int] = {}  # quantity -> current min price
        self.avg_prices: Dict[int, int] = {}  # quantity -> current avg price
        
        # Only track our own listings
        self._our_listings: Dict[int, List[MarketListing]] = {}  # quantity -> our listings

    def init_from_seller_descriptor(self, msg: "ExchangeStartedBidSellerMessage") -> None:
        """Initialize market rules and our listings from seller descriptor"""
        descriptor = msg.sellerDescriptor
        self.tax_percentage = descriptor.taxPercentage
        self.max_item_level = descriptor.maxItemLevel
        self.max_item_count = descriptor.maxItemPerAccount
        self.allowed_types = list(descriptor.types)
        self.valid_quantities = list(descriptor.quantities)
        
        # Clear existing state
        self._our_listings.clear()
        
        # Load our active listings
        for item in msg.objectsInfos:
            listing = MarketListing(
                uid=item.objectUID,
                price=item.objectPrice,
                quantity=item.quantity,
                unsold_delay=item.unsoldDelay,
                max_delay=self.max_delay,
                item_type=item.effects.typeId if item.effects else None,
                item_gid=item.objectGID
            )
            self._add_our_listing(listing)

    def _add_our_listing(self, listing: MarketListing) -> None:
        """Track one of our listings"""
        if listing.quantity not in self._our_listings:
            self._our_listings[listing.quantity] = []
            
        self._our_listings[listing.quantity].append(listing)
        self._our_listings[listing.quantity].sort()  # Keep sorted by price
        
    def handle_type_description(self, msg: "ExchangeTypesItemsExchangerDescriptionForUserMessage") -> None:
        """Handle market price information from item search"""
        if not msg.itemTypeDescriptions:
            self._logger.debug(f"No price data for item {msg.objectGID}")
            return
            
        # Get prices from first description
        first_item = msg.itemTypeDescriptions[0]
        
        # Update prices for each quantity
        for i, quantity in enumerate(self.valid_quantities):
            if i < len(first_item.prices):
                self.min_prices[quantity] = first_item.prices[i]
                # Average price not provided in this message type
                
        self._search_initialized = True
        self._logger.debug(f"Updated prices for item {msg.objectGID}: {self.min_prices}")
                       
    def handle_market_update(self, msg: "ExchangeBidHouseInListUpdatedMessage") -> List[Tuple[int, int, int]]:
        """Track market price changes"""
        changes = []
        for i, quantity in enumerate(self.valid_quantities):
            if i < len(msg.prices):
                old_price = self.min_prices.get(quantity)
                new_price = msg.prices[i]
                
                # Don't update min price if we have better
                our_min = min((l.price for l in self._our_listings.get(quantity, [])), default=None)
                if our_min is not None and our_min <= new_price:
                    continue
                    
                if old_price != new_price:
                    self.min_prices[quantity] = new_price
                    changes.append((quantity, old_price, new_price))
                    self._logger.debug(f"Price changed for {quantity}x: {old_price} -> {new_price}")
                    
        return changes

    def handle_price_info(self, msg: "ExchangeBidPriceForSellerMessage") -> None:
        """Update current market prices"""
        for i, quantity in enumerate(self.valid_quantities):
            if i < len(msg.minimalPrices):
                self.min_prices[quantity] = msg.minimalPrices[i]
                self.avg_prices[quantity] = msg.averagePrice * quantity

    def remove_listing(self, uid: int) -> Optional[MarketListing]:
        """Remove one of our listings when sold/removed"""
        for listings in self._our_listings.values():
            for i, listing in enumerate(listings):
                if listing.uid == uid:
                    return listings.pop(i)
        return None
    
    def handle_listing_remove(self, msg: "ExchangeBidHouseItemRemoveOkMessage") -> Optional[MarketListing]:
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

    def handle_listing_add(self, msg: "ExchangeBidHouseItemAddOkMessage") -> MarketListing:
        """Track when one of our listings is added"""
        listing = MarketListing(
            uid=msg.itemInfo.objectUID,
            price=msg.itemInfo.objectPrice,
            quantity=msg.itemInfo.quantity,
            unsold_delay=msg.itemInfo.unsoldDelay,
            max_delay=self.max_delay,
            item_type=msg.itemInfo.effects.typeId if msg.itemInfo.effects else None,
            item_gid=msg.itemInfo.objectGID
        )
        
        self._add_our_listing(listing)
        
        # Update min price if our new listing is lowest
        current_min = self.min_prices.get(listing.quantity)
        if current_min is None or listing.price <= current_min:
            self.min_prices[listing.quantity] = listing.price
            self._logger.debug(
                f"Our new listing is lowest price for {listing.quantity}x at {listing.price}"
            )
            
        return listing

    def is_search_initialized(self, type_ids: List[int]) -> bool:
        """Check if search mode is initialized for given types"""
        return (self._search_initialized and 
                self._last_search_types == type_ids)

    def invalidate_search(self):
        """Force search reinitialization"""
        self._search_initialized = False
        self._last_search_types = None

    def get_listings(self, quantity: int) -> List[MarketListing]:
        """Get sorted listings for quantity"""
        return self._our_listings.get(quantity, [])

    def find_matching_listing(self, price: int, quantity: int) -> Optional[MarketListing]:
        """Find oldest listing matching price and quantity"""
        matches = [l for l in self.get_listings(quantity) if l.price == price]
        if not matches:
            return None
        return min(matches, key=lambda x: x.unsold_delay)

    def calculate_tax(self, price: int) -> int:
        """Calculate tax amount for given price"""
        return (price * self.tax_percentage) // 100

    def validate_listing(self, quantity: int, price: int, item_level: int) -> Tuple[bool, str]:
        """Validate listing parameters against market rules"""
        if quantity not in self.valid_quantities:
            return False, f"Invalid quantity. Must be one of: {self.valid_quantities}"
            
        if len(self.get_listings(quantity)) >= self.max_item_count:
            return False, f"Maximum listings ({self.max_item_count}) reached"
            
        if item_level > self.max_item_level:
            return False, f"Item level exceeds maximum ({self.max_item_level})"
            
        return True, ""

    @property
    def total_listings(self) -> int:
        """Get total number of active listings"""
        return sum(len(listings) for listings in self._our_listings.values())

    def get_quantity_info(self, quantity: int) -> Dict:
        """Get current market info for specific quantity"""
        return {
            "min_price": self.min_prices.get(quantity),
            "avg_price": self.avg_prices.get(quantity),
            "active_listings": len(self.get_listings(quantity)),
            "oldest_listing": min(self.get_listings(quantity), key=lambda x: x.unsold_delay) if self.get_listings(quantity) else None
        }
        
    def get_listings_older_than(self, quantity: int, hours: float, item_gid: int = None) -> List[MarketListing]:
        """
        Get listings older than specified hours, optionally filtered by item GID.
        
        Args:
            quantity: The quantity per listing to filter for
            hours: Minimum age in hours
            item_gid: Optional item GID to filter for
            
        Returns:
            List of MarketListing objects sorted by age (oldest first)
        """
        min_age = int(hours * 3600)  # Convert hours to seconds
        listings = self.get_listings(quantity)
        
        if item_gid is not None:
            listings = [l for l in listings if l.item_gid == item_gid]
            
        return sorted(
            [l for l in listings if l.age >= min_age],
            key=lambda x: x.age,
            reverse=True  # Oldest first
        )

    def get_safe_price(self, quantity: int, min_price_ratio: float, item_gid: int) -> Optional[int]:
        """
        Get safe price that won't go below minimum ratio of average for a specific item.
        
        Args:
            quantity: The quantity per listing
            min_price_ratio: Minimum acceptable price as ratio of average price
            item_gid: The item GID to check
            
        Returns:
            Target price or None if market price unsafe
        """
        market_info = self.get_quantity_info_by_gid(quantity, item_gid)
        if not market_info["min_price"] or not market_info["avg_price"]:
            return None

        min_acceptable = int(market_info["avg_price"] * min_price_ratio)
        if market_info["min_price"] < min_acceptable:
            return None  # Market price too low
                
        return max(min_acceptable, market_info["min_price"] - 1)

    def get_updatable_listings(
            self, 
            quantity: int,
            min_hours: float,
            min_price_ratio: float
        ) -> List[MarketListing]:
            """Get updatable listings sorted by highest price first, then oldest first"""
            # Check prices exist
            min_price = self.min_prices.get(quantity)
            avg_price = self.avg_prices.get(quantity)
            if not min_price or not avg_price:
                return []

            # Check market price acceptable
            min_acceptable = int(avg_price * min_price_ratio)
            if min_price < min_acceptable:
                self._logger.warning(f"Market price {min_price} below minimum {min_acceptable}")
                return []

            # Check if we already have best price
            our_listings = self._our_listings.get(quantity, [])
            if our_listings and our_listings[0].price <= min_price:
                self._logger.debug(f"We have the best price at {our_listings[0].price}")
                return []

            # Filter listings that are:
            # 1. Old enough to update
            # 2. Above current market price
            min_age = int(min_hours * 3600)
            updatable = [
                listing for listing in our_listings
                if listing.age >= min_age and listing.price > min_price
            ]

            # Sort by price (highest first) and age (oldest first)
            if updatable:
                updatable.sort()  # Uses __lt__ which sorts highest price & oldest first
                self._logger.info(
                    f"Found {len(updatable)} listings to update, "
                    f"highest price: {updatable[0].price}"
                )

            return updatable
    
    def get_listings_by_gid(self, quantity: int, item_gid: int) -> List[MarketListing]:
        """
        Get all listings for a specific item GID and quantity.
        
        Args:
            quantity: The quantity per listing to filter for
            item_gid: The item GID to filter for
            
        Returns:
            List of matching MarketListing objects
        """
        return [
            listing for listing in self.get_listings(quantity)
            if listing.item_gid == item_gid
        ]

    def get_quantity_info_by_gid(self, quantity: int, item_gid: int) -> Dict:
        """
        Get current market info for specific quantity and item GID.
        
        Args:
            quantity: The quantity per listing to check
            item_gid: The item GID to check
            
        Returns:
            Dict containing market information for the specific item
        """
        listings = self.get_listings_by_gid(quantity, item_gid)
        return {
            "min_price": self.min_prices.get(quantity),
            "avg_price": self.avg_prices.get(quantity),
            "active_listings": len(listings),
            "oldest_listing": min(listings, key=lambda x: x.unsold_delay) if listings else None
        }
    
    def get_safe_price(self, quantity: int, min_price_ratio: float) -> Optional[int]:
        """
        Get safe price that won't go below minimum ratio of average
        Returns: Target price or None if market price unsafe
        """
        market_info = self.get_quantity_info(quantity)
        if not market_info["min_price"] or not market_info["avg_price"]:
            return None

        min_acceptable = int(market_info["avg_price"] * min_price_ratio)
        if market_info["min_price"] < min_acceptable:
            return None  # Market price too low
            
        return max(min_acceptable, market_info["min_price"] - 1)