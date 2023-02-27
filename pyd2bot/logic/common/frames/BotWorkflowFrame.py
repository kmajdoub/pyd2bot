from pyd2bot.logic.fight.frames.BotFightFrame import BotFightFrame
from pyd2bot.logic.fight.frames.BotMuleFightFrame import BotMuleFightFrame
from pyd2bot.logic.managers.BotConfig import BotConfig
from pyd2bot.logic.roleplay.behaviors.AutoRevive import AutoRevive
from pyd2bot.logic.roleplay.behaviors.FarmPath import FarmPath
from pyd2bot.logic.roleplay.behaviors.GiveItems import GiveItems
from pyd2bot.logic.roleplay.behaviors.UnloadInBank import UnloadInBank
from pyd2bot.logic.roleplay.frames.BotPartyFrame import BotPartyFrame
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.network.enums.GameContextEnum import \
    GameContextEnum
from pydofus2.com.ankamagames.dofus.network.enums.PlayerLifeStatusEnum import \
    PlayerLifeStatusEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameContextCreateMessage import \
    GameContextCreateMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.GameContextDestroyMessage import \
    GameContextDestroyMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.death.GameRolePlayGameOverMessage import \
    GameRolePlayGameOverMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority


class BotWorkflowFrame(Frame):
    def __init__(self):
        self.currentContext = None
        super().__init__()

    def pushed(self) -> bool:
        self._delayedAutoUnlaod = False
        return True

    def pulled(self) -> bool:
        return True

    @property
    def priority(self) -> int:
        return Priority.VERY_LOW
    
    def process(self, msg: Message) -> bool:

        if isinstance(msg, GameContextCreateMessage):
            ctxname = "Fight" if msg.context == GameContextEnum.FIGHT else "Roleplay"
            Logger().separator(f"{ctxname} Game Context Created")
            self.currentContext = msg.context
            if BotConfig().party and not Kernel().worker.contains("BotPartyFrame"):
                Kernel().worker.addFrame(BotPartyFrame())
            if self.currentContext == GameContextEnum.ROLE_PLAY:
                if PlayedCharacterManager().inventoryWeight / PlayedCharacterManager().inventoryWeightMax > 0.95:
                    Logger().warning(f"[BotWorkflow] Inventory is almost full will trigger auto unload...")
                    return KernelEventsManager().onceMapProcessed(self.unloadInventory)
                if BotConfig().path and not FarmPath().isRunning():
                    KernelEventsManager().onceMapProcessed(FarmPath().start)
            elif self.currentContext == GameContextEnum.FIGHT:
                if BotConfig().isLeader:
                    Kernel().worker.addFrame(BotFightFrame())
                else:
                    Kernel().worker.addFrame(BotMuleFightFrame())
            return True

        elif isinstance(msg, GameContextDestroyMessage):
            ctxname = "Fight" if self.currentContext == GameContextEnum.FIGHT else "Roleplay"
            Logger().separator(f"{ctxname} Context Destroyed")
            if self.currentContext == GameContextEnum.FIGHT:
                if BotConfig().isLeader and Kernel().worker.contains("BotFightFrame"):
                    Kernel().worker.removeFrameByName("BotFightFrame")
                elif Kernel().worker.contains("BotMuleFightFrame"):
                    Kernel().worker.removeFrameByName("BotMuleFightFrame")
            if self.currentContext == GameContextEnum.ROLE_PLAY:
                if BotConfig().path and FarmPath().isRunning():
                    FarmPath().stop()
            return True
        
        elif isinstance(msg, GameRolePlayGameOverMessage):
            self.onPlayerStateChange(None, PlayerLifeStatusEnum.STATUS_TOMBSTONE)

    def onPlayerStateChange(self, event, state):
        if state == PlayerLifeStatusEnum.STATUS_TOMBSTONE or state == PlayerLifeStatusEnum.STATUS_PHANTOM:
            if BotConfig().isLeader:
                FarmPath().stop()
            Kernel().worker.removeFrameByName("BotPartyFrame")
            PlayedCharacterManager().state = state
            AutoRevive().start(self.onPhenixAutoReviveEnded)
        
    def onPhenixAutoReviveEnded(self, e=None):
        Logger().debug(f"[BotWorkflow] Phenix auto revive ended.")
        if BotConfig().path:
            FarmPath().start()
        if BotConfig().party and not Kernel().worker.contains("BotPartyFrame"):
            Kernel().worker.addFrame(BotPartyFrame())
        return True

    def unloadInventory(self, callback=None):
        def onInventoryUnloaded(status, error):
            if error:
                raise Exception(f"[BotWorkflow] Error while unloading inventory: {error}")
            if BotConfig().party:
                Kernel().worker.addFrame(BotPartyFrame())
            if BotConfig().path and not FarmPath().isRunning():
                FarmPath().start()
        if callback:
            callback()
        if BotConfig().party:
            Kernel().worker.removeFrameByName("BotPartyFrame")
        if BotConfig().unloadInBank:
            UnloadInBank().start(onInventoryUnloaded)
        elif BotConfig().unloadInSeller:
            GiveItems().start(BotConfig().seller, onInventoryUnloaded)
        if BotConfig().path and FarmPath().isRunning():
            FarmPath().stop()
    