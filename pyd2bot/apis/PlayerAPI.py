import threading
from typing import TYPE_CHECKING

from pyd2bot.logic.roleplay.behaviors.AutoRevive import AutoRevive
from pyd2bot.logic.roleplay.behaviors.AutoTrip import AutoTrip
from pyd2bot.logic.roleplay.behaviors.ChangeMap import ChangeMap
from pyd2bot.logic.roleplay.behaviors.MapMove import MapMove
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.metaclasses.Singleton import Singleton

if TYPE_CHECKING:
    from pyd2bot.logic.roleplay.frames.BotPartyFrame import BotPartyFrame
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayEntitiesFrame import \
        RoleplayEntitiesFrame
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayInteractivesFrame import \
        RoleplayInteractivesFrame
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayMovementFrame import \
        RoleplayMovementFrame


class PlayerAPI(metaclass=Singleton):
    def __init__(self):
        pass

    def isIdle(self) -> bool:
        return self.status == "idle"
    
    def isProcessingMapData(self) -> bool:
        rpeframe: "RoleplayEntitiesFrame" = Kernel().worker.getFrameByName("RoleplayEntitiesFrame")
        return not rpeframe or not rpeframe.mcidm_processessed

    @property
    def status(self) -> str:
        from pyd2bot.logic.roleplay.behaviors.CollectItems import CollectItems
        from pyd2bot.logic.roleplay.behaviors.FarmPath import FarmPath
        from pyd2bot.logic.roleplay.behaviors.GiveItems import GiveItems
        from pyd2bot.logic.roleplay.behaviors.UnloadInBank import UnloadInBank
        bpframe: "BotPartyFrame" = Kernel().worker.getFrameByName("BotPartyFrame")
        mvframe: "RoleplayMovementFrame" = Kernel().worker.getFrameByName("RoleplayMovementFrame")
        iframe: "RoleplayInteractivesFrame" = Kernel().worker.getFrameByName("RoleplayInteractivesFrame")
        if MapDisplayManager().currentDataMap is None:
            status = "loadingMap"
        elif self.isProcessingMapData():
            status = "processingMapData"
        elif PlayedCharacterManager().isInFight:
            status = "fighting"
        elif bpframe and bpframe.followingLeaderTransition:
            status = f"FollowingLeaderTransition"
        elif bpframe and bpframe.joiningLeaderVertex is not None:
            status = f"joiningLeaderVertex"
        elif MapMove().isRunning():
            status = f"movingToCell:{MapMove().dstCell}"
        elif ChangeMap().isRunning():
            status = f"changingMap"
        elif CollectItems().isRunning():
            status = f"collectingSellerItems:{CollectItems().state.name}"
        elif UnloadInBank().isRunning():
            status = f"inBankAutoUnload:{UnloadInBank().state.name}"
        elif GiveItems().isRunning():
            status = f"inSellerAutoUnload:{GiveItems().state.name}"
        elif AutoRevive().isRunning():
            status = "inPhenixAutoRevive"
        elif AutoTrip().isRunning():
            status = f"inAutoTripTo:{AutoTrip().dstMapId}"
        elif FarmPath().isRunning():
            status = f"Farm:{FarmPath().state.name}"
        elif iframe and iframe._usingInteractive:
            status = "interacting"
        elif mvframe and mvframe.isMoving:
            status = "moving"
        elif mvframe and mvframe.requestType:
            status = mvframe.requestType.name
        else:
            status = "idle"
        return status
