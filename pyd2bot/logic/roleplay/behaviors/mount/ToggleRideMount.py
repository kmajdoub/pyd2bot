from typing import TYPE_CHECKING

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.data.enums import ServerNotificationEnum
from pydofus2.com.ankamagames.atouin.HaapiEventsManager import HaapiEventsManager
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.uiApi.PlayedCharacterApi import PlayedCharacterApi
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    pass


class ToggleRideMount(AbstractBehavior):
    NEED_LVL_60 = 77887661
    NO_ENERGY_LEFT = 77887662
    NO_EQUIPPED_MOUNT = 77887663
    ALREADY_RIDING = 77887664
    ONLY_SUBSCRIBED = 77887665
    DIDNT_GET_WANTED_STATE = 77887666
    
    def __init__(self) -> None:
        super().__init__()
    
    def onServerTextInfo(self, event, msgId, msgType, textId, text, params):
        if textId == ServerNotificationEnum.MOUNT_HAS_NO_ENERGY_LEFT:  # Mount has no energy left
            self.finish(self.NO_ENERGY_LEFT, text)

    def useToggleRideMountShortcut(self):
        if not Kernel().mountFrame:
            return self.once_frame_pushed('MountFrame', self.useToggleRideMountShortcut)
        KernelEventsManager().once(KernelEvent.MountRiding, self.onMountRiding)
        HaapiEventsManager().registerShortcutUse("openMount")
        if not Kernel().worker.terminated.wait(0.3):
            Kernel().mountFrame.mountToggleRidingRequest()
    
    def onMountRiding(self, event, isRiding):
        if self.wanted_ride_state is not None and self.wanted_ride_state != isRiding:
            return self.finish(self.DIDNT_GET_WANTED_STATE, "Mount riding state is not as wanted")
        self.finish(0)

    def run(self, wanted_ride_state=None) -> bool:
        self.wanted_ride_state = wanted_ride_state
        self.mount = PlayedCharacterApi.getMount()
        if not self.mount:
            return self.finish(self.NO_EQUIPPED_MOUNT, "No mount")
        if PlayerManager().isBasicAccount():
            return self.finish(self.ONLY_SUBSCRIBED, "Only subscribed accounts can ride mounts")
        if PlayedCharacterManager().infos.level < 60:
            return self.finish(self.NEED_LVL_60, "Need to be level 10 to ride a mount")
        energy_left_ration = self.mount.energy / self.mount.energyMax
        if energy_left_ration < 0.05:
            return self.finish(self.NO_ENERGY_LEFT, "Mount has no energy left to ride")
        if wanted_ride_state is not None:
            if wanted_ride_state and PlayedCharacterApi.isRiding():
                return self.finish(self.ALREADY_RIDING, "Already riding mount")
            if not wanted_ride_state and not PlayedCharacterApi.isRiding():
                return self.finish(self.ALREADY_RIDING, "Not riding mount can't dismount")
        self.useToggleRideMountShortcut()