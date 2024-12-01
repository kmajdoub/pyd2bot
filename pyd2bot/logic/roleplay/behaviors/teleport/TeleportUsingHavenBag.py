from enum import Enum
from typing import Optional
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.teleport.UseZaap import UseZaap
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

class TeleportUsingHavenbag(AbstractBehavior):
    
    class errors(Enum):
        INSUFFICIENT_LEVEL = 555112
        BASIC_ACCOUNT = 555113

    def __init__(self, dst_map_id) -> None:
        super().__init__()
        self.dst_map_id = dst_map_id

    def run(self):
        if not self.checkCanUse():
            return

        self.toggle_haven_bag(wanted_state=True, callback=self.onInsideHavenbag)

    def checkCanUse(self) -> bool:
        if PlayerManager().isBasicAccount():
            self.finish(self.errors.BASIC_ACCOUNT, "Cannot use havenbag - basic account")
            return False
        if PlayedCharacterManager().infos.level < 10:
            self.finish(self.errors.INSUFFICIENT_LEVEL, "Cannot use havenbag - insufficient level")
            return False
        return True
   

    def onInsideHavenbag(self, code: int, err: Optional[str]) -> None:
        if err:
            return self.finish(code, err)

        self.useZaap(
            self.dst_map_id,
            callback=self.onDestinationReached
        )

    def onDestinationReached(self, code: int, err: Optional[str]) -> None:
        if err:
            if code == UseZaap.DST_ZAAP_NOT_KNOWN:
                def onHavenbagClosed(code2, err2):
                    if err2:
                        KernelEventsManager().send(
                            KernelEvent.ClientRestart, 
                            f"Failed to close havenbag for reason {code2} {err2} after, destination zaap was not found in possible destinations."
                        )
                        return

                    self.finish(code, err)

                return self.toggle_haven_bag(wanted_state=False, callback=onHavenbagClosed)

            return self.finish(code, err)
        
        Logger().debug(f"Successfully teleported to map {self.dst_map_id}")
        self.finish(0)