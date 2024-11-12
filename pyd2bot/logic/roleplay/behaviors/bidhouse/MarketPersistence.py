import psycopg2
import psycopg2.pool
import psycopg2.extras
from contextlib import contextmanager
from typing import Dict, List, Optional
import threading
from datetime import datetime, timezone
import uuid
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.metaclass.ThreadSharedSingleton import ThreadSharedSingleton

class MarketPersistence(metaclass=ThreadSharedSingleton):
    """Manages persistence of market data and bid tracking"""
    
    _lock = threading.Lock()
    
    def __init__(self,
                 host: str = "localhost",
                 port: int = 5432,
                 database: str = "pyd2bot",
                 user: str = "pyd2bot", 
                 password: str = "rMrTXHA4*",
                 min_connections: int = 5,
                 max_connections: int = 15):
        
        self.logger = Logger()
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=min_connections,
            maxconn=max_connections,
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables and indexes"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Global market configuration
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS markets (
                        id SERIAL PRIMARY KEY,
                        market_type INTEGER NOT NULL,
                        level_max INTEGER NOT NULL,
                        map_id INTEGER NOT NULL,
                        npc_id INTEGER,
                        accepted_resources INTEGER[] NOT NULL DEFAULT '{}',
                        tax_percentage INTEGER NOT NULL,
                        max_sell_slots INTEGER NOT NULL,
                        gfx_id INTEGER,
                        last_time_opened TIMESTAMPTZ,
                        require_subscription BOOLEAN NOT NULL DEFAULT false,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        UNIQUE(market_type, map_id)
                    )
                """)
                
                # Server/account specific bids
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bids (
                        id SERIAL PRIMARY KEY,
                        uid INTEGER NOT NULL,
                        server_id INTEGER NOT NULL,
                        account_id INTEGER NOT NULL,
                        session_id UUID NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        price INTEGER NOT NULL,
                        object_gid INTEGER NOT NULL,
                        batch_size INTEGER NOT NULL,
                        sold_at TIMESTAMPTZ,
                        UNIQUE(uid, server_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_bids_lookup 
                        ON bids (server_id, object_gid, batch_size, price) 
                        WHERE sold_at IS NULL;
                        
                    CREATE INDEX IF NOT EXISTS idx_bids_session 
                        ON bids (session_id);
                """)
                
                # Tax history with server/account tracking
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tax_history (
                        id SERIAL PRIMARY KEY,
                        object_gid INTEGER NOT NULL,
                        batch_size INTEGER NOT NULL,
                        tax_amount INTEGER NOT NULL,
                        server_id INTEGER NOT NULL,
                        account_id INTEGER NOT NULL,
                        session_id UUID NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        UNIQUE(object_gid, batch_size, tax_amount, created_at, server_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_tax_lookup
                        ON tax_history (server_id, object_gid, batch_size);
                """)
                
                conn.commit()

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool with automatic return"""
        conn = self.pool.getconn()
        try:
            yield conn
        finally:
            self.pool.putconn(conn)
    
    def get_current_time(self) -> datetime:
        """Get current UTC time with timezone information"""
        return datetime.now(timezone.utc)

    def add_or_update_market(self,
                           market_type: int,
                           level_max: int,
                           map_id: int,
                           tax_percentage: int,
                           max_sell_slots: int,
                           accepted_resources: List[int],
                           npc_id: Optional[int] = None,
                           gfx_id: Optional[int] = None,
                           require_subscription: bool = False) -> Optional[int]:
        """Add or update market configuration"""
        with self._lock:
            current_time = self.get_current_time()
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        cur.execute("""
                            INSERT INTO markets (
                                market_type, level_max, map_id, npc_id, accepted_resources,
                                tax_percentage, max_sell_slots, gfx_id, require_subscription,
                                created_at, updated_at, last_time_opened
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                            )
                            ON CONFLICT (market_type, map_id) DO UPDATE SET
                                level_max = EXCLUDED.level_max,
                                npc_id = EXCLUDED.npc_id,
                                accepted_resources = EXCLUDED.accepted_resources,
                                tax_percentage = EXCLUDED.tax_percentage,
                                max_sell_slots = EXCLUDED.max_sell_slots,
                                gfx_id = EXCLUDED.gfx_id,
                                require_subscription = EXCLUDED.require_subscription,
                                updated_at = EXCLUDED.updated_at,
                                last_time_opened = EXCLUDED.last_time_opened
                            RETURNING id
                        """, (
                            market_type, level_max, map_id, npc_id, accepted_resources,
                            tax_percentage, max_sell_slots, gfx_id, require_subscription,
                            current_time, current_time, current_time
                        ))
                        
                        market_id = cur.fetchone()[0]
                        conn.commit()
                        return market_id
                        
                    except Exception as e:
                        self.logger.error(f"Database error in add_or_update_market: {e}")
                        conn.rollback()
                        return None

    def add_bids_bulk(self,
                    bids: List[Dict],
                    server_id: int,
                    account_id: int,
                    session_id: str) -> int:
        """
        Bulk insert multiple bids at once
        Returns number of successfully inserted bids
        """
        if not bids:
            return 0
            
        with self._lock:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        session_uuid = uuid.UUID(session_id)
                        current_time = self.get_current_time()
                        
                        # Prepare values for bulk insert
                        values = [(
                            bid['uid'],
                            server_id,
                            account_id,
                            session_uuid,
                            current_time,
                            bid['price'],
                            bid['item_gid'],
                            bid['quantity']
                        ) for bid in bids]
                        
                        # Bulk insert
                        cur.execute("""
                            INSERT INTO bids (
                                uid, server_id, account_id, session_id,
                                created_at, price, object_gid, batch_size
                            )
                            VALUES %s
                            ON CONFLICT (uid, server_id) DO NOTHING
                            RETURNING id
                        """, (psycopg2.extras.execute_values(cur, "VALUES %s", values, template=None, page_size=100)))
                        
                        result = cur.fetchall()
                        conn.commit()
                        return len(result)  # Number of successful inserts
                        
                    except Exception as e:
                        self.logger.error(f"Database error in add_bids_bulk: {e}")
                        conn.rollback()
                        return 0
                    
    def add_bid(self,
            uid: int,
            server_id: int,
            account_id: int,
            session_id: str,
            price: int,
            object_gid: int,
            batch_size: int) -> bool:
        """Add a new bid"""
        with self._lock:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        session_uuid = uuid.UUID(session_id)
                        cur.execute("""
                            INSERT INTO bids (
                                uid, server_id, account_id, session_id,
                                created_at, price, object_gid, batch_size
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s
                            )
                            ON CONFLICT (uid, server_id) DO NOTHING
                            RETURNING id
                        """, (
                            uid, server_id, account_id, session_uuid,
                            self.get_current_time(), price, object_gid, batch_size
                        ))
                        
                        result = cur.fetchone()
                        conn.commit()
                        return result is not None
                        
                    except Exception as e:
                        self.logger.error(f"Database error in add_bid: {e}")
                        conn.rollback()
                        return False

    def delete_bid(self, uid: int, server_id: int) -> bool:
        """Delete a bid by its unique identifier and server"""
        with self._lock:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        cur.execute("""
                            DELETE FROM bids 
                            WHERE uid = %s AND server_id = %s
                            RETURNING id
                        """, (uid, server_id))
                        
                        result = cur.fetchone()
                        conn.commit()
                        return result is not None
                        
                    except Exception as e:
                        self.logger.error(f"Database error in delete_bid: {e}")
                        conn.rollback()
                        return False

    def mark_bid_as_sold(self, server_id: int, object_gid: int, batch_size: int, price: int, sold_at: int) -> Optional[int]:
        """Mark oldest matching unsold bid as sold"""
        with self._lock:            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        cur.execute("""
                            UPDATE bids
                            SET sold_at = %s
                            WHERE id = (
                                SELECT id
                                FROM bids
                                WHERE server_id = %s
                                AND object_gid = %s
                                AND batch_size = %s
                                AND price = %s
                                AND sold_at IS NULL         # Only unsold bids
                                ORDER BY created_at ASC     # Oldest first
                                LIMIT 1                     # Take just the oldest one
                                FOR UPDATE                  # Lock the row
                            )
                            RETURNING uid
                        """, (sold_at, server_id, object_gid, batch_size, price))
                        
                        result = cur.fetchone()
                        conn.commit()
                        return result[0] if result else None
                        
                    except Exception as e:
                        self.logger.error(f"Database error in mark_bid_as_sold: {e}")
                        conn.rollback()
                        return None

    def record_tax_payment(self,
                          object_gid: int,
                          batch_size: int,
                          tax_amount: int,
                          server_id: int,
                          account_id: int,
                          session_id: int) -> bool:
        """Record a tax payment"""
        with self._lock:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        cur.execute("""
                            INSERT INTO tax_history (
                                object_gid, batch_size, tax_amount,
                                server_id, account_id, session_id, created_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (object_gid, batch_size, tax_amount, created_at, server_id) 
                            DO NOTHING
                            RETURNING id
                        """, (
                            object_gid, batch_size, tax_amount,
                            server_id, account_id, session_id,
                            self.get_current_time()
                        ))
                        
                        result = cur.fetchone()
                        conn.commit()
                        return result is not None
                        
                    except Exception as e:
                        self.logger.error(f"Database error in record_tax_payment: {e}")
                        conn.rollback()
                        return False

    def get_average_tax(self, object_gid: int, batch_size: int, server_id: int) -> Optional[float]:
        """Calculate average tax for item/quantity on a server"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("""
                        SELECT AVG(tax_amount)
                        FROM tax_history
                        WHERE object_gid = %s
                        AND batch_size = %s
                        AND server_id = %s
                    """, (object_gid, batch_size, server_id))
                    
                    result = cur.fetchone()
                    return float(result[0]) if result and result[0] else None
                    
                except Exception as e:
                    self.logger.error(f"Database error in get_average_tax: {e}")
                    return None

    def get_active_bids(self, server_id: int, session_id: Optional[int] = None) -> List[Dict]:
        """Get active (unsold) bids for a server, optionally filtered by session"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                try:
                    if session_id:
                        cur.execute("""
                            SELECT * FROM bids
                            WHERE server_id = %s
                            AND session_id = %s
                            AND sold_at IS NULL
                            ORDER BY created_at DESC
                        """, (server_id, session_id))
                    else:
                        cur.execute("""
                            SELECT * FROM bids
                            WHERE server_id = %s
                            AND sold_at IS NULL
                            ORDER BY created_at DESC
                        """, (server_id,))
                    
                    return cur.fetchall()
                    
                except Exception as e:
                    self.logger.error(f"Database error in get_active_bids: {e}")
                    return []

    def __del__(self):
        """Clean up connection pool on deletion"""
        if hasattr(self, 'pool'):
            self.pool.closeall()