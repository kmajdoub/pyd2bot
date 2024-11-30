from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
import numpy as np
from typing import List, Dict, Optional, Tuple
from pyd2bot.logic.roleplay.behaviors.bidhouse.MarketPersistence import MarketPersistence
from pydofus2.com.ankamagames.dofus.datacenter.items.Item import Item

@dataclass
class MarketStats:
    server_id: int
    object_gid: int
    batch_size: int
    item_name: str
    calculated_at: datetime
    num_samples: int
    mean_time_to_sell: float
    std_time_to_sell: float
    exp_rate: float
    mean_price: float
    std_price: float
    median_price: float
    mean_tax: float
    std_tax: float
    sales_rate: float
    mean_profit_per_hour: float
    std_profit_per_hour: float
    p95_profit_per_hour: float

    def __post_init__(self):
        """Convert any NumPy types to Python native types after initialization"""
        self.server_id = int(self.server_id)
        self.object_gid = int(self.object_gid)
        self.batch_size = int(self.batch_size)
        self.num_samples = int(self.num_samples)
        self.mean_time_to_sell = float(self.mean_time_to_sell)
        self.std_time_to_sell = float(self.std_time_to_sell)
        self.exp_rate = float(self.exp_rate)
        self.mean_price = float(self.mean_price)
        self.std_price = float(self.std_price)
        self.median_price = float(self.median_price)
        self.mean_tax = float(self.mean_tax)
        self.std_tax = float(self.std_tax)
        self.sales_rate = float(self.sales_rate)
        self.mean_profit_per_hour = float(self.mean_profit_per_hour)
        self.std_profit_per_hour = float(self.std_profit_per_hour)
        self.p95_profit_per_hour = float(self.p95_profit_per_hour)
        
