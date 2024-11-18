from enum import Enum, auto
from typing import Optional
from pyd2bot.logic.fight.behaviors.FightStateManager import FightStateManager
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InactivityManager import InactivityManager
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameMapMovementRequestMessage import GameMapMovementRequestMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.positions.MovementPath import MovementPath
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
    
class FightMoveBehavior(AbstractBehavior):
    MAX_RETRIES = 3

    class errors(Enum):
        NO_FIGHTER_POS = auto()
        PATH_BLOCKED = auto()
        INSUFFICIENT_MP = auto()
        MOVEMENT_FAILED = auto()
        INVALID_PATH = auto()
        MAX_RETRIES_EXCEEDED = auto()

    def __init__(self, path_cells: list[int]):
        """Initialize the FightMove behavior"""
        super().__init__()
        self.path_cells = path_cells
        self.path = self.create_move_path()
        self._movement_request_sent = False
        self._retry_count = 0
        self.state_manager = FightStateManager()

    def run(self) -> bool:
        """Start the movement behavior"""
        self.once(KernelEvent.FightMovementFailed, self.on_movement_failed)
        self.on(KernelEvent.FighterMovementApplied, self.on_fighter_moved)
        self.on(KernelEvent.ServerTextInfo, self._handle_server_info)    
        self.move_to_cell()
        return True

    def _handle_server_info(self, event, msgId, msgType, textId, text, params):
        """Handle server info messages"""
        if textId == 4993:  # Movement points exceeded
            Logger().warning("Not enough movement points")
            self.finish(self.errors.INSUFFICIENT_MP, "Not enough movement points")

        elif textId == 4897:  # Path blocked
            Logger().warning("Movement blocked by obstacle")
            current_pos = self.state_manager.fighter_pos
            if current_pos:
                blocked_cell = self._identify_blocked_cell(current_pos.cellId)
                infos = {
                    "stopped_at": current_pos.cellId,
                    "blocked_cell": blocked_cell
                }
                self.finish(self.errors.PATH_BLOCKED, "Path blocked by obstacle", infos)
            else:
                self.finish(self.errors.PATH_BLOCKED, "Path blocked but position unknown")

    def _identify_blocked_cell(self, current_cell: int) -> Optional[int]:
        """Identify which cell is likely blocked based on where movement stopped"""
        try:
            current_idx = self.path_cells.index(current_cell)
            if current_idx < len(self.path_cells) - 1:
                return self.path_cells[current_idx + 1]  # Next cell in path is blocked
        except ValueError:
            Logger().error(f"Current cell {current_cell} not found in path")
        return None

    def create_move_path(self) -> MovementPath:
        """Create movement path from cell list"""
        path = MovementPath()
        path.fillFromCellIds(self.path_cells[:-1])
        path.end = MapPoint.fromCellId(self.path_cells[-1])
        
        if len(path.path) > 0:
            path.path[-1].orientation = path.path[-1].step.orientationTo(path.end)
        return path

    def send_move_request(self) -> None:
        """Send movement request to server"""
        if self._movement_request_sent:
            Logger().warning("Movement request already sent to server")
            return
            
        message = GameMapMovementRequestMessage()
        message.init(self.path.keyMoves(), PlayedCharacterManager().currentMap.mapId)
        self.state_manager.connection.send(message)
        InactivityManager().activity()
        self._movement_request_sent = True
        
    def move_to_cell(self) -> None:
        """Execute the movement along the specified path"""
        if not self.state_manager.fighter_pos:
            Logger().error("Cannot move: fighter position not found")
            self.finish(self.errors.NO_FIGHTER_POS, "Fighter position not found")
            return

        if not self.path_cells:
            Logger().error("Invalid path: empty cell list")
            self.finish(self.errors.INVALID_PATH, "Empty path provided")
            return

        Logger().info(f"Moving along path: {self.path_cells}")
        self.send_move_request()

    def retry_movement(self) -> None:
        """Attempt to retry the movement after a failure"""
        self._retry_count += 1
        self._movement_request_sent = False
        
        if self._retry_count >= self.MAX_RETRIES:
            Logger().error(f"Movement failed after {self._retry_count} attempts, ending turn")
            self.finish(self.errors.MAX_RETRIES_EXCEEDED, f"Movement failed after {self.MAX_RETRIES} attempts")
            return
            
        Logger().info(f"Retrying movement (attempt {self._retry_count + 1}/{self.MAX_RETRIES})")
        self.move_to_cell()
        
    def on_fighter_moved(self, event, moved_fighter_id, move_path: MovementPath) -> None:
        """Handle fighter movement event"""
        if moved_fighter_id == self.state_manager.current_player.id:
            event.listener.delete()
            self.on_movement_applied(move_path)
        
    def on_movement_applied(self, actual_path: MovementPath) -> None:
        """Handle movement completion"""
        if not self._movement_request_sent:
            return
            
        Logger().info(f"Movement applied, landed on cell {self.state_manager.fighter_pos.cellId}")
        self._movement_request_sent = False
        
        if actual_path.end.cellId != self.path.end.cellId:
            Logger().warning("Movement failed to reach destination cell")
            try:
                stopped_cell_idx = self.path_cells.index(actual_path.end.cellId)
                if stopped_cell_idx == 0:
                    Logger().error("Could not find last reached cell in path")
                self.retry_movement()
                return
            except ValueError:
                Logger().error("Cell where movement stopped was not in original path")
                self.finish(self.errors.MOVEMENT_FAILED, "Movement stopped at unexpected cell")
                return
                    
        self.finish(0)
            
    def on_movement_failed(self, event) -> None:
        """Handle movement failure"""
        self._movement_request_sent = False

        if not self.state_manager.current_player :
            return self.finish(0)
            
        if self._movement_request_sent:
            Logger().error("Movement failed!")
            self.retry_movement()
