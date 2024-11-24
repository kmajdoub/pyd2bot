from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import ConnectionsHandler
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapRunningFightDetailsMessage import MapRunningFightDetailsMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.MapRunningFightDetailsRequestMessage import MapRunningFightDetailsRequestMessage


class GetMapFightDetails(AbstractBehavior):
    def __init__(self):
        super().__init__()

    def run(self):
        self.on(KernelEvent.MapFightDetails, self._on_fight_details)
        self.results = []
        self._fights_processed = []
        self.process_next()
    
    def process_next(self):
        for fightId, fight in Kernel().roleplayEntitiesFrame._fights.items():
            if fightId not in self._fights_processed:
                self._fights_processed.append(fightId)
                msg = MapRunningFightDetailsRequestMessage()
                msg.init(fightId)
                ConnectionsHandler().send(msg)
                return
        self.finish(0, None, self.results)
    
    def _on_fight_details(self, event, msg: MapRunningFightDetailsMessage):
        self.results.append(msg)
        self._fights_processed.append(msg.fightId)
        self.process_next()