class MarketItemAnalytics:
    def __init__(self):
        self.market_db = MarketPersistence()
        self._ensure_stats_table()

    def calculate_item_stats(self, server_id: int, gid: int, batch_size: int) -> Optional[MarketStats]:
        """Calculate statistics for a specific item."""
        try:
            def safe_mean(arr):
                return float(np.mean(arr)) if len(arr) > 0 else 0.0
                
            def safe_std(arr):
                return float(np.std(arr)) if len(arr) > 0 else 0.0
                
            def safe_median(arr):
                return float(np.median(arr)) if len(arr) > 0 else 0.0
                
            def safe_percentile(arr, p):
                return float(np.percentile(arr, p)) if len(arr) > 0 else 0.0
            
            # Fetch specific sales data
            with self.market_db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            price,
                            sold_at,
                            created_at
                        FROM bids
                        WHERE server_id = %s 
                        AND object_gid = %s 
                        AND batch_size = %s
                        AND sold_at IS NOT NULL
                        ORDER BY sold_at DESC
                    """, (server_id, gid, batch_size))
                    
                    sales = [{'price': float(row[0]), 'sold_at': row[1], 'created_at': row[2]} 
                            for row in cur.fetchall()]
                    
                    # Fetch average tax
                    cur.execute("""
                        SELECT AVG(tax_amount) as avg_tax
                        FROM tax_history
                        WHERE server_id = %s 
                        AND object_gid = %s 
                        AND batch_size = %s
                    """, (server_id, gid, batch_size))
                    
                    avg_tax = float(cur.fetchone()[0] or 0)

            if not sales:
                return None
                
            item_name = Item.getItemById(gid).name
            
            # Calculate time to sell in hours
            times_to_sell = [(sale['sold_at'] - sale['created_at']).total_seconds() / 3600 
                            for sale in sales]
            
            # Calculate prices
            prices = [sale['price'] for sale in sales]
            
            # Calculate profits per hour
            profits_per_hour = [
                (sale['price'] - avg_tax) / ((sale['sold_at'] - sale['created_at']).total_seconds() / 3600)
                for sale in sales
                if (sale['sold_at'] - sale['created_at']).total_seconds() > 0
            ]
            
            # Calculate sales rate (sales per day)
            if len(sales) >= 2:
                time_span = (sales[0]['sold_at'] - sales[-1]['sold_at']).total_seconds() / (24 * 3600)
                sales_rate = len(sales) / time_span if time_span > 0 else 0
            else:
                sales_rate = 0
            
            # Fit exponential distribution to time to sell
                        # Calculate statistics with safe conversions
            mean_time = safe_mean(times_to_sell)
            exp_rate = float(1 / mean_time if mean_time > 0 else 0)
            
            return MarketStats(
                server_id=int(server_id),
                object_gid=int(gid),
                batch_size=int(batch_size),
                item_name=str(item_name),
                calculated_at=datetime.now(),
                num_samples=int(len(sales)),
                mean_time_to_sell=safe_mean(times_to_sell),
                std_time_to_sell=safe_std(times_to_sell),
                exp_rate=exp_rate,
                mean_price=safe_mean(prices),
                std_price=safe_std(prices),
                median_price=safe_median(prices),
                mean_tax=float(avg_tax),
                std_tax=0.0,
                sales_rate=float(sales_rate),
                mean_profit_per_hour=safe_mean(profits_per_hour),
                std_profit_per_hour=safe_std(profits_per_hour),
                p95_profit_per_hour=safe_percentile(profits_per_hour, 95)
            )
                    
        except Exception as e:
            print(f"Error calculating stats for server={server_id}, gid={gid}, batch={batch_size}: {str(e)}")
            return None

    def _ensure_stats_table(self):
        """Create the statistics table if it doesn't exist."""
        with self.market_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS market_statistics (
                        server_id INTEGER,
                        object_gid INTEGER,
                        batch_size INTEGER,
                        item_name VARCHAR(255),
                        calculated_at TIMESTAMP,
                        num_samples INTEGER,
                        mean_time_to_sell FLOAT,
                        std_time_to_sell FLOAT,
                        exp_rate FLOAT,
                        mean_price FLOAT,
                        std_price FLOAT,
                        median_price FLOAT,
                        mean_tax FLOAT,
                        std_tax FLOAT,
                        sales_rate FLOAT,
                        mean_profit_per_hour FLOAT,
                        std_profit_per_hour FLOAT,
                        p95_profit_per_hour FLOAT,
                        PRIMARY KEY (server_id, object_gid, batch_size, calculated_at)
                    )
                """)
            conn.commit()

    def _fetch_all_sales_data(self) -> Dict[Tuple[int, int, int], List[dict]]:
        """Fetch all sales data in a single query."""
        sales_by_key = defaultdict(list)
        with self.market_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        server_id,
                        object_gid,
                        batch_size,
                        price,
                        sold_at,
                        created_at
                    FROM bids
                    WHERE sold_at IS NOT NULL
                    ORDER BY sold_at DESC
                """)
                
                for row in cur.fetchall():
                    key = (row[0], row[1], row[2])  # server_id, object_gid, batch_size
                    sales_by_key[key].append({
                        'price': float(row[3]),
                        'sold_at': row[4],
                        'created_at': row[5]
                    })
        
        return dict(sales_by_key)

    def _fetch_all_taxes(self) -> Dict[Tuple[int, int, int], float]:
            """Fetch all average taxes using only the tax_history table."""
            with self.market_db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            server_id,
                            object_gid,
                            batch_size,
                            AVG(tax_amount) as avg_tax
                        FROM tax_history
                        GROUP BY server_id, object_gid, batch_size
                    """)
                    
                    return {(row[0], row[1], row[2]): float(row[3]) for row in cur.fetchall()}

    def calculate_all_stats(self) -> List[MarketStats]:
        """Calculate statistics for all items in a single batch."""
        # Fetch all data at once
        print("Fetching all sales data...")
        sales_data = self._fetch_all_sales_data()
        print(f"Found {len(sales_data)} unique combinations with sales data")
        
        print("Fetching all tax data...")
        tax_data = self._fetch_all_taxes()
        print(f"Found {len(tax_data)} unique combinations with tax data")
        
        # Calculate statistics for each combination
        all_stats = []
        for key, sales in sales_data.items():
            server_id, gid, batch_size = key
            avg_tax = tax_data.get(key, 0)
            
            try:
                item_name = Item.getItemById(gid).name
                
                # Calculate time to sell in hours
                times_to_sell = [(sale['sold_at'] - sale['created_at']).total_seconds() / 3600 
                                for sale in sales]
                
                # Calculate prices
                prices = [sale['price'] for sale in sales]
                
                # Calculate profits per hour
                profits_per_hour = [
                    (sale['price'] - avg_tax) / ((sale['sold_at'] - sale['created_at']).total_seconds() / 3600)
                    for sale in sales
                    if (sale['sold_at'] - sale['created_at']).total_seconds() > 0
                ]
                
                # Calculate sales rate (sales per day)
                if len(sales) >= 2:
                    time_span = (sales[0]['sold_at'] - sales[-1]['sold_at']).total_seconds() / (24 * 3600)
                    sales_rate = len(sales) / time_span if time_span > 0 else 0
                else:
                    sales_rate = 0
                
                # Fit exponential distribution to time to sell
                exp_rate = 1 / np.mean(times_to_sell) if times_to_sell else 0
                
                stats = MarketStats(
                    server_id=server_id,
                    object_gid=gid,
                    batch_size=batch_size,
                    item_name=item_name,
                    calculated_at=datetime.now(),
                    num_samples=len(sales),
                    mean_time_to_sell=np.mean(times_to_sell),
                    std_time_to_sell=np.std(times_to_sell),
                    exp_rate=exp_rate,
                    mean_price=np.mean(prices),
                    std_price=np.std(prices),
                    median_price=np.median(prices),
                    mean_tax=avg_tax,
                    std_tax=0,
                    sales_rate=sales_rate,
                    mean_profit_per_hour=np.mean(profits_per_hour) if profits_per_hour else 0,
                    std_profit_per_hour=np.std(profits_per_hour) if profits_per_hour else 0,
                    p95_profit_per_hour=np.percentile(profits_per_hour, 95) if profits_per_hour else 0
                )
                all_stats.append(stats)
                
            except Exception as e:
                print(f"Error processing server={server_id}, gid={gid}, batch={batch_size}: {str(e)}")
                continue
        
        return all_stats

    def batch_save_stats(self, all_stats: List[MarketStats]):
        """Save all statistics in a single transaction."""
        with self.market_db.get_connection() as conn:
            with conn.cursor() as cur:
                for stats in all_stats:
                    cur.execute("""
                        INSERT INTO market_statistics (
                            server_id, object_gid, item_name, batch_size, calculated_at,
                            num_samples, mean_time_to_sell, std_time_to_sell, exp_rate,
                            mean_price, std_price, median_price,
                            mean_tax, std_tax, sales_rate,
                            mean_profit_per_hour, std_profit_per_hour, p95_profit_per_hour
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        stats.server_id, stats.object_gid, stats.item_name, stats.batch_size, stats.calculated_at,
                        stats.num_samples, stats.mean_time_to_sell, stats.std_time_to_sell, stats.exp_rate,
                        stats.mean_price, stats.std_price, stats.median_price,
                        stats.mean_tax, stats.std_tax, stats.sales_rate,
                        stats.mean_profit_per_hour, stats.std_profit_per_hour, stats.p95_profit_per_hour
                    ))
            conn.commit()

if __name__ == "__main__":
    calculator = MarketItemAnalytics()
    
    print("Calculating statistics...")
    all_stats = calculator.calculate_all_stats()
    print(f"Calculated statistics for {len(all_stats)} items")
    
    print("Saving statistics to database...")
    calculator.batch_save_stats(all_stats)
    print("Done!")