from com.ankamagames.dofus.network.types.game.character.characteristic.CharacterCharacteristic import CharacterCharacteristic


class CharacterCharacteristicDetailed(CharacterCharacteristic):
    protocolId = 9089
    base:int
    additional:int
    objectsAndMountBonus:int
    alignGiftBonus:int
    contextModif:int
    
    
