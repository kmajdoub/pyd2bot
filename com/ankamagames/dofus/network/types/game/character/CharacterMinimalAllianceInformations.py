from com.ankamagames.dofus.network.types.game.character.CharacterMinimalGuildInformations import CharacterMinimalGuildInformations
from com.ankamagames.dofus.network.types.game.context.roleplay.BasicAllianceInformations import BasicAllianceInformations


class CharacterMinimalAllianceInformations(CharacterMinimalGuildInformations):
    protocolId = 4354
    alliance:BasicAllianceInformations
    
    
