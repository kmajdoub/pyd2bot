from pyd2bot.data.models import Session
from pyd2bot.logic.common.rpcMessages.PlayerConnectedMessage import \
    PlayerConnectedMessage
from pyd2bot.logic.roleplay.messages.SellerVacantMessage import \
    SellerVacantMessage
from pyd2bot.misc.BotEventsManager import BotEventsManager
from pyd2bot.data.enums import ServerNotificationEnum
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.kernel.net.PlayerDisconnectedMessage import \
    PlayerDisconnectedMessage
from pydofus2.com.ankamagames.dofus.network.messages.common.basic.BasicPingMessage import \
    BasicPingMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.ankamagames.jerakine.messages.Frame import Frame
from pydofus2.com.ankamagames.jerakine.messages.Message import Message
from pydofus2.com.ankamagames.jerakine.types.enums.Priority import Priority


class BotWorkflowFrame(Frame):
    def __init__(self, session: Session):
        self.currentContext = None
        self.session = session
        super().__init__()

    def pushed(self) -> bool:
        KernelEventsManager().on(KernelEvent.ServerTextInfo, self.onServerNotif, originator=self)
        return True

    def pulled(self) -> bool:
        KernelEventsManager().clearAllByOrigin(self)
        return True

    @property
    def priority(self) -> int:
        return Priority.VERY_LOW
    
    def process(self, msg: Message) -> bool:
        
        if isinstance(msg, PlayerConnectedMessage):
            Logger().info(f"Bot {msg.instanceId} connected")
            BotEventsManager().send(BotEventsManager.BOT_CONNECTED, msg.instanceId)
            return True
        
        elif isinstance(msg, PlayerDisconnectedMessage):
            Logger().info(f"Bot {msg.instanceId} disconnected")
            BotEventsManager().send(BotEventsManager.PLAYER_DISCONNECTED, msg.instanceId, msg.connectionType)
            return True

        elif isinstance(msg, SellerVacantMessage):
            Logger().info(f"Seller {msg.instanceId} is vacant")
            BotEventsManager().send(BotEventsManager.SELLER_AVAILABLE, msg.instanceId)
            return True

    def onServerNotif(self, event, msgId, msgType, textId, text, params):
        # if textId == ServerNotificationEnum.INACTIVITY_WARNING:
        #     if not self.session.isSeller:
        #         KernelEventsManager().send(KernelEvent.ClientRestart, "Bot stayed inactive for too long, must have a bug")
        #     else:
        #         pingMsg = BasicPingMessage()
        #         pingMsg.init(True)
        #         ConnectionsHandler().send(pingMsg)
        pass
