

from enum import Enum
from time import sleep
from typing import TYPE_CHECKING

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.skill.UseSkill import UseSkill
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import \
    KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.net.ConnectionsHandler import \
    ConnectionsHandler
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import \
    PlayerManager
from pydofus2.com.ankamagames.dofus.network.enums.CharacterCreationResultEnum import \
    CharacterCreationResultEnum
from pydofus2.com.ankamagames.dofus.network.messages.game.character.choice.CharacterFirstSelectionMessage import \
    CharacterFirstSelectionMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.character.creation.CharacterCreationRequestMessage import \
    CharacterCreationRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.character.creation.CharacterNameSuggestionRequestMessage import \
    CharacterNameSuggestionRequestMessage
from pydofus2.com.ankamagames.dofus.network.messages.game.context.roleplay.quest.GuidedModeQuitRequestMessage import \
    GuidedModeQuitRequestMessage
from pydofus2.com.ankamagames.jerakine.data.I18n import I18n
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

if TYPE_CHECKING:
    pass

class NewCharacterStates(Enum):
    GET_NAME_SUGGESTION = -1 
    CHARACTER_CREATION = 0
    CHARACTER_SELECTION = 1
    TUTORIAL = 2
    MOVING_TO_ASTRUB = 3
    OUT_OF_TUTORIAL = 4

class CreateNewCharacter(AbstractBehavior):
    NAME_SUGGESTION_FAILED = 6991
    CHARACTER_CREATION_FAILED = 6992
    CREATED_CHARACTER_NOTFOUND = 6993
    CRATE_CHARACTER_TIMEOUT = 6994
    
    def __init__(self) -> None:
        super().__init__()
        self.requestTimer = None

    def run(self, breedId, name=None, sex=False) -> bool:
        self.name = name
        self.breedId = breedId
        self.sex = sex
        self.character = None
        self.nbrFails = 0
        self.charNameSuggListener = None
        self.charNameSuggFailListener = None
        Logger().info(f"New character breedId {breedId}, name {name}, sex {sex}.")
        if self.name is None:
            self.askNameSuggestion()
        else:
            self.requestNewCharacter()

    def onCharacterNameSuggestion(self, event, suggestion):
        self.name = suggestion
        KernelEventsManager().removeListener(KernelEvent.CharacterNameSuggestionFailed, self.charNameSuggFailListener)
        self.requestNewCharacter()

    def onCharacterNameSuggestionFail(self, event):
        self.nbrFails += 1
        if self.nbrFails > 3:
            KernelEventsManager().removeListener(KernelEvent.CharacterNameSuggestion, self.charNameSuggListener)
            return self.finish(self.NAME_SUGGESTION_FAILED, "failed to get character name suggestion")
        sleep(3)
        KernelEventsManager().once(KernelEvent.CharacterNameSuggestionFailed, self.onCharacterNameSuggestionFail, originator=self)
        msg = CharacterNameSuggestionRequestMessage()
        msg.init()
        ConnectionsHandler().send(msg)
    
    def askNameSuggestion(self):
        self.charNameSuggListener = KernelEventsManager().once(KernelEvent.CharacterNameSuggestion, self.onCharacterNameSuggestion, originator=self)
        self.charNameSuggFailListener = KernelEventsManager().once(KernelEvent.CharacterNameSuggestionFailed, self.onCharacterNameSuggestionFail, originator=self)
        msg = CharacterNameSuggestionRequestMessage()
        msg.init()
        ConnectionsHandler().send(msg)
        self.state = NewCharacterStates.GET_NAME_SUGGESTION

    def onNewCharacterResult(self, event, result, reason):
        if result > 0:
            if result == CharacterCreationResultEnum.ERR_INVALID_NAME:
                errorMsg = "Invalid Name : " + I18n.getUiText("ui.charcrea.invalidNameReason" + str(reason))
            elif result == CharacterCreationResultEnum.ERR_NOT_ALLOWED:
                errorMsg = "You need to subscribed : " + I18n.getUiText("ui.popup.charcrea.notSubscriber")
            elif result == CharacterCreationResultEnum.ERR_TOO_MANY_CHARACTERS:
                errorMsg = "No character slots available : " + I18n.getUiText("ui.popup.charcrea.tooManyCharacters")
            elif result == CharacterCreationResultEnum.ERR_NO_REASON:
                errorMsg = "Unexpected reason : " + I18n.getUiText("ui.popup.charcrea.noReason")
            elif result == CharacterCreationResultEnum.ERR_RESTRICTED_ZONE:
                errorMsg = "Charactezr deletion in unsecure mode : " + I18n.getUiText("ui.charSel.deletionErrorUnsecureMode")
            self.finish(self.CHARACTER_CREATION_FAILED, f"Create character error : {errorMsg}")
        else:
            KernelEventsManager().once(KernelEvent.CharactersList, self.onCharacterList, originator=self)

    def onMapProcessed(self):
        if self.state == NewCharacterStates.CHARACTER_SELECTION:
            KernelEventsManager().onceMapProcessed(self.onMapProcessed, originator=self)
            def onquest(event, msg):
                msg = GuidedModeQuitRequestMessage()
                self.state = NewCharacterStates.TUTORIAL
                ConnectionsHandler().send(msg)
            KernelEventsManager().once(KernelEvent.QuestStart, onquest, originator=self)
        elif self.state == NewCharacterStates.TUTORIAL:
            KernelEventsManager().onceMapProcessed(self.onMapProcessed, originator=self)
            self.state = NewCharacterStates.OUT_OF_TUTORIAL
        elif self.state == NewCharacterStates.OUT_OF_TUTORIAL:
            def onSkillUsed(status, error):
                if error:
                   return self.finish(status, error)
                KernelEventsManager().onceMapProcessed(lambda:self.finish(True, None, character=self.character), mapId=152046597, originator=self)
            UseSkill().start(None, elementId=489318, skilluid=148931090, waitForSkillUsed=True, callback=onSkillUsed, parent=self)
        
    def onCharacterList(self, event, return_value):
        for ch in PlayerManager().charactersList:
            if ch.name == self.name: 
                KernelEventsManager().onceMapProcessed(self.onMapProcessed, originator=self)
                self.character = ch
                msg = CharacterFirstSelectionMessage()
                msg.init(True, ch.id)
                ConnectionsHandler().send(msg)
                self.state = NewCharacterStates.CHARACTER_SELECTION
                return
        self.finish(self.CREATED_CHARACTER_NOTFOUND, "The created character is not found in characters list")                

    def requestNewCharacter(self):
        def onTimeout():
            self.finish(self.CREATE_CHARACTER_TIMEOUT, "Request character create timedout")
        KernelEventsManager().once(KernelEvent.CharacterCreationResult, self.onNewCharacterResult, timeout=10, ontimeout=onTimeout, originator=self)
        msg = CharacterCreationRequestMessage()
        msg.init(str(self.name), int(self.breedId), bool(self.sex), [12215600, 12111183, 4803893, 9083451, 13358995], 153)
        ConnectionsHandler().send(msg)
        self.state = NewCharacterStates.CHARACTER_CREATION
