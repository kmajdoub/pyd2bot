from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class WatchFightSequence(AbstractBehavior):
    
    def __init__(self):
        super().__init__()
        self._active_sequences = 0
    
    def run(self) -> bool:
        self.once(KernelEvent.FightSequenceStart, self._on_fight_sequence_start)
        self.once(KernelEvent.FightSequenceEnd, self._on_fight_sequence_end)

    def _on_fight_sequence_start(self, event) -> None:
        self._active_sequences += 1

    def _on_fight_sequence_end(self, event) -> None:
        self._active_sequences = max(0, self._active_sequences - 1)
        if self._active_sequences == 0:
            if Kernel().battleFrame.is_sequence_executing():
                Logger().info("Waiting for sequences to end before trigger sequence listeners")
                self.once(KernelEvent.SequenceExecFinished, lambda *_: self.callback(0))
                return True
            Logger().debug("Sequence finished")
            self.callback(0)
