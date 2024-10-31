# Market Behavior System Documentation

## Overview
The market (bidhouse) system handles buying and selling items through a real-time marketplace interface. The system maintains continuous price monitoring and handles various market events through background updates.

## Core Components

### Market State
The system maintains state information including:
- Current minimum prices for each quantity (1, 10, 100)
- Average market prices
- Current top bid UID in orderbook
- Active market listings and their age (via unsoldDelay)
- Market rules and constraints from sellerDescriptor
- Tax rates and modifications
- Current listing durations and expiry times

### Market Rules (from ExchangeStartedBidSellerMessage)
- Allowed item types
- Valid quantities (1, 10, 100)
- Tax percentage and modifications
- Maximum items per account
- Item level restrictions
- Seller descriptor configuration:
  * maxDelay: Maximum listing duration in seconds
  * taxPercentage: Tax rate for listings
  * maxItemLevel: Maximum allowed item level
  * maxItemCount: Maximum number of concurrent listings
- Unsold delay timers (tracked per item)

## Server Interaction Sequences

### 1. Initial Market Setup
```
Client -> Server:
1. Travel to market map -> Wait for callback
2. Open market interface -> Wait for callback
3. Switch to sell mode (NpcGenericActionRequestMessage)

Server -> Client:
- ExchangeStartedBidSellerMessage
  Contains: 
  - Market rules (allowed types, quantities, max items, etc.)
  - sellerDescriptor:
    * maxDelay: Maximum time (in seconds) items can be listed
    * taxPercentage: Current tax rate for this market
    * maxItemLevel: Level restriction for items
    * maxItemCount: Maximum concurrent listings allowed
  - Our current active listings only (not all market listings)
    Format: objectUID, objectGID, quantity, objectPrice, unsoldDelay
    Note: unsoldDelay is seconds remaining until listing expires (maxDelay from sellerDescriptor)
          Can be used to determine exact listing age: (maxDelay - unsoldDelay)
  Note: This only shows our character's active listings in the market,
        allowing us to track what we have for sale
```

### 2. Price Monitoring Initialization
```
Client -> Server:
1. ExchangeBidHouseSearchMessage(objectGID, follow=true)

Server -> Client:
1. ExchangeTypesItemsExchangerDescriptionForUserMessage
   Contains: Initial market state (tax amount, allowed item type ids, max items we can put up in sale) for item and our listings
```

### 3. Price Check Sequence
```
Client -> Server:
1. ExchangeBidHousePriceMessage(objectGID)

Server -> Client:
1. ExchangeBidPriceForSellerMessage
   Contains: Minimal prices per quantity, average price
```

### 4. Put Item For Sale Sequence
```
Client -> Server:
1. ExchangeObjectMovePricedMessage(price, objectUID, quantity)
objectUID: we get from the object in our inventory, iw.objectUID
iw: is the item object we fetched from inventory using getObject

Server -> Client (Complete sequence):
1. ObjectQuantityMessage or ObjectDeletedMessage (inventory update)
2. KamasUpdateMessage (tax deducted)
3. ExchangeBidHouseItemAddOkMessage (listing confirmed)
4. ExchangeBidHouseInListUpdatedMessage (market update)
5. InventoryWeightMessage
```

### 5. Update Existing Bid Sequence
```
Client -> Server:
1. ExchangeObjectModifyPricedMessage(newPrice, objectUID, quantity)

Server -> Client (Complete sequence):
1. KamasUpdateMessage
2. ExchangeBidHouseInListUpdatedMessage
3. ExchangeBidHouseItemRemoveOkMessage
4. ExchangeBidHouseItemAddOkMessage (includes new unsoldDelay)
5. ExchangeBidHouseInListUpdatedMessage
```

## Background Updates & Notifications

### Real-time Price Updates
The server sends ExchangeBidHouseInListUpdatedMessage containing:
- itemUID: Current top bid's unique identifier
- objectGID: Item type ID
- prices: Current minimum prices for all quantities
These updates occur whenever the market state changes.

### Sale Notifications
When an item is sold, the server sends:
1. ExchangeBidHouseInListUpdatedMessage (new top bid)
2. ExchangeBidHouseItemRemoveOkMessage (item removal)
3. TextInformationMessage (msgId=65)
   Parameters: [price, itemGID, itemGID, quantity]

Note: When receiving sale notifications for our own items, we can determine which specific item sold by:
1. Finding all our listings matching the sold quantity
2. Among those, identifying the ones with lowest price
3. From those, selecting the one with highest unsoldDelay (oldest listing)
This matches the server's behavior of selling oldest cheapest items first.

## State Management Guidelines

### Price Monitoring
- Always enable price following (follow=true) when searching for items
- Track top bid changes through ExchangeBidHouseInListUpdatedMessage
- Maintain current minimum and average prices
- Update prices when receiving price notifications

### Listing Management
- Track active listings by their unique IDs
- Track listing age using unsoldDelay (sellerDescriptor.maxDelay - unsoldDelay = time listed)
- Monitor listing removals through ExchangeBidHouseItemRemoveOkMessage
- Validate new listings against market rules:
  * Check against sellerDescriptor.maxItemCount
  * Verify item level against sellerDescriptor.maxItemLevel
  * Ensure listing duration doesn't exceed sellerDescriptor.maxDelay
- Track listing expiry times
- Use unsoldDelay to:
  * Determine which listings need price updates (oldest first)
  * Match sold items to specific listings
  * Monitor listing age and auto-relist if needed
  * Sort listings by age for accurate sale tracking
- Note that maxDelay can vary by server/market type, always use sellerDescriptor.maxDelay

### Bid Tracking Best Practices
1. Maintain listings sorted by:
   - Primary: quantity (1, 10, 100)
   - Secondary: price (ascending)
   - Tertiary: unsoldDelay (descending = oldest first)

2. When receiving sale notification:
   - Filter listings by sold quantity
   - Among lowest price matches, remove the one with highest unsoldDelay
   - This accurately matches server's sale order

3. For price updates:
   - Prioritize updating oldest listings (highest unsoldDelay)
   - Consider both price position and listing age
   - Reset unsoldDelay when updating price

### Error Handling
- Verify complete message sequences for operations
- Handle partial sequence failures
- Maintain consistent state on errors
- Validate all operations against market rules
- Verify listing constraints against sellerDescriptor before operations

## Implementation Notes

### Price Updates
- Server sends regular updates for followed items
- Updates contain current best prices for all quantities
- Track changes to respond to market movements
- Consider listing age when deciding update priority

### Sale Processing
- Sale notifications provide final sale price
- Match sales to specific listings using quantity + price + unsoldDelay
- Remove sold items from active tracking
- Update market state after sales
- Use unsoldDelay to maintain accurate listing order

### Tax Handling
- Calculate tax using sellerDescriptor.taxPercentage
- Verify kamas balance before operations
- Track tax payments in operation sequences
- Consider tax modifications from market rules