from typing import Optional, Iterable
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.movement.MapMove import MapMove
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.InactivityManager import InactivityManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.types.MovementFailError import MovementFailError
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.ChangeMapMessage import ChangeMapMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.types.enums.DirectionsEnum import DirectionsEnum
from pydofus2.mapTools import MapTools

class ScrollMapChange(AbstractBehavior):
    MAP_CHANGE_TIMEOUT = 20
    LANDED_ON_WRONG_MAP = 1002

    def __init__(self, dst_map_id: int, tr_mapid:int, cell: int, direction: int) -> None:
        super().__init__()
        self.dst_map_id = dst_map_id
        self.tr_mapid = tr_mapid
        self.cell = cell
        self.direction = direction
        self.map_change_cell: Optional[int] = None
        self.forbidden_cells: list[int] = []
        self.iter_scroll_cells: Optional[Iterable[int]] = None
        self._map_change_request_sent = False
        
    def run(self) -> None:
        Logger().debug(f"Running scroll transition to dst map {self.dst_map_id}, direction {DirectionsEnum(self.direction).name} on cell {self.cell}")
        self.iter_scroll_cells = self.get_scroll_cells()
        self.try_next_scroll_cell()

    def get_scroll_cells(self) -> Iterable[int]:
        """Get iterator of possible scroll cells"""
        # First try the transition's specified cell
        if self.cell not in self.forbidden_cells:
            yield self.cell
            
        # Then try other possible scroll cells in that direction
        for cell in MapTools.iterMapChangeCells(self.direction):
            if cell not in self.forbidden_cells:
                yield cell

    def try_next_scroll_cell(self) -> None:
        """Try the next available scroll cell"""
        try:
            self.map_change_cell = next(self.iter_scroll_cells)
        except StopIteration:
            return self.finish(
                MovementFailError.NO_VALID_SCROLL_CELL,
                "No valid scroll cells remaining"
            )

        self.on(
            KernelEvent.CurrentMap,
            self.on_current_map,
            timeout=self.MAP_CHANGE_TIMEOUT,
            ontimeout=self.on_request_timeout
        )

        self.on(
            KernelEvent.MovementRequestRejected,
            self.on_request_rejected
        )

        self.map_move_to_cell(
            self.map_change_cell,
            exact_destination=True,
            forMapChange=True,
            mapChangeDirection=self.direction,
            callback=self.on_move_to_scroll_cell
        )

    def on_move_to_scroll_cell(self, code: int, error: Optional[str], landing_cell: Optional[int]) -> None:
        if PlayedCharacterManager().isInFight:
            return self.finish(0)

        if error:
            Logger().error(f"Move to scroll map change failed with error [{code}] {error} => will try another scroll cell!")
        
        if code == MovementFailError.MOVE_REQUEST_REJECTED:
            self.forbidden_cells.append(self.map_change_cell)
            return self.try_next_scroll_cell()

        if error:
            return self.finish(code, error)

        Logger().debug(f"Reached scroll cell {self.map_change_cell}")
        Kernel().defer(self.send_map_change_request)

    def send_map_change_request(self) -> None:
        msg = ChangeMapMessage()
        msg.init(int(self.tr_mapid), False)
        ConnectionsHandler().send(msg)
        self._map_change_request_sent = True
        InactivityManager().activity()

    def on_request_rejected(self, even) -> None:
        if not self._map_change_request_sent:
            return
            
        self.clearListeners()
        self.forbidden_cells.append(self.map_change_cell)
        self.try_next_scroll_cell()

    def on_current_map(self, event, map_id: int) -> None:
        self.clearListeners()
        if map_id == self.dst_map_id:
            callback = lambda: self.finish(0)
        else:
            callback = lambda: self.finish(
                self.LANDED_ON_WRONG_MAP,
                f"Landed on new map '{map_id}', different from dest '{self.dst_map_id}'."
            )
        self.once_map_rendered(callback=callback, mapId=map_id, timeout=20, ontimeout=self.on_dest_map_rendered_timeout)

    def on_dest_map_rendered_timeout(self, listener):
        if PlayedCharacterManager().isInFight:
            self.stop(True)
            return

        self.finish(222, "Request Map data timeout")
        
    def on_request_timeout(self, listener) -> None:
        if MapMove().isRunning():
            listener.armTimer()
            return
            
        self.clearListeners()
        self.forbidden_cells.append(self.map_change_cell)
        self.try_next_scroll_cell()
