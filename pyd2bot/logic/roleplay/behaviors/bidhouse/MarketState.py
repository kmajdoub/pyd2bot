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
    """Represents a single market listing with tracking data"""
    uid: int
    price: int
    quantity: int
    unsold_delay: int
    max_delay: int
    item_type: Optional[int] = None
    item_gid: Optional[int] = None
    
    @property
    def age(self) -> int:
        """Get listing age in seconds based on max_delay - unsold_delay"""
        return self.max_delay - self.unsold_delay

    @property
    def age_hours(self) -> int:
        """Get listing age in hours"""
        return self.age // 3600
        
    @property
    def remaining_hours(self) -> int:
        """Get remaining time in hours"""
        return self.unsold_delay // 3600
    
    def __lt__(self, other: "MarketListing"):
        """Compare listings by price (ascending) then age (descending)"""
        if self.price != other.price:
            return self.price < other.price
        return self.unsold_delay < other.unsold_delay  # Higher unsoldDelay = newer listing

class MarketState:
    """Manages market state and rule tracking"""
    MAX_LISTING_DAYS = 27
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
        self.top_bid_uid: Optional[int] = None
        
        # Active listings organized by quantity and type
        self._listings: Dict[int, List[MarketListing]] = {}  # quantity -> listings
        self._type_listings: Dict[int, TypeObjectData] = {}  # type_id -> TypeObjectData
        
        # Search mode tracking (from original implementation)
        self._search_initialized: bool = False
        self._last_search_types: Optional[List[int]] = None

    def init_from_seller_descriptor(self, msg: "ExchangeStartedBidSellerMessage") -> None:
        """Initialize market rules and state from seller descriptor"""
        descriptor = msg.sellerDescriptor
        self.tax_percentage = descriptor.taxPercentage
        self.max_item_level = descriptor.maxItemLevel
        self.max_item_count = descriptor.maxItemPerAccount
        self.allowed_types = list(descriptor.types)
        self.valid_quantities = list(descriptor.quantities)
        self.npc_id = descriptor.npcContextualId
        
        # Clear existing state
        self._listings.clear()
        self._type_listings.clear()
        
        # Initialize type tracking
        for type_id in self.allowed_types:
            self._type_listings[type_id] = TypeObjectData(type_id, {})
        
        # Load active listings
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
            self.add_listing(listing)
            
        # Reset search state if types changed
        if self._last_search_types != self.allowed_types:
            self._search_initialized = False
            self._last_search_types = self.allowed_types.copy()
            
        self._logger.debug(
            f"Market initialized: maxDelay={self.max_delay}, "
            f"quantities={self.valid_quantities}, "
            f"types={len(self.allowed_types)}, "
            f"listings={self.total_listings}"
        )

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
        """
        Process market price updates
        Returns list of (quantity, old_price, new_price) tuples for changed prices
        """
        old_prices = self.min_prices.copy()
        self.top_bid_uid = msg.itemUID
        
        # Update prices and type tracking
        for i, quantity in enumerate(self.valid_quantities):
            if i < len(msg.prices):
                self.min_prices[quantity] = msg.prices[i]
        
        # Update type listings
        if msg.objectType in self._type_listings:
            type_data = self._type_listings[msg.objectType]
            type_data.objects[msg.objectGID] = type_data.objects.get(msg.objectGID, [])
            
            # Update or add price info
            found = False
            for listing in type_data.objects[msg.objectGID]:
                if listing['uid'] == msg.itemUID:
                    listing['prices'] = msg.prices
                    found = True
                    break
            
            if not found:
                type_data.objects[msg.objectGID].append({
                    'uid': msg.itemUID,
                    'prices': msg.prices
                })
                
        # Track price changes
        changed_prices = []
        for quantity, new_price in self.min_prices.items():
            old_price = old_prices.get(quantity)
            if old_price != new_price:
                changed_prices.append((quantity, old_price, new_price))
                self._logger.debug(f"Price changed for {quantity}x: {old_price} -> {new_price}")
                
        return changed_prices

    def handle_price_info(self, msg: "ExchangeBidPriceForSellerMessage") -> None:
        """Update price information from price check response"""
        for i, quantity in enumerate(self.valid_quantities):
            if i < len(msg.minimalPrices):
                self.min_prices[quantity] = msg.minimalPrices[i]
                # Average price is per unit, multiply by quantity
                self.avg_prices[quantity] = msg.averagePrice * quantity

    def remove_listing(self, seller_id: int) -> Optional[MarketListing]:
        listing = None
        for listings in self._listings.values():
            for i, listing in enumerate(listings):
                if listing.uid == seller_id:
                    listing = listings.pop(i)
                    if listing.item_type and listing.item_gid:
                        type_data = self._type_listings.get(listing.item_type)
                        if type_data and listing.item_gid in type_data.objects:
                            type_data.objects[listing.item_gid] = [
                                l for l in type_data.objects[listing.item_gid] 
                                if l['uid'] != seller_id
                            ]
                    return listing
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
        listing = MarketListing(
            uid=msg.itemInfo.objectUID,
            price=msg.itemInfo.objectPrice,  
            quantity=msg.itemInfo.quantity,
            unsold_delay=msg.itemInfo.unsoldDelay,
            max_delay=self.max_delay,
            item_type=msg.itemInfo.effects.typeId if msg.itemInfo.effects else None,  # Add this
            item_gid=msg.itemInfo.objectGID  # Add this
        )
        self.add_listing(listing)
        return listing

    def add_listing(self, listing: MarketListing) -> bool:
        """Add new listing, maintaining sort order and type tracking"""
        # Check quantity limits
        if len(self.get_listings(listing.quantity)) >= self.max_item_count:
            return False
            
        # Add to quantity-based listings
        if listing.quantity not in self._listings:
            self._listings[listing.quantity] = []
        
        listings = self._listings[listing.quantity]
        listings.append(listing)
        listings.sort()  # Uses __lt__ for price+age sorting
        
        # Add to type tracking if type info available
        if listing.item_type and listing.item_gid:
            if listing.item_type not in self._type_listings:
                self._type_listings[listing.item_type] = TypeObjectData(listing.item_type, {})
            
            type_data = self._type_listings[listing.item_type]
            if listing.item_gid not in type_data.objects:
                type_data.objects[listing.item_gid] = []
                
            type_data.objects[listing.item_gid].append({
                'uid': listing.uid,
                'price': listing.price,
                'quantity': listing.quantity,
                'age': listing.age
            })
            
        return True

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
        return self._listings.get(quantity, [])

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
        return sum(len(listings) for listings in self._listings.values())

    def get_quantity_info(self, quantity: int) -> Dict:
        """Get current market info for specific quantity"""
        return {
            "min_price": self.min_prices.get(quantity),
            "avg_price": self.avg_prices.get(quantity),
            "active_listings": len(self.get_listings(quantity)),
            "oldest_listing": min(self.get_listings(quantity), key=lambda x: x.unsold_delay) if self.get_listings(quantity) else None
        }
        
    def get_listings_older_than(self, quantity: int, hours: float) -> List[MarketListing]:
        """Get listings older than specified hours, sorted by age"""
        min_age = int(hours * 3600)  # Convert hours to seconds
        return sorted(
            [l for l in self.get_listings(quantity) if l.age >= min_age],
            key=lambda x: x.age,
            reverse=True  # Oldest first
        )

    def get_updatable_listings(self, quantity: int, min_hours: float, min_price_ratio: float) -> List[MarketListing]:
        """
        Get listings that could be updated based on age and price criteria
        Returns: List of listings sorted by age (oldest first)
        """
        market_info = self.get_quantity_info(quantity)
        if not market_info["min_price"] or not market_info["avg_price"]:
            return []

        min_acceptable = int(market_info["avg_price"] * min_price_ratio)
        if market_info["min_price"] < min_acceptable:
            return []  # Market price too low for safe updates

        return [
            listing for listing in self.get_listings_older_than(quantity, min_hours)
            if listing.price > market_info["min_price"]  # Only update if above market price
        ]

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