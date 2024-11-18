 
 
 
from hashlib import md5

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.network.messages.game.character.deletion.CharacterDeletionPrepareRequestMessage import \
    CharacterDeletionPrepareRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.character.deletion.CharacterDeletionRequestMessage import \
    CharacterDeletionRequestMessage
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class DeleteCharacter(AbstractBehavior):
    
    def __init__(self) -> None:
        super().__init__()

    def run(self, characterId) -> bool:
        self.characterId = characterId
        Logger().info("[CreateNewCharacter] Started.")
        self.sendPrepareDeletionRequest(characterId)

    def sendPrepareDeletionRequest(self, characterId):
        msg = CharacterDeletionPrepareRequestMessage()
        msg.init(characterId)
        def onCharDelPrepared(event, msg):
            self.sendCharDeleteRequest(characterId)
        KernelEventsManager().on(KernelEvent.CharacterDelPrepare, onCharDelPrepared)
        ConnectionsHandler().send(msg)

    def sendCharDeleteRequest(self, characterId):
        cdrmsg = CharacterDeletionRequestMessage()
        answer = f"{characterId}~000000000000000000"
        answerhash =  md5(answer.encode()).hexdigest()
        cdrmsg.init(characterId, answerhash)
        def oncharList(event, return_value):
            Logger().info(f"Characters list : {[(c.id, c.name) for c in return_value]}")
            for c in return_value:
                if c == characterId:
                    return self.finish(False, "Character wasent deleted and still in chars list")
            self.finish(0)
        KernelEventsManager().once(KernelEvent.CharactersList, oncharList, originator=self)
        ConnectionsHandler().send(cdrmsg)