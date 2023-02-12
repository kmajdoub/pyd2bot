import threading
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import (
    PlayedCharacterManager,
)
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import MapDisplayManager
from typing import TYPE_CHECKING

from pydofus2.com.ankamagames.jerakine.metaclasses.Singleton import Singleton

if TYPE_CHECKING:
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayEntitiesFrame import (
        RoleplayEntitiesFrame,
    )
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayInteractivesFrame import (
        RoleplayInteractivesFrame,
    )
    from pydofus2.com.ankamagames.dofus.logic.game.roleplay.frames.RoleplayMovementFrame import (
        RoleplayMovementFrame,
    )
    from pyd2bot.logic.roleplay.frames.BotFarmPathFrame import BotFarmPathFrame
    from pyd2bot.logic.roleplay.frames.BotPartyFrame import BotPartyFrame
    from pyd2bot.logic.roleplay.frames.BotUnloadInBankFrame import BotUnloadInBankFrame
    from pyd2bot.logic.roleplay.frames.BotUnloadInSellerFrame import BotUnloadInSellerFrame
    from pyd2bot.logic.roleplay.frames.BotSellerCollectFrame import BotSellerCollectFrame


class PlayerAPI(metaclass=Singleton):
    def __init__(self):
        self.inAutoTrip = threading.Event()

    def isIdle(self) -> bool:
        return self.status == "idle"
    
    def isProcessingMapData(self) -> bool:
        rpeframe: "RoleplayEntitiesFrame" = Kernel().worker.getFrameByName("RoleplayEntitiesFrame")
        return not rpeframe or not rpeframe.mcidm_processessed

    @property
    def status(self) -> str:
        bpframe: "BotPartyFrame" = Kernel().worker.getFrameByName("BotPartyFrame")
        mvframe: "RoleplayMovementFrame" = Kernel().worker.getFrameByName("RoleplayMovementFrame")
        iframe: "RoleplayInteractivesFrame" = Kernel().worker.getFrameByName("RoleplayInteractivesFrame")
        
        bfpf: "BotFarmPathFrame" = Kernel().worker.getFrameByName("BotFarmPathFrame")
        if MapDisplayManager().currentDataMap is None:
            status = "loadingMap"
        elif self.isProcessingMapData():
            status = "processingMapComplementaryData"
        elif PlayedCharacterManager().isInFight:
            status = "fighting"
        elif bpframe and bpframe.followingLeaderTransition:
            status = f"inTransition:{bpframe.followingLeaderTransition}"
        elif bpframe and bpframe.joiningLeaderVertex is not None:
            status = f"joiningLeaderVertex:{bpframe.joiningLeaderVertex}"
        elif Kernel().worker.getFrameByName("BotSellerCollectFrame"):
            f: "BotSellerCollectFrame" = Kernel().worker.getFrameByName("BotSellerCollectFrame")
            status = "collectingSellerItems:" + f.state.name
        elif Kernel().worker.getFrameByName("BotUnloadInBankFrame"):
            f: "BotUnloadInBankFrame" = Kernel().worker.getFrameByName("BotUnloadInBankFrame")
            status = "inBankAutoUnload:" + f.state.name
        elif Kernel().worker.getFrameByName("BotUnloadInSellerFrame"):
            f: "BotUnloadInSellerFrame" = Kernel().worker.getFrameByName("BotUnloadInSellerFrame")
            status = "inSellerAutoUnload:" + f.state.name
        elif Kernel().worker.getFrameByName("BotPhenixAutoRevive"):
            status = "inPhenixAutoRevive"
        elif self.inAutoTrip.is_set():
            status = "inAutoTrip"
        elif bfpf and bfpf._followinMonsterGroup:
            status = "followingMonsterGroup"
        elif bfpf and bfpf._followingIe:
            status = "followingIe"
        elif iframe and iframe._usingInteractive:
            status = "interacting"
        elif mvframe and mvframe._isMoving:
            status = "moving"
        elif mvframe and mvframe._wantToChangeMap:
            status = "changingMap"
        else:
            status = "idle"
        return status
