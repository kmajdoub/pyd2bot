from sqlalchemy import create_engine, Column, Integer, String, JSON, UniqueConstraint, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from typing import Dict, List, Optional
import threading
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone

from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

Base = declarative_base()

class MapVertex(Base):
    __tablename__ = 'map_vertices'
    
    id = Column(Integer, primary_key=True)
    map_id = Column(Integer, nullable=False)
    zone_id = Column(Integer, nullable=False)
    vertex_uid = Column(String, nullable=False, unique=True)
    resource_counts = Column(JSON, nullable=False)  # Stores {resource_id: count}
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('map_id', 'zone_id', name='unique_map_zone'),
    )

class FarmSession(Base):
    __tablename__ = 'farm_sessions'
    
    id = Column(Integer, primary_key=True)
    path_id = Column(String, nullable=False, index=True)  # Identifier for the farm path
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    duration_seconds = Column(Float, nullable=False)
    resources_collected = Column(JSON, nullable=False)  # {resource_id: quantity}
    paused_at = Column(DateTime(timezone=True), nullable=True)  # Track when session was last paused

class ResourceTracker:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ResourceTracker, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, expiration_days: int = 30):
        if not hasattr(self, 'initialized'):
            db_path = Path('data/map_resources.db')
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.engine = create_engine(f'sqlite:///{db_path}')
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
            self.expiration_days = expiration_days
            self.initialized = True
            self.logger = Logger()
            self.active_sessions = {}  # Track session states

    def get_current_time(self) -> datetime:
        """Get current UTC time with timezone information."""
        return datetime.now(timezone.utc)
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            self.logger.error(f"Database error: {e}")
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_vertex_value(self, vertex_uid: str) -> Optional[int]:
        """
        Calculate the total economic value of resources in a vertex based on
        current average market prices.
        
        Args:
            vertex_uid: Unique identifier of the vertex
            
        Returns:
            int: Total value in kamas of all resources in the vertex
                 None if vertex not found or data expired
        """
        # Get resource counts using existing method
        resource_counts = self.get_vertex_resources(vertex_uid)
        if not resource_counts:
            return None
            
        total_value = 0
        price_frame = Kernel().averagePricesFrame
        
        # Calculate total value of all resources
        for resource_id_str, count in resource_counts.items():
            try:
                resource_id = int(resource_id_str)
                avg_price = price_frame.getItemAveragePrice(resource_id)
                if avg_price:  # Check if price exists
                    total_value += avg_price * count
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Error calculating value for resource {resource_id_str}: {e}")
                continue
                
        return total_value
    
    def update_vertex_resources(self, vertex, resource_ids: List[int]) -> bool:
        """
        Update or create a vertex entry with its resource counts.
        Optimized to minimize operations - only updates if entry doesn't exist
        or is expired.
        
        Args:
            vertex: Vertex object with mapId and zoneId attributes
            resource_ids: List of resource IDs found in the map
            
        Returns:
            bool: True if update was performed, False if skipped
        """
        with self._lock:
            with self.session_scope() as session:
                # First check if vertex exists and is not expired
                vertex_entry = session.query(MapVertex).filter_by(
                    vertex_uid=vertex.UID
                ).first()
                
                current_time = self.get_current_time()
                
                # If entry exists and is not expired, skip update
                if vertex_entry and not self.is_expired(vertex_entry):
                    self.logger.debug(f"Skipping update for non-expired vertex {vertex.UID}")
                    return False
                
                # Only count resources if we need to update
                resource_counts = {}
                for res_id in resource_ids:
                    resource_counts[str(res_id)] = resource_counts.get(str(res_id), 0) + 1
                
                if vertex_entry is None:
                    # Create new entry
                    vertex_entry = MapVertex(
                        map_id=vertex.mapId,
                        zone_id=vertex.zoneId,
                        vertex_uid=vertex.UID,
                        resource_counts=resource_counts,
                        created_at=current_time,
                        updated_at=current_time
                    )
                    session.add(vertex_entry)
                    self.logger.info(f"Added new vertex: {vertex.UID}")
                else:
                    # Update expired entry
                    vertex_entry.resource_counts = resource_counts
                    vertex_entry.updated_at = current_time
                    self.logger.debug(f"Updated expired vertex {vertex.UID}")
                
                return True
    
    def get_vertex_resources(self, vertex_uid: str, ignore_expiration: bool = False) -> Optional[Dict[str, int]]:
        """
        Get resource counts for a specific vertex.
        
        Args:
            vertex_uid: Unique identifier of the vertex
            ignore_expiration: If True, return data even if expired
            
        Returns:
            Dictionary of resource_id: count or None if vertex not found or data expired
        """
        with self.session_scope() as session:
            vertex_entry = session.query(MapVertex).filter_by(
                vertex_uid=vertex_uid
            ).first()
            
            if vertex_entry:
                if ignore_expiration or not self.is_expired(vertex_entry):
                    return vertex_entry.resource_counts
                self.logger.debug(f"Vertex {vertex_uid} data is expired")
                return None
            return None
    
    def is_expired(self, vertex_entry: MapVertex) -> bool:
        """Check if the vertex data is expired based on expiration_days setting."""
        expiration_date = self.get_current_time() - timedelta(days=self.expiration_days)
        return vertex_entry.updated_at < expiration_date
    
    def clean_expired_data(self):
        """Remove all expired vertex entries from the database."""
        with self._lock:
            with self.session_scope() as session:
                expiration_date = self.get_current_time() - timedelta(days=self.expiration_days)
                expired_count = session.query(MapVertex).filter(
                    MapVertex.updated_at < expiration_date
                ).delete()
                self.logger.info(f"Cleaned {expired_count} expired vertex entries")
    
    def get_recent_vertices(self, days: int = None) -> List[MapVertex]:
        """
        Get vertices updated within the specified number of days.
        
        Args:
            days: Number of days to look back (defaults to expiration_days if None)
        
        Returns:
            List of MapVertex objects
        """
        if days is None:
            days = self.expiration_days
            
        with self.session_scope() as session:
            cutoff_date = self.get_current_time() - timedelta(days=days)
            return session.query(MapVertex).filter(
                MapVertex.updated_at >= cutoff_date
            ).all()

    def start_farm_session(self, path_id: str) -> int:
        """Start tracking a new farming session."""
        with self._lock:
            with self.session_scope() as session:
                current_time = self.get_current_time()
                farm_session = FarmSession(
                    path_id=path_id,
                    start_time=current_time,
                    resources_collected={},
                    active_duration_seconds=0
                )
                session.add(farm_session)
                session.flush()  # Get the ID
                
                # Initialize session state
                self.active_sessions[farm_session.id] = {
                    'is_paused': False,
                    'last_pause_time': None,
                    'accumulated_duration': 0
                }
                
                return farm_session.id

    def end_farm_session(self, session_id: int, resources_collected: Dict[str, int]):
        """
        End a farming session. Only stores raw data without calculating values.
        
        Args:
            session_id: ID of the session to end
            resources_collected: Dictionary of {resource_id: quantity}
        """
        with self._lock:
            with self.session_scope() as session:
                farm_session = session.query(FarmSession).get(session_id)
                if not farm_session:
                    self.logger.error(f"Session {session_id} not found")
                    return
                
                end_time = self.get_current_time()
                duration = (end_time - farm_session.start_time).total_seconds()
                
                # Only store raw data
                farm_session.end_time = end_time
                farm_session.duration_seconds = duration
                farm_session.resources_collected = resources_collected
    
    def calculate_session_value(self, farm_session: FarmSession) -> int:
        """
        Calculate current value of a session based on current market prices.
        """
        total_value = 0
        price_frame = Kernel().averagePricesFrame
        
        for resource_id, quantity in farm_session.resources_collected.items():
            avg_price = price_frame.getItemAveragePrice(int(resource_id))
            if avg_price:
                total_value += avg_price * quantity
                
        return total_value
    
    def get_path_statistics(self, path_id: str, days: Optional[int] = None) -> Dict:
        """
        Get detailed statistics for a farming path using current market prices.
        """
        with self.session_scope() as session:
            query = session.query(FarmSession).filter(FarmSession.path_id == path_id)
            
            if days is not None:
                cutoff = self.get_current_time() - timedelta(days=days)
                query = query.filter(FarmSession.end_time >= cutoff)
            
            sessions = query.all()
            
            if not sessions:
                return None
            
            # Initialize statistics
            total_duration = sum(s.duration_seconds for s in sessions)
            total_value = sum(self.calculate_session_value(s) for s in sessions)
            
            # Aggregate resource counts
            resource_totals = {}
            for s in sessions:
                for res_id, qty in s.resources_collected.items():
                    resource_totals[res_id] = resource_totals.get(res_id, 0) + qty
            
            # Calculate hourly rates based on current prices
            hours = total_duration / 3600
            value_per_hour = total_value / hours if hours > 0 else 0
            
            # Calculate current value per resource
            price_frame = Kernel().averagePricesFrame
            resource_values = []
            for res_id, qty in resource_totals.items():
                avg_price = price_frame.getItemAveragePrice(int(res_id))
                if avg_price:
                    total_res_value = avg_price * qty
                    resource_values.append({
                        'resource_id': res_id,
                        'quantity': qty,
                        'current_value': total_res_value,
                        'value_per_hour': total_res_value / hours if hours > 0 else 0
                    })
            
            return {
                'total_sessions': len(sessions),
                'total_duration_hours': hours,
                'current_total_value': total_value,  # Renamed to emphasize this is current value
                'current_value_per_hour': value_per_hour,  # Renamed to emphasize this is current value
                'resources_per_hour': {
                    res_id: qty / hours if hours > 0 else 0
                    for res_id, qty in resource_totals.items()
                },
                'resource_statistics': sorted(
                    resource_values,
                    key=lambda x: x['current_value'],
                    reverse=True
                )
            }

    def pause_session(self, session_id: int):
        """
        Pause time tracking for a session (e.g., during inventory management)
        """
        with self._lock:
            session_state = self.active_sessions.get(session_id)
            if not session_state or session_state['is_paused']:
                return
            
            current_time = self.get_current_time()
            with self.session_scope() as session:
                farm_session = session.query(FarmSession).get(session_id)
                if farm_session:
                    farm_session.paused_at = current_time
                    # Calculate and update active duration up to this point
                    if not session_state['last_pause_time']:  # If this is first pause
                        active_duration = (current_time - farm_session.start_time).total_seconds()
                    else:
                        active_duration = (current_time - session_state['last_pause_time']).total_seconds()
                    
                    farm_session.active_duration_seconds += active_duration
                    session_state['accumulated_duration'] = farm_session.active_duration_seconds
                    
            session_state['is_paused'] = True
            session_state['last_pause_time'] = current_time

    def resume_session(self, session_id: int):
        """
        Resume time tracking for a session
        """
        with self._lock:
            session_state = self.active_sessions.get(session_id)
            if not session_state or not session_state['is_paused']:
                return
            
            current_time = self.get_current_time()
            session_state['is_paused'] = False
            session_state['last_pause_time'] = current_time

# Usage example in ResourceFarm class:
"""
class ResourceFarm(AbstractFarmBehavior):
    def __init__(self, path: AbstractFarmPath, jobFilters: List[JobFilter], timeout=None):
        super().__init__(timeout)
        self.jobFilters = jobFilters
        self.path = path
        self.deadEnds = set()
        # Initialize with custom expiration (e.g., 15 days)
        self.resource_tracker = ResourceTracker(expiration_days=15)

    def getAvailableResources(self) -> list[CollectableResource]:
        if not Kernel().interactiveFrame:
            Logger().error("No interactive frame found")
            return None
            
        collectables = Kernel().interactiveFrame.collectables.values()
        
        # Track resources for current vertex
        current_vertex = PlayedCharacterManager().currVertex
        resources_ids = [it.skill.gatheredRessource.id for it in collectables]
        self.resource_tracker.update_vertex_resources(current_vertex, resources_ids)
        
        # Periodically clean expired data (could be moved to a maintenance task)
        if random.random() < 0.01:  # 1% chance to clean on each call
            self.resource_tracker.clean_expired_data()
        
        collectableResources = [CollectableResource(it) for it in collectables]
        return collectableResources
"""