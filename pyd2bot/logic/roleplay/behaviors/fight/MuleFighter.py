from time import perf_counter
from typing import Optional
from dataclasses import dataclass

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.misc.BotEventsManager import BotEventsManager
from pyd2bot.data.models import Character
from pydofus2.com.ankamagames.berilia.managers.EventsHandler import Event, Listener
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.Vertex import Vertex
from pydofus2.com.ankamagames.dofus.network.messages.game.context.fight.GameFightJoinRequestMessage import GameFightJoinRequestMessage
from pydofus2.com.ankamagames.dofus.network.types.game.context.fight.FightCommonInformations import FightCommonInformations
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint

@dataclass
class FightAttempt:
    """Track fight join attempts and cooldowns"""
    fight_id: int
    leader_id: int
    attempt_count: int = 0
    last_attempt: float = 0
    is_joining: bool = False

class MuleFighter(AbstractBehavior):
    """Improved MuleFighter behavior with better fight detection and retry logic"""
    
    FIGHT_JOIN_TIMEOUT = 3
    MAX_JOIN_ATTEMPTS = 3
    JOIN_RETRY_DELAY = 2
    MOVE_RETRY_DELAY = 1
    
    def __init__(self, leader: Character):
        super().__init__()
        self.leader = leader
        self.current_fight: Optional[FightAttempt] = None
        self.is_moving = False
        self._reset_state()

    def _reset_state(self):
        """Reset internal state variables"""
        self.current_fight = None
        self.is_moving = False
        self.join_fight_listener = None

    def run(self):
        """Initialize behavior and set up event listeners"""
        Logger().info(f"Starting mule fighter following leader {self.leader.name} ({self.leader.id})")
        
        # Core event listeners
        self.on(KernelEvent.FightSwordShowed, self._on_fight_detected)
        self.on(KernelEvent.ServerTextInfo, self._on_server_notification)
        self.on(KernelEvent.FightEnded, self._on_fight_ended)
        self.on(KernelEvent.RoleplayStarted, lambda _: self._check_player_state())
        
        # Movement handling
        BotEventsManager().on(
            BotEventsManager.MOVE_TO_VERTEX, 
            self._on_move_to_vertex_request, 
            originator=self
        )
        
        # Initial state check
        self._check_player_state()
        
    def _check_player_state(self):
        """Verify player state and handle revival if needed"""
        if PlayedCharacterManager().isDead():
            Logger().warning("Mule is dead, initiating revival sequence")
            self.autoRevive(callback=self._on_revival_complete)

    def _on_revival_complete(self, code, error):
        """Handle revival completion"""
        if error:
            Logger().error(f"Revival failed with error {error}")
            KernelEventsManager().send(
                KernelEvent.ClientShutdown, 
                f"Failed to revive character: Error[{code}] - {error}"
            )
            return
            
        Logger().info("Revival successful, resuming mule fighter operations")
        self._reset_state()

    def _on_bank_unload_complete(self, code, err):
        if err:
            return self.finish(code, f"Error while unloading: {err}")

    def _check_inventory_status(self, *args):
        """Check inventory status and initiate unload if needed"""        
        if PlayedCharacterManager().isPodsFull():
            Logger().warning("Inventory is full, initiating bank unload sequence...")
            return self.unloadInBank(callback=self._on_bank_unload_complete)

    def _on_fight_detected(self, event: Event, fight_info: FightCommonInformations):
        """Handle new fight detection with improved validation"""
        if self.current_fight and self.current_fight.is_joining:
            Logger().debug("Already attempting to join a fight, ignoring new fight")
            return

        # Validate fight teams
        leader_team = None
        for team in fight_info.fightTeams:
            if team.leaderId == self.leader.id:
                leader_team = team
                break
                
        if not leader_team:
            Logger().debug(f"Fight {fight_info.fightId} does not involve leader {self.leader.id}")
            return

        Logger().info(f"Leader fight detected - ID: {fight_info.fightId}, Leader: {self.leader.id}")
        self.current_fight = FightAttempt(
            fight_id=fight_info.fightId,
            leader_id=self.leader.id
        )
        self._attempt_join_fight()

    def _attempt_join_fight(self):
        """Attempt to join fight with retry logic"""
        if not self.current_fight:
            Logger().warning("No active fight to join")
            return
            
        if self.current_fight.attempt_count >= self.MAX_JOIN_ATTEMPTS:
            Logger().warning(f"Max join attempts ({self.MAX_JOIN_ATTEMPTS}) reached for fight {self.current_fight.fight_id}")
            self._reset_state()
            return

        current_time = perf_counter()
        if (current_time - self.current_fight.last_attempt) < self.JOIN_RETRY_DELAY:
            Logger().debug("Waiting for join cooldown")
            return

        self.current_fight.attempt_count += 1
        self.current_fight.last_attempt = current_time
        self.current_fight.is_joining = True

        Logger().info(f"Attempting to join fight {self.current_fight.fight_id} (Attempt {self.current_fight.attempt_count}/{self.MAX_JOIN_ATTEMPTS})")
        
        # Set up join fight listener with timeout
        self.join_fight_listener = KernelEventsManager().once(
            KernelEvent.FightStarted,
            self._on_fight_joined,
            timeout=self.FIGHT_JOIN_TIMEOUT,
            ontimeout=self._on_join_timeout,
            originator=self
        )

        # Send join request
        join_msg = GameFightJoinRequestMessage()
        join_msg.init(self.current_fight.leader_id, self.current_fight.fight_id)
        ConnectionsHandler().send(join_msg)

    def _on_fight_joined(self, event):
        """Handle successful fight join"""
        Logger().info("Successfully joined leader's fight")
        if self.current_fight:
            self.current_fight.is_joining = False
        if self.join_fight_listener:
            self.join_fight_listener.delete()

    def _on_join_timeout(self, listener: Listener):
        """Handle fight join timeout"""
        Logger().warning(f"Join fight request timed out (Attempt {self.current_fight.attempt_count if self.current_fight else 'Unknown'})")
        
        if self.current_fight:
            self.current_fight.is_joining = False
            Kernel().worker.terminated.wait(self.JOIN_RETRY_DELAY)
            self._attempt_join_fight()

    def _on_server_notification(self, event, msgId, msgType, textId, text, params):
        """Handle server notifications, particularly join delays"""
        if textId != 773221:  # Fight join delay notification
            return

        if self.join_fight_listener:
            self.join_fight_listener.delete()

        delay = int(params[0])
        Logger().info(f"Server enforced wait time of {delay}s before joining fight")
        
        # Try to move to an adjacent cell while waiting
        self._attempt_position_adjustment(delay)

    def _attempt_position_adjustment(self, wait_time: float):
        """Try to move to adjacent cells while waiting to join"""
        current_cell = MapPoint.fromCellId(PlayedCharacterManager().currentCellId)
        adjacent_cells = list(current_cell.iterChildren(False))
        
        if not adjacent_cells:
            Logger().debug("No adjacent cells available for movement")
            self._schedule_delayed_join(wait_time)
            return

        def try_next_cell(remaining_cells):
            if not remaining_cells:
                Logger().debug("No more cells to try")
                self._schedule_delayed_join(wait_time)
                return

            target_cell = MapPoint.fromCoords(*remaining_cells[0])
            
            def on_move_complete(code, err, _):
                if err:
                    Logger().debug(f"Failed to move to cell: {err}")
                    try_next_cell(remaining_cells[1:])
                    return
                self._attempt_join_fight()

            self.mapMove(
                target_cell.cellId,
                callback=on_move_complete
            )

        try_next_cell(adjacent_cells)

    def _schedule_delayed_join(self, delay: float):
        """Schedule a delayed fight join attempt"""
        remaining = max(0, delay - (perf_counter() - (self.current_fight.last_attempt if self.current_fight else 0)))
        if remaining > 0:
            Kernel().worker.terminated.wait(remaining)
        self._attempt_join_fight()

    def _on_fight_ended(self, event):
        """Handle fight end"""
        Logger().debug("Fight ended, resetting state and checking status")
        self._reset_state()
        self.once(
            KernelEvent.RoleplayStarted,
            lambda e: self.onceMapProcessed(self._check_player_state)
        )

    def _on_move_to_vertex_request(self, event: Event, vertex: Vertex):
        """Handle movement requests with improved validation"""
        Logger().info(f"Received move request to vertex {vertex}")

        if self.is_moving:
            Logger().debug("Already processing a move request")
            return

        if PlayedCharacterManager().isDead():
            Logger().warning("Cannot move while dead, initiating revival")
            self.autoRevive(lambda code, err: self._on_revival_complete(code, err))
            return

        # Check for blocking behaviors
        blocking_behaviors = [b for b in self.getOtherRunningBehaviors() if not b.IS_BACKGROUND_TASK]
        if blocking_behaviors:
            Logger().warning(f"Movement blocked by active behaviors: {blocking_behaviors}")
            return

        self.is_moving = True
        curr_vertex = PlayedCharacterManager().currVertex

        if not curr_vertex:
            Logger().error("Current vertex unknown, waiting for map processing")
            self.onceMapProcessed(lambda: self._on_move_to_vertex_request(event, vertex))
            return

        if curr_vertex.UID == vertex.UID:
            Logger().info("Already at destination vertex")
            self.is_moving = False
            return

        self.travelUsingZaap(
            vertex.mapId,
            vertex.zoneId,
            callback=self._on_movement_complete
        )

    def _on_movement_complete(self, code, error):
        """Handle movement completion"""
        self.is_moving = False
        if error:
            Logger().error(f"Movement failed: {error}")
            return
        Logger().info("Movement completed successfully")

    def stop(self):
        """Clean shutdown of the behavior"""
        self._reset_state()
        super().finish(True, None)
