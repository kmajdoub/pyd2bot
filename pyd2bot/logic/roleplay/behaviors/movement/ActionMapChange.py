from typing import Optional, Tuple, Iterable
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.movement.MapMove import MapMove
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.ChangeMapMessage import ChangeMapMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.positions.MapPoint import MapPoint
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.types.MovementFailError import MovementFailError

class ActionMapChange(AbstractBehavior):
    MAP_CHANGE_TIMEOUT = 20
    MAP_ACTION_ALREADY_ON_CELL = 1204
    MAP_CHANGED_UNEXPECTEDLY = 1556
    LANDED_ON_WRONG_MAP = 1002
    
    def __init__(self, dst_map_id: int, cell_id: int) -> None:
        super().__init__()
        self.current_mp_childs: Optional[Iterable[Tuple[int, int]]] = None
        self._map_change_request_sent = False
        self.dst_map_id = dst_map_id
        self.map_change_cell = cell_id

    def run(self, ) -> None:
        Logger().debug(f"Action map change to dest {self.dst_map_id} using cell {self.map_change_cell}")
        if self.dst_map_id == PlayedCharacterManager().currVertex.mapId:
            self.on(
                KernelEvent.PlayerTeleportedOnSameMap,
                self.on_same_map_teleport,
                timeout=self.MAP_CHANGE_TIMEOUT,
                ontimeout=self.on_request_timeout,
            )
        else:
            self.on(
                KernelEvent.CurrentMap,
                self.on_current_map,
                timeout=self.MAP_CHANGE_TIMEOUT,
                ontimeout=self.on_request_timeout
            )
        
        self.map_move_to_cell(
            self.map_change_cell, 
            exact_destination=True,
            callback=self.on_move_to_map_change_cell
        )

    def on_move_to_map_change_cell(self, code: int, error: Optional[str], landing_cell: Optional[int]) -> None:
        """Handler for reaching the map change cell"""
        if PlayedCharacterManager().isInFight:
            return self.stop()

        if code == MapMove.ALREADY_ON_CELL:
            Logger().debug("Already on map action cell, need to move away first")
            return self.handle_same_cell_case()
            
        if error:
            return self.finish(code, error)

        Logger().debug("Reached map change cell, waiting for server to change map")

    def on_same_map_teleport(self, event, new_map_position):
        self.finish(0)
        
    def handle_same_cell_case(self) -> None:
        """Handle the case where we're already on the map change cell"""
        self.current_mp_childs = MapPoint.fromCellId(self.map_change_cell).iterChildren(False, True)
        
        try:
            x, y = next(self.current_mp_childs)
        except StopIteration:
            return self.finish(
                self.MAP_ACTION_ALREADY_ON_CELL,
                "Already on map action cell and can't move away from it."
            )

        # Move to adjacent cell first
        self.map_move_to_cell(
            MapPoint.fromCoords(x, y).cellId,
            exact_destination=True,
            callback=self.on_moved_away
        )

    def on_moved_away(self, code: int, error: Optional[str], landing_cell: Optional[int]) -> None:
        """Handler for moving away from map change cell"""
        if error:
            try:
                x, y = next(self.current_mp_childs)
            except StopIteration:
                return self.finish(
                    self.MAP_ACTION_ALREADY_ON_CELL,
                    "Already on map action cell and can't move away from it."
                )
            return self.map_move_to_cell(
                MapPoint.fromCoords(x, y).cellId,
                exact_destination=True,
                callback=self.on_moved_away
            )

        # Now move back to map change cell
        self.on(
            KernelEvent.CurrentMap,
            callback=self.on_unexpected_map_change,
            timeout=3,
            ontimeout=lambda *_: self.move_back_to_change_cell()
        )

    def move_back_to_change_cell(self) -> None:
        """Move back to the map change cell after moving away"""
        self.map_move_to_cell(
            self.map_change_cell,
            exact_destination=True,
            callback=self.on_move_to_map_change_cell
        )

    def on_unexpected_map_change(self, event, map_id: int) -> None:
        """Handler for unexpected map changes"""
        self.finish(
            self.MAP_CHANGED_UNEXPECTEDLY,
            "Map changed unexpectedly while resolving."
        )

    def on_current_map(self, event, map_id: int) -> None:
        """Handler for map change completion"""
        if map_id == self.dst_map_id:
            callback = lambda *_: self.finish(0)
        else:
            callback = lambda *_: self.finish(
                self.LANDED_ON_WRONG_MAP,
                f"Landed on new map '{map_id}', different from dest '{self.dst_map_id}'."
            )
        self.once_map_rendered(callback=callback, mapId=map_id, timeout=20, ontimeout=self.on_dest_map_rendered_timeout)

    def on_dest_map_rendered_timeout(self, listener):
        if PlayedCharacterManager().isInFight:
            self.stop(True)
            return

        self.finish(222, "Request Map data timed out!")

    def on_request_timeout(self, listener) -> None:
        """Handler for map change request timeout"""
        if MapMove().isRunning():
            listener.armTimer()
            return
            
        self.finish(
            MovementFailError.MAP_CHANGE_TIMEOUT,
            "Map change request timed out"
        )

    def send_map_change_request(self) -> None:
        """Send the map change request to the server"""
        msg = ChangeMapMessage()
        msg.init(self.dst_map_id, False)
        ConnectionsHandler().send(msg)
        self._map_change_request_sent = True