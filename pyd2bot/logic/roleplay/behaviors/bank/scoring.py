from datetime import datetime, timedelta
import threading
from typing import Any, Optional
from pyd2bot.logic.roleplay.behaviors.bidhouse.MarketItemAnalytics import MarketStats, MarketItemAnalytics
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

class MarketScorer:
    def __init__(self, stats_max_age_hours: int = 24):
        self.analytics = MarketItemAnalytics()
        self.stats_max_age_hours = stats_max_age_hours
        self._stats_cache = dict()
        self._recalculation_lock = threading.Lock()
        self._last_full_recalculation = None
    
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
            Logger().error(f"Error retrieving stats for item {gid}: {str(e)}")
            return None
    
    def _needs_recalculation(self, stats: Optional[MarketStats]) -> bool:
        """Determine if stats need to be recalculated based on age."""
        # First check the full recalculation timestamp
        if self._last_full_recalculation:
            age = datetime.now() - self._last_full_recalculation
            if age <= timedelta(hours=self.stats_max_age_hours):
                return False
        
        # Then check individual stats if available
        if stats:
            age = datetime.now() - stats.calculated_at
            return age > timedelta(hours=self.stats_max_age_hours)
        
        return True
    
    def _recalculate_all_stats(self):
        """Recalculate all stats using the analytics module."""
        # Use a lock to prevent multiple simultaneous recalculations
        if not self._recalculation_lock.acquire(blocking=False):
            Logger().debug("Recalculation already in progress, skipping")
            return
        
        try:
            # Check if we really need to recalculate
            if self._last_full_recalculation:
                age = datetime.now() - self._last_full_recalculation
                if age <= timedelta(hours=self.stats_max_age_hours):
                    Logger().debug("Stats are still fresh, skipping recalculation")
                    return
            
            Logger().info("Starting full stats recalculation")
            all_stats = self.analytics.calculate_all_stats()
            
            # Batch insert new stats with timestamp
            current_time = datetime.now()
            for stats in all_stats:
                stats.calculated_at = current_time
            
            self.analytics.batch_save_stats(all_stats)
            
            # Update cache with all new stats
            self._stats_cache.clear()  # Clear old cache
            for stats in all_stats:
                cache_key = (stats.server_id, stats.object_gid, stats.batch_size)
                self._stats_cache[cache_key] = (current_time, stats)
            
            self._last_full_recalculation = current_time
            Logger().info("Completed full stats recalculation")
            
        except Exception as e:
            Logger().error(f"Error during stats recalculation: {str(e)}")
            raise
        finally:
            self._recalculation_lock.release()
    
    def score(self, server_id: int, gid: int, batch_size: int) -> float:
        """Score an item based on its market statistics."""
        try:
            # Check if item exists in server items first
            if not Kernel().averagePricesFrame.getItemAveragePrice(gid):
                Logger().debug(f"Item {gid} not found in server items")
                return 0.0
            
            # Get latest stats (from cache or DB)
            stats = self._get_latest_stats(server_id, gid, batch_size)
            
            # Only recalculate if really needed
            if self._needs_recalculation(stats):
                try:
                    self._recalculate_all_stats()
                    stats = self._get_latest_stats(server_id, gid, batch_size)
                except Exception as e:
                    Logger().error(f"Failed to recalculate stats: {str(e)}")
            
            if stats:
                return stats.mean_profit_per_hour
            
            # Fallback calculation if no stats available
            avg_price = Kernel().averagePricesFrame.getItemAveragePrice(gid)
            return (batch_size * avg_price) / 0.5 if avg_price else 0.0
            
        except Exception as e:
            Logger().error(f"Error scoring item {gid}: {str(e)}")
            return 0.0