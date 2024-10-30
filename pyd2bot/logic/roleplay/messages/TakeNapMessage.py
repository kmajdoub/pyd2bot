from pydofus2.com.ankamagames.jerakine.messages.Message import Message

class TakeNapMessage(Message):
    """Message sent from leader to followers to coordinate nap times"""
    def __init__(self, nap_duration: int):
        super().__init__()
        if not isinstance(nap_duration, int) or nap_duration <= 0:
            raise ValueError(f"Invalid nap duration: {nap_duration}. Must be positive integer.")
        self.nap_duration = nap_duration
