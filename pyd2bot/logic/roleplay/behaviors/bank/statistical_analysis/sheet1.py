
from pyd2bot.logic.roleplay.behaviors.bidhouse.MarketPersistence import MarketPersistence
from pydofus2.com.ankamagames.dofus.datacenter.items.Item import Item

def get_avg_tax(server_id: int, gid: int, batch_size: int):
    with MarketPersistence().get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT AVG(COALESCE(tax_amount, price * 0.02)) as avg_tax
                FROM bids b
                LEFT JOIN tax_history t ON 
                    t.object_gid = b.object_gid 
                    AND t.batch_size = b.batch_size
                    AND t.server_id = b.server_id
                WHERE b.object_gid = %s 
                AND b.server_id = %s
                AND b.batch_size = %s
                AND b.sold_at IS NOT NULL
            """, (gid, server_id, batch_size))
            
            result = cur.fetchone()
            return float(result[0]) if result[0] else None

def get_raw_sales(server_id: int, gid: int, batch_size: int):
    with MarketPersistence().get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    price,
                    sold_at,
                    created_at
                FROM bids
                WHERE object_gid = %s 
                AND server_id = %s
                AND batch_size = %s
                AND sold_at IS NOT NULL
                ORDER BY sold_at DESC
            """, (gid, server_id, batch_size))
            
            rows = cur.fetchall()
            print(f"Found {len(rows)} sales records")
            
            return [
                {
                    'price': float(row[0]),
                    'sold_at': row[1],
                    'created_at': row[2]
                }
                for row in rows
            ]

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import seaborn as sns
    import numpy as np
    
    server_id = 291
    gid = 441
    batch_size = 100
    
    for gid in [312, 313, 350, 395, 421, 428, 441, 442, 443, 444, 445, 446, 449, 461, 441, 16488, 7033, 7032, 6902, 6903, 6897, 2540, 2357, 1782, 474, 471]:
        print("\n\n=================================================================================================")
        item = Item.getItemById(gid)
        
        # Get average tax
        avg_tax = get_avg_tax(server_id, gid, batch_size)
        if not avg_tax:
            continue
        print(f"Item name : {item.name}")
        print(f"Average tax: {avg_tax:,.0f}")
        
        # Get sales data
        sales = get_raw_sales(server_id, gid, batch_size)
        
        # Calculate profits per hour
        profits = []
        for sale in sales:
            hours = (sale['sold_at'] - sale['created_at']).total_seconds() / 3600
            if hours > 0:  # Avoid division by zero
                profit_per_hour = (sale['price'] - avg_tax) / hours
                profits.append(profit_per_hour)
        
        if profits:
            # Calculate stats
            mean_profit = sum(profits) / len(profits)
            median_profit = sorted(profits)[len(profits)//2]
            percentile_95 = np.percentile(profits, 95)
            std_profit = np.std(profits)
            
            # Print stats
            print(f"\nStats:")
            print(f"Number of sales: {len(profits)}")
            print(f"Mean profit/hour: {mean_profit:,.0f}")
            print(f"Median profit/hour: {median_profit:,.0f}")
            print(f"95th percentile: {percentile_95:,.0f}")
            print(f"Std dev: {std_profit:,.0f}")
            print(f"Min profit/hour: {min(profits):,.0f}")
            print(f"Max profit/hour: {max(profits):,.0f}")
            
            # Print distribution by ranges
            ranges = [0, 10000, 50000, 100000, float('inf')]
            print("\nDistribution by ranges:")
            for i in range(len(ranges)-1):
                count = sum(1 for p in profits if ranges[i] <= p < ranges[i+1])
                pct = (count / len(profits)) * 100
                print(f"{ranges[i]:,} to {ranges[i+1]:,}: {count} sales ({pct:.1f}%)")
