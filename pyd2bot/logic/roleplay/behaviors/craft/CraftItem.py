from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.Listener import Listener


class CraftItem(AbstractBehavior):

    def __init__(self):
        self.guestDisconnectedListener: Listener = None
        super().__init__()

    def run(self, bank, atelier, itemId) -> bool:
        self.atelier = atelier
        self.itemId = itemId
        self.bank = bank
        self.unLoad()
    
    def unLoad(self):
        def onBankUnload(code, err):
            if err:
                pass
            self.retrieveRecepie()
        
    def retrieveRecepie(self):
        def onretrieve(code, err):
            if err:
                pass
            self.goToAtelier()