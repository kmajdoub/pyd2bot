from datetime import datetime, timedelta
from typing import Any, Optional
from pyd2bot.logic.roleplay.behaviors.bidhouse.MarketItemAnalytics import MarketStats, MarketItemAnalytics
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

class MarketScorer:
    def __init__(self, stats_max_age_hours: int = 24):
        self.analytics = MarketItemAnalytics()
        self.stats_max_age_hours = stats_max_age_hours
        self._stats_cache = dict()
    
    def _get_latest_stats(self, server_id: int, gid: int, batch_size: int) -> Optional[MarketStats]:
        """Retrieve the latest stats for an item from the database."""
        cache_key = (server_id, gid, batch_size)
        
        # Check memory cache first
        cached = self._stats_cache.get(cache_key)
        if cached:
            timestamp, stats = cached
            if datetime.now() - timestamp <= timedelta(hours=self.stats_max_age_hours):
                return stats
        
        # If not in cache or expired, get from database
        try:
            with self.analytics.market_db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT *
                        FROM market_statistics
                        WHERE server_id = %s AND object_gid = %s AND batch_size = %s
                        ORDER BY calculated_at DESC
                        LIMIT 1
                    """, (server_id, gid, batch_size))
                    
                    row = cur.fetchone()
                    if not row:
                        return None
                    
                    stats = MarketStats(
                        server_id=row[0],
                        object_gid=row[1],
                        batch_size=row[2],
                        item_name=row[3],
                        calculated_at=row[4],
                        num_samples=row[5],
                        mean_time_to_sell=row[6],
                        std_time_to_sell=row[7],
                        exp_rate=row[8],
                        mean_price=row[9],
                        std_price=row[10],
                        median_price=row[11],
                        mean_tax=row[12],
                        std_tax=row[13],
                        sales_rate=row[14],
                        mean_profit_per_hour=row[15],
                        std_profit_per_hour=row[16],
                        p95_profit_per_hour=row[17]
                    )
                    
                    # Update cache
                    self._stats_cache[cache_key] = (datetime.now(), stats)
                    return stats
                    
        except Exception as e:
            print(f"Error retrieving stats for item {gid}: {str(e)}")
            return None
    
    def score(self, server_id: int, gid: int, batch_size: int) -> float:
        """Score an item based on its market statistics."""
        try:
            # Get latest stats (from cache or DB)
            stats = self._get_latest_stats(server_id, gid, batch_size)
            
            # Calculate if missing or too old
            if not stats or (datetime.now() - stats.calculated_at) > timedelta(hours=self.stats_max_age_hours):
                stats = self.analytics.calculate_item_stats(server_id, gid, batch_size)
                if stats:
                    # Save to DB
                    self.analytics.batch_save_stats([stats])
                    # Update cache
                    self._stats_cache[(server_id, gid, batch_size)] = (datetime.now(), stats)
            
            if stats:
                return stats.mean_profit_per_hour
            
            # Fallback calculation if no stats
            avg_price = Kernel().averagePricesFrame.getItemAveragePrice(gid)
            return (batch_size * avg_price) / 0.5 if avg_price else 0.0
            
        except Exception as e:
            Logger().error(f"Error scoring item {gid}: {str(e)}")
            return 0.0