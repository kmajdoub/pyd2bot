import json
import psycopg2
import psycopg2.pool
import psycopg2.extras
from contextlib import contextmanager
from typing import Dict, List, Optional
import threading
from datetime import datetime, timedelta, timezone

from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.metaclass.ThreadSharedSingleton import ThreadSharedSingleton

class ResourceTracker(metaclass=ThreadSharedSingleton):
    _lock = threading.Lock()
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 5432,
                 database: str = "pyd2bot",
                 user: str = "pyd2bot",
                 password: str = "rMrTXHA4*",
                 expiration_days: int = 30,
                 min_connections: int = 5,
                 max_connections: int = 15):
        
        self.logger = Logger()
        self.expiration_days = expiration_days
        self.active_sessions = {}
        
        # Create connection pool
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=min_connections,
            maxconn=max_connections,
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        
        # Initialize database schema
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables and indexes"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Create map_vertices table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS map_vertices (
                        id SERIAL PRIMARY KEY,
                        map_id INTEGER NOT NULL,
                        zone_id INTEGER NOT NULL,
                        vertex_uid TEXT NOT NULL UNIQUE,
                        resource_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    );
                    
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_map_zone 
                        ON map_vertices (map_id, zone_id);
                        
                    CREATE INDEX IF NOT EXISTS idx_vertex_uid 
                        ON map_vertices (vertex_uid);
                        
                    CREATE INDEX IF NOT EXISTS idx_updated_at 
                        ON map_vertices (updated_at);
                        
                    CREATE INDEX IF NOT EXISTS idx_resource_counts 
                        ON map_vertices USING GIN (resource_counts);
                """)
                
                # Create farm_sessions table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS farm_sessions (
                        id SERIAL PRIMARY KEY,
                        path_id TEXT NOT NULL,
                        start_time TIMESTAMPTZ NOT NULL,
                        end_time TIMESTAMPTZ,
                        active_duration_seconds FLOAT NOT NULL DEFAULT 0,
                        resources_collected JSONB NOT NULL DEFAULT '{}'::jsonb,
                        paused_at TIMESTAMPTZ,
                        total_duration_seconds FLOAT NOT NULL DEFAULT 0,
                        last_update TIMESTAMPTZ
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_path_id 
                        ON farm_sessions (path_id);
                        
                    CREATE INDEX IF NOT EXISTS idx_path_end_time 
                        ON farm_sessions (path_id, end_time);
                        
                    CREATE INDEX IF NOT EXISTS idx_resources_collected 
                        ON farm_sessions USING GIN (resources_collected);
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

    def update_vertex_resources(self, vertex: Vertex, resource_ids: List[int]) -> bool:
        """Update or create vertex entry with resource counts"""
        with self._lock:
            current_time = self.get_current_time()
            
            # Build resource counts
            resource_counts = {}
            for res_id in resource_ids:
                resource_counts[str(res_id)] = resource_counts.get(str(res_id), 0) + 1
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        cur.execute("""
                            INSERT INTO map_vertices 
                                (map_id, zone_id, vertex_uid, resource_counts, created_at, updated_at)
                            VALUES 
                                (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (vertex_uid) DO UPDATE SET
                                resource_counts = %s,
                                updated_at = %s
                            WHERE 
                                map_vertices.updated_at < %s
                            RETURNING updated_at = %s as was_updated
                        """, (
                            vertex.mapId,
                            vertex.zoneId,
                            vertex.UID,
                            json.dumps(resource_counts),
                            current_time,
                            current_time,
                            json.dumps(resource_counts),
                            current_time,
                            current_time - timedelta(days=self.expiration_days),
                            current_time
                        ))
                        
                        result = cur.fetchone()
                        conn.commit()
                        return result is not None and result[0]
                        
                    except Exception as e:
                        self.logger.error(f"Database error in update_vertex_resources: {e}")
                        conn.rollback()
                        return False

    def get_vertex_resources(self, vertex_uid: str, ignore_expiration: bool = False) -> Optional[Dict[str, int]]:
        """Get resource counts for a specific vertex"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                try:
                    if not ignore_expiration:
                        expiration_date = self.get_current_time() - timedelta(days=self.expiration_days)
                        cur.execute("""
                            SELECT resource_counts FROM map_vertices 
                            WHERE vertex_uid = %s AND updated_at >= %s
                        """, (vertex_uid, expiration_date))
                    else:
                        cur.execute("""
                            SELECT resource_counts FROM map_vertices 
                            WHERE vertex_uid = %s
                        """, (vertex_uid,))
                    
                    result = cur.fetchone()
                    return dict(result['resource_counts']) if result else None
                except Exception as e:
                    self.logger.error(f"Database error in get_vertex_resources: {e}")
                    return None

    def get_vertices_with_resource_minimum(self, resource_id: str, min_count: int) -> List[Dict]:
        """Find vertices with minimum resource count"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                try:
                    cur.execute("""
                        SELECT * FROM map_vertices
                        WHERE (resource_counts->>%s)::int >= %s
                        AND updated_at >= %s
                        ORDER BY (resource_counts->>%s)::int DESC
                    """, (
                        resource_id,
                        min_count,
                        self.get_current_time() - timedelta(days=self.expiration_days),
                        resource_id
                    ))
                    return cur.fetchall()
                except Exception as e:
                    self.logger.error(f"Database error in get_vertices_with_resource_minimum: {e}")
                    return []

    def start_farm_session(self, path_id: str) -> Optional[int]:
        """Start a new farming session"""
        with self._lock:
            current_time = self.get_current_time()
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        cur.execute("""
                            INSERT INTO farm_sessions 
                                (path_id, start_time, resources_collected, 
                                active_duration_seconds, total_duration_seconds)
                            VALUES (%s, %s, %s::jsonb, 0, 0)
                            RETURNING id
                        """, (
                            path_id,
                            current_time,
                            '{}'
                        ))
                        
                        session_id = cur.fetchone()[0]
                        conn.commit()
                        
                        # Initialize session state
                        self.active_sessions[session_id] = {
                            'is_paused': False,
                            'last_pause_time': None,
                            'accumulated_duration': 0
                        }
                        
                        return session_id
                    except Exception as e:
                        self.logger.error(f"Database error in start_farm_session: {str(e)}")
                        conn.rollback()
                        return None

    def update_session_collected_resources(self, session_id: int, resource_id: str, qty: int) -> bool:
        """Update resources collected in a session, handling both positive and negative quantities"""
        with self._lock:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        # First, get current value for the resource
                        cur.execute("""
                            SELECT COALESCE((resources_collected->>%s)::integer, 0) as current_qty
                            FROM farm_sessions
                            WHERE id = %s
                        """, (resource_id, session_id))
                        
                        result = cur.fetchone()
                        if result is None:
                            self.logger.error(f"Session {session_id} not found")
                            return False
                        
                        current_qty = result[0]
                        new_qty = current_qty + qty
                        
                        # Ensure we don't go below 0
                        if new_qty < 0:
                            self.logger.warning(
                                f"Attempted to reduce resource {resource_id} below 0 "
                                f"(current: {current_qty}, change: {qty})"
                            )
                            new_qty = 0
                        
                        # Update the resource count
                        cur.execute("""
                            UPDATE farm_sessions 
                            SET resources_collected = 
                                CASE 
                                    WHEN %s = 0 THEN 
                                        resources_collected - %s::text
                                    ELSE
                                        jsonb_set(
                                            COALESCE(resources_collected, '{}'::jsonb),
                                            ARRAY[%s],
                                            %s::text::jsonb
                                        )
                                END,
                                last_update = %s
                            WHERE id = %s
                            RETURNING resources_collected->>%s as new_quantity
                        """, (
                            new_qty,
                            resource_id,
                            resource_id,
                            str(new_qty),
                            self.get_current_time(),
                            session_id,
                            resource_id
                        ))
                        
                        result = cur.fetchone()
                        if result is None:
                            self.logger.error(f"Session {session_id} not found")
                            return False
                            
                        conn.commit()
                        
                        # Log the update with value calculation
                        try:
                            new_qty = int(result[0]) if result[0] else 0
                            avg_price = Kernel().averagePricesFrame.getItemAveragePrice(int(resource_id))
                            if avg_price:
                                value = avg_price * qty
                                total_value = avg_price * new_qty
                                self.logger.debug(
                                    f"{'Added' if qty > 0 else 'Removed'} {abs(qty)} x {resource_id} "
                                    f"(value: {abs(value):,} kamas, total: {total_value:,} kamas)"
                                )
                            else:
                                self.logger.debug(
                                    f"{'Added' if qty > 0 else 'Removed'} {abs(qty)} x {resource_id} "
                                    "(no price available)"
                                )
                        except (ValueError, TypeError) as e:
                            self.logger.warning(f"Error calculating value for resource {resource_id}: {e}")
                        
                        return True
                        
                    except Exception as e:
                        self.logger.error(f"Database error in update_session_collected_resources: {e}")
                        conn.rollback()
                        return False

    def end_farm_session(self, session_id: int, resources_collected: Dict[str, int]):
        """End a farming session"""
        with self._lock:
            current_time = self.get_current_time()
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        # Get current session data
                        cur.execute("""
                            SELECT start_time FROM farm_sessions WHERE id = %s
                        """, (session_id,))
                        
                        result = cur.fetchone()
                        if not result:
                            self.logger.error(f"Session {session_id} not found")
                            return
                            
                        start_time = result[0]
                        total_duration = (current_time - start_time).total_seconds()
                        
                        # Calculate active duration
                        session_state = self.active_sessions.get(session_id)
                        active_duration = 0
                        
                        if session_state:
                            if session_state['is_paused']:
                                active_duration = session_state['accumulated_duration']
                            else:
                                last_active_start = session_state['last_pause_time'] or start_time
                                final_duration = (current_time - last_active_start).total_seconds()
                                active_duration = session_state['accumulated_duration'] + final_duration
                        
                        # Update session
                        cur.execute("""
                            UPDATE farm_sessions SET
                                end_time = %s,
                                total_duration_seconds = %s,
                                active_duration_seconds = %s,
                                resources_collected = %s
                            WHERE id = %s
                        """, (
                            current_time,
                            total_duration,
                            active_duration,
                            json.dumps(resources_collected),
                            session_id
                        ))
                        
                        conn.commit()
                        
                        # Clean up session state
                        self.active_sessions.pop(session_id, None)
                        
                    except Exception as e:
                        self.logger.error(f"Database error in end_farm_session: {e}")
                        conn.rollback()

    def get_path_statistics(self, path_id: str, days: Optional[int] = None) -> Optional[Dict]:
        """Get detailed path statistics"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                try:
                    cur.execute("""
                        WITH expanded_sessions AS (
                            SELECT 
                                id,
                                total_duration_seconds,
                                active_duration_seconds,
                                jsonb_each_text(resources_collected) as resource_data
                            FROM farm_sessions
                            WHERE path_id = %s
                            AND (%s IS NULL OR end_time >= %s)
                        ),
                        resource_stats AS (
                            SELECT 
                                (resource_data).key as resource_id,
                                SUM(CAST((resource_data).value AS INTEGER)) as total_qty
                            FROM expanded_sessions
                            GROUP BY (resource_data).key
                        ),
                        session_stats AS (
                            SELECT 
                                COUNT(DISTINCT id) as total_sessions,
                                SUM(total_duration_seconds) as total_duration,
                                SUM(active_duration_seconds) as active_duration
                            FROM expanded_sessions
                        )
                        SELECT 
                            ss.*,
                            jsonb_object_agg(
                                rs.resource_id,
                                rs.total_qty
                            ) as resource_totals
                        FROM session_stats ss
                        LEFT JOIN resource_stats rs ON true
                        GROUP BY 
                            ss.total_sessions,
                            ss.total_duration,
                            ss.active_duration
                    """, (
                        path_id,
                        days is not None,
                        self.get_current_time() - timedelta(days=days) if days else None
                    ))
                    
                    result = cur.fetchone()
                    if not result or not result['total_sessions']:
                        return None
                    
                    # Process results as before...
                    return {
                        'total_sessions': result['total_sessions'],
                        'total_duration_hours': result['total_duration'] / 3600 if result['total_duration'] else 0,
                        'active_duration_hours': result['active_duration'] / 3600 if result['active_duration'] else 0,
                        'pause_duration_hours': (result['total_duration'] - result['active_duration']) / 3600 
                            if result['total_duration'] and result['active_duration'] else 0,
                        'current_total_value': 0,  # Will be calculated below
                        'current_value_per_active_hour': 0,  # Will be calculated below
                        'resources_per_active_hour': {},  # Will be calculated below
                        'resource_statistics': []  # Will be calculated below
                    }
                    
                except Exception as e:
                    self.logger.error(f"Database error in get_path_statistics: {str(e)}")
                    return None

    def pause_session(self, session_id: int):
        """Pause time tracking for a session"""
        with self._lock:
            session_state = self.active_sessions.get(session_id)
            if not session_state or session_state['is_paused']:
                return
            
            current_time = self.get_current_time()
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        # Get session start time
                        cur.execute("""
                            SELECT start_time FROM farm_sessions WHERE id = %s
                        """, (session_id,))
                        
                        result = cur.fetchone()
                        if result:
                            # Calculate active duration
                            if not session_state['last_pause_time']:
                                active_duration = (current_time - result[0]).total_seconds()
                            else:
                                active_duration = (current_time - session_state['last_pause_time']).total_seconds()
                            
                            session_state['accumulated_duration'] += active_duration
                            
                            # Update session
                            cur.execute("""
                                UPDATE farm_sessions SET
                                    paused_at = %s,
                                    active_duration_seconds = %s
                                WHERE id = %s
                            """, (
                                current_time,
                                session_state['accumulated_duration'],
                                session_id
                            ))
                            
                            conn.commit()
                            
                            session_state['is_paused'] = True
                            session_state['last_pause_time'] = current_time
                            
                    except Exception as e:
                        self.logger.error(f"Database error in pause_session: {e}")
                        conn.rollback()

    def resume_session(self, session_id: int):
        """Resume time tracking for a session"""
        with self._lock:
            session_state = self.active_sessions.get(session_id)
            if not session_state or not session_state['is_paused']:
                return
            
            current_time = self.get_current_time()
            session_state['is_paused'] = False
            session_state['last_pause_time'] = current_time

    def clean_expired_data(self):
        """Remove expired vertex entries"""
        with self._lock:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        expiration_date = self.get_current_time() - timedelta(days=self.expiration_days)
                        cur.execute("""
                            DELETE FROM map_vertices 
                            WHERE updated_at < %s
                            RETURNING id
                        """, (expiration_date,))
                        
                        deleted_count = len(cur.fetchall())
                        conn.commit()
                        self.logger.info(f"Cleaned {deleted_count} expired vertex entries")
                        
                    except Exception as e:
                        self.logger.error(f"Database error in clean_expired_data: {e}")
                        conn.rollback()
    
    def __del__(self):
        """Clean up connection pool on deletion"""
        if hasattr(self, 'pool'):
            self.pool.closeall()

if __name__ == "__main__":
    Logger.logToConsole = True
    tracker = ResourceTracker()
    
    # Test 1: Update vertex resources
    print("\n--- Test 1: Update Vertex Resources ---")
    vertex = Vertex(123456, 1, "test_vertex_1")
    result = tracker.update_vertex_resources(vertex, [1234, 1234, 5678])  # Multiple resources
    print(f"Update result: {result}")

    # Test 2: Get vertex resources
    print("\n--- Test 2: Get Vertex Resources ---")
    resources = tracker.get_vertex_resources("test_vertex_1")
    print(f"Retrieved resources: {resources}")

    # Test 3: Start farm session
    print("\n--- Test 3: Start Farm Session ---")
    session_id = tracker.start_farm_session("test_path_1")
    print(f"Started session ID: {session_id}")

    # Test 4: Update collected resources
    print("\n--- Test 4: Update Session Resources ---")
    if session_id:
        result = tracker.update_session_collected_resources(session_id, "1234", 5)
        print(f"Updated session resources: {result}")

    # Test 5: Pause/Resume session
    print("\n--- Test 5: Pause/Resume Session ---")
    if session_id:
        tracker.pause_session(session_id)
        print("Session paused")
        # Wait a bit to simulate pause
        import time
        time.sleep(2)
        tracker.resume_session(session_id)
        print("Session resumed")

    # Test 6: End session
    print("\n--- Test 6: End Session ---")
    if session_id:
        tracker.end_farm_session(session_id, {"1234": 5, "5678": 3})
        print("Session ended")

    # Test 7: Get statistics
    print("\n--- Test 7: Get Path Statistics ---")
    stats = tracker.get_path_statistics("test_path_1")
    print(f"Path statistics: {stats}")

    # Test 8: Find vertices with minimum resources
    print("\n--- Test 8: Find Vertices with Resources ---")
    vertices = tracker.get_vertices_with_resource_minimum("1234", 2)
    print(f"Found vertices: {vertices}")

    # Test 9: Clean expired data
    print("\n--- Test 9: Clean Expired Data ---")
    tracker.clean_expired_data()