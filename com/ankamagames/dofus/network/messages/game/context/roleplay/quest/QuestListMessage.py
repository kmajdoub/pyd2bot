from com.ankamagames.dofus.network.messages.NetworkMessage import NetworkMessage
from com.ankamagames.dofus.network.types.game.context.roleplay.quest.QuestActiveInformations import QuestActiveInformations


class QuestListMessage(NetworkMessage):
    protocolId = 5774
    finishedQuestsIds:list[int]
    finishedQuestsCounts:list[int]
    activeQuests:list[QuestActiveInformations]
    reinitDoneQuestsIds:list[int]
    
