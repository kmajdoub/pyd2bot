from enum import Enum
from typing import Optional
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.skill.UseSkill import UseSkill
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.datacenter.interactives.Interactive import Interactive
from pydofus2.com.ankamagames.dofus.internalDatacenter.DataEnum import DataEnum
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.InteractiveElementData import InteractiveElementData
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.types.MovementFailError import MovementFailError
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

class InteractiveMapChange(AbstractBehavior):    
    class errors(Enum):
        LANDED_ON_WRONG_MAP = 1002
        IE_NOT_FOUND = 1003
        WRONG_IE_TYPE = 1004

    def __init__(self, dst_map_id: int, ie_elem_id: int, skill_id: int, cell_id: int) -> None:
        super().__init__()
        self.dst_map_id = dst_map_id
        self.ie_elem_id = ie_elem_id
        self.skill_id = skill_id
        self.cell_id = cell_id
        self.map_change_ie: Optional[InteractiveElementData] = None

    def run(self) -> None:
        # Check and validate the interactive element first
        self.map_change_ie = Kernel().interactiveFrame._ie.get(self.ie_elem_id)
        
        if not self.map_change_ie:
            return self.finish(
                self.errors.IE_NOT_FOUND,
                f"Unable to find interactive element {self.ie_elem_id}! Available: {Kernel().interactiveFrame._ie}"
            )

        # Log IE info if available
        ie_type = Interactive.getInteractiveById(self.map_change_ie.element.elementTypeId)
        if ie_type:
            Logger().debug(f"Transition IE is {ie_type.name} ==> {ie_type.actionId}")

        # Check if it's a zaap - if so, we shouldn't handle it
        if self.map_change_ie.element.elementTypeId == DataEnum.ZAAP_TYPEID:
            return self.useZaap(self.dst_map_id, callback=self.finish)

        self.on(
            KernelEvent.CurrentMap,
            self.on_current_map,
            timeout=20,
            ontimeout=self.on_request_timeout
        )

        self.on(
            KernelEvent.InteractiveUseError,
            self.on_use_error
        )

        self.use_skill(
            elementId=self.ie_elem_id,
            skilluid=self.skill_id,
            cell=self.cell_id,
            exactDestination=False,
            callback=self.on_skill_used
        )

    def on_skill_used(self, code: int, error: Optional[str]) -> None:
        if PlayedCharacterManager().isInFight:
            return self.stop()

        if error:
            return self.finish(code, error)

        Logger().debug("Map change IE used")

    def on_use_error(self, event) -> None:
        self.finish(
            MovementFailError.INTERACTIVE_USE_ERROR,
            "Failed to use interactive element"
        )

    def on_current_map(self, event, map_id: int) -> None:
        self.clearListeners()
        if map_id == self.dst_map_id:
            callback = lambda: self.finish(0)
        else:
            callback = lambda: self.finish(
                self.errors.LANDED_ON_WRONG_MAP,
                f"Landed on new map '{map_id}', different from dest '{self.dst_map_id}'."
            )
        self.once_map_rendered(callback=callback, mapId=map_id, timeout=20, ontimeout=self.on_dest_map_rendered_timeout)

    def on_dest_map_rendered_timeout(self, listener):
        if PlayedCharacterManager().isInFight:
            self.stop(True)
            return

        self.finish(222, "Request Map data timeout")
        
    def on_request_timeout(self, listener) -> None:
        if UseSkill().isRunning():
            listener.armTimer()
            return
            
        self.finish(
            MovementFailError.MAP_CHANGE_TIMEOUT,
            "Map change request timed out"
        )
