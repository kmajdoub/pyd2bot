
from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.fight.MuleFighter import MuleFighter
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.metaclasses.Singleton import Singleton


class PlayerAPI(metaclass=Singleton):
    def __init__(self):
        pass


    def status(self, instanceId) -> str:
        for behavior in AbstractBehavior.getSubs(instanceId):
            if type(behavior) != MuleFighter and behavior.isRunning():
                return f"Running:{type(behavior).__name__}"
        if PlayedCharacterManager.getInstance(instanceId).isInFight:
            status = "fighting"
        elif MapDisplayManager.getInstance(instanceId).currentDataMap is None:
            status = "loadingMap"
        elif not Kernel.getInstance(instanceId).roleplayEntitiesFrame:
            status = "outOfRolePlay"
        elif not Kernel.getInstance(instanceId).roleplayEntitiesFrame.mcidm_processed:
            status = "processingMapData"
        else:
            status = "idle"
        return status
