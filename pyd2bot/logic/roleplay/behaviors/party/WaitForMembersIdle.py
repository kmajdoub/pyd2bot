import json
import threading

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
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
    
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

    def run(self, members: list[Character], leader: Character) -> bool:
        self.leader = leader
        self.members = members
        thread_name = threading.current_thread().name
        self.status_thread = threading.Thread(target=self.fetchStatuses, name=thread_name)
        self.status_thread.daemon = True
        self.status_thread.start()
        
    def fetchStatuses(self):
        Logger().debug("Fetch status started")
        if not self.isRunning():
            return
        while not Kernel().worker.terminated.is_set():
            Logger().debug("Fetching members statuses ...")
            self.memberStatus = {member.accountId: self.getMuleStatus(member.accountId) for member in self.members}
            Logger().debug(json.dumps(self.memberStatus, indent=2))
            if any(status != "idle" for status in self.memberStatus.values()):
                Logger().info(f"Some of the members are not idle!")
                if any(status == "disconnected" for status in self.memberStatus.values()):
                    Logger().debug("Some members are disconnected will wait for 10 seconds before fetching again")
                    if Kernel().worker.terminated.wait(5):
                        Logger().debug("fetch members status will shutdown because worker terminated!")
                        return
                else:
                    if Kernel().worker.terminated.wait(2):
                        Logger().debug("fetch members status will shutdown because worker terminated!")
                        return
            else:
                Logger().info(f"All members are idle.")
                return self.finish(True, None)
        Logger().debug("Fetch status finished because worker is terminated")
    
    def getMuleStatus(self, instanceId):
        Logger().debug(f"Fetching player {instanceId} status")
        try:
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
            elif PlayedCharacterManager.getInstance(instanceId).isDead():
                return "muleIsDead"
            Logger().debug(f"Checking if player {instanceId} is running behaviors")
            for behavior in AbstractBehavior.getSubs(instanceId):
                if type(behavior).__name__ != "MuleFighter" and behavior.isRunning() and not behavior.IS_BACKGROUND_TASK:
                    return type(behavior).__name__
            return "idle"
        except Exception as e:
            Logger().error("Something went wrong while fetching mule status", exc_info=True)
            KernelEventsManager().send(KernelEvent.ClientShutdown, f"Error while fetching mule status: {e}")
            raise
