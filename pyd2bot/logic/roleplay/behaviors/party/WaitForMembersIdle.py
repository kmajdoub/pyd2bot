import json
import threading
from typing import TYPE_CHECKING

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.data.models import Character
from pydofus2.com.ankamagames.atouin.managers.MapDisplayManager import \
    MapDisplayManager
from pydofus2.com.ankamagames.berilia.managers.Listener import Listener
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionType import \
    ConnectionType
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    pass

class WaitForMembersIdle(AbstractBehavior):
    GET_STATUS_TIMEOUT = 992
    MEMBER_RECONNECT_WAIT_TIMEOUT = 30
    MEMBER_DISCONNECTED = 997
    
    def __init__(self) -> None:
        super().__init__()
        self.actorShowedListener: 'Listener' = None
        self.partyMemberLeftPartyListener = None
        self.memberStatus = dict[str, str]()
        self.members = list[Character]()

    def run(self, members: list[Character]) -> bool:
        self.members = members
        Logger().debug("Waiting for party members Idle.")
        thread_name = threading.current_thread().name
        self.status_thread = threading.Thread(target=self.fetchStatuses, name=thread_name)
        self.status_thread.daemon = True
        self.status_thread.start()
        
    def fetchStatuses(self):
        if not self.isRunning():
            return
        while not Kernel().worker.terminated.is_set():
            self.memberStatus = {member.accountId: self.getMuleStatus(member.accountId) for member in self.members}
            Logger().info(json.dumps(self.memberStatus, indent=2))
            if any(status != "idle" for status in self.memberStatus.values()):
                if any(status == "disconnected" for status in self.memberStatus.values()):
                    if Kernel().worker.terminated.wait(20): 
                        return
                else:
                    if Kernel().worker.terminated.wait(2): 
                        return
            else:
                Logger().info(f"All members are idle.")
                return self.finish(True, None)
    
    def getMuleStatus(self, instanceId):
        if not ConnectionsHandler.getInstance(instanceId) or \
            ConnectionsHandler.getInstance(instanceId).connectionType == ConnectionType.DISCONNECTED:
            return "disconnected"
        elif ConnectionsHandler.getInstance(instanceId).connectionType == ConnectionType.TO_LOGIN_SERVER:
            return "authenticating"
        if PlayedCharacterManager.getInstance(instanceId).isInFight:
            return "fighting"
        elif not Kernel.getInstance(instanceId).roleplayEntitiesFrame:
            return "outOfRolePlay"
        elif MapDisplayManager.getInstance(instanceId).currentDataMap is None:
            return "loadingMap"
        elif not Kernel.getInstance(instanceId).roleplayEntitiesFrame.mcidm_processed:
            return "processingMapData"
        for behavior in AbstractBehavior.getSubs(instanceId):
            if type(behavior).__name__ != "MuleFighter" and behavior.isRunning():
                return str(behavior)
        return "idle"
