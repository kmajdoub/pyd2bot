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

    @property
    def status(self) -> str:
        bpframe: "BotPartyFrame" = Kernel().worker.getFrame("BotPartyFrame")
        mvframe: "RoleplayMovementFrame" = Kernel().worker.getFrame("RoleplayMovementFrame")
        iframe: "RoleplayInteractivesFrame" = Kernel().worker.getFrame("RoleplayInteractivesFrame")
        rpeframe: "RoleplayEntitiesFrame" = Kernel().worker.getFrame("RoleplayEntitiesFrame")
        bfpf: "BotFarmPathFrame" = Kernel().worker.getFrame("BotFarmPathFrame")
        if MapDisplayManager().currentDataMap is None:
            status = "loadingMap"
        elif rpeframe and not rpeframe.mcidm_processessed:
            status = "processingMapComplementaryData"
        elif PlayedCharacterManager().isInFight:
            status = "fighting"
        elif bpframe and bpframe.followingLeaderTransition:
            status = f"inTransition:{bpframe.followingLeaderTransition}"
        elif bpframe and bpframe.joiningLeaderVertex is not None:
            status = f"joiningLeaderVertex:{bpframe.joiningLeaderVertex}"
        elif Kernel().worker.getFrame("BotSellerCollectFrame"):
            f: "BotSellerCollectFrame" = Kernel().worker.getFrame("BotSellerCollectFrame")
            status = "collectingSellerItems:" + f.state.name
        elif Kernel().worker.getFrame("BotUnloadInBankFrame"):
            f: "BotUnloadInBankFrame" = Kernel().worker.getFrame("BotUnloadInBankFrame")
            status = "inBankAutoUnload:" + f.state.name
        elif Kernel().worker.getFrame("BotUnloadInSellerFrame"):
            f: "BotUnloadInSellerFrame" = Kernel().worker.getFrame("BotUnloadInSellerFrame")
            status = "inSellerAutoUnload:" + f.state.name
        elif Kernel().worker.getFrame("BotPhenixAutoRevive"):
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
