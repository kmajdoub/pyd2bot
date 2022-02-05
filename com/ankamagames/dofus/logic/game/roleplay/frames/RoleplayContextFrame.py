from com.ankamagames.atouin.managers.MapDisplayManager import MapDisplayManager
from com.ankamagames.dofus.datacenter.world.SubArea import SubArea
from com.ankamagames.dofus.internalDatacenter.world.WorldPointWrapper import WorldPointWrapper
from com.ankamagames.dofus.kernel.Kernel import Kernel
from com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import PlayedCharacterManager
from com.ankamagames.dofus.network.messages.game.context.GameContextDestroyMessage import GameContextDestroyMessage
from com.ankamagames.dofus.network.messages.game.context.roleplay.CurrentMapInstanceMessage import CurrentMapInstanceMessage
from com.ankamagames.dofus.network.messages.game.context.roleplay.CurrentMapMessage import CurrentMapMessage
from com.ankamagames.jerakine.logger.Logger import Logger
from com.ankamagames.jerakine.messages.Frame import Frame
from com.ankamagames.jerakine.messages.Message import Message
from com.ankamagames.jerakine.types.enums.Priority import Priority
logger = Logger(__name__)
class RoleplayContextFrame(Frame):

    

    def __init__(self):
        self._newCurrentMapIsReceived = False
        self._previousMapId = None
        self._priority = Priority.NORMAL
        super().__init__()

    @property
    def priority(self) -> int:
        return self._priority

    @priority.setter
    def priority(self, p: int) -> None:
        self._priority = p

    @property
    def previousMapId(self) -> float:
        return self._previousMapId

    @property
    def newCurrentMapIsReceived(self) -> bool:
        return self._newCurrentMapIsReceived

    @newCurrentMapIsReceived.setter
    def newCurrentMapIsReceived(self, value: bool) -> None:
        self._newCurrentMapIsReceived = value

    def pushed(self) -> bool:
        return True

    def process(self, msg: Message) -> bool:

        if isinstance(msg, CurrentMapMessage):
            mcmsg = msg
            self._newCurrentMapIsReceived = True
            newSubArea = SubArea.getSubAreaByMapId(mcmsg.mapId)
            PlayedCharacterManager().currentSubArea = newSubArea
            if isinstance(mcmsg, CurrentMapInstanceMessage):
                MapDisplayManager().mapInstanceId = mcmsg.instantiatedMapId
            else:
                MapDisplayManager().mapInstanceId = 0
            wp = None
            if PlayedCharacterManager().isInHouse:
                wp = WorldPointWrapper(mcmsg.mapId, True, PlayedCharacterManager().currentMap.outdoorX, PlayedCharacterManager().currentMap.outdoorY)
            else:
                wp = WorldPointWrapper(int(mcmsg.mapId))

            if PlayedCharacterManager().currentMap:
                self._previousMapId = PlayedCharacterManager().currentMap.mapId

            PlayedCharacterManager().currentMap = wp
            logger.info("Current map changed to " + str(PlayedCharacterManager().currentMap.mapId))
            MapDisplayManager().loadMap(int(mcmsg.mapId))
            return True

        elif isinstance(msg, GameContextDestroyMessage):
            Kernel().getWorker().removeFrame(self)
            return True

        return False

    def pulled(self) -> bool:
        return True
