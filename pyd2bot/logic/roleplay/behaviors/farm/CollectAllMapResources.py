from enum import Enum, auto
import threading
from typing import List
from prettytable import PrettyTable

from pyd2bot.logic.roleplay.behaviors.AbstractBehavior import AbstractBehavior
from pyd2bot.logic.roleplay.behaviors.farm.CollectableResource import \
    CollectableResource
from pyd2bot.logic.roleplay.behaviors.farm.ResourcesTracker import ResourceTracker
from pyd2bot.logic.roleplay.behaviors.inventory.UseItemsByType import UseItemsByType
from pyd2bot.logic.roleplay.behaviors.skill.UseSkill import UseSkill
from pyd2bot.data.models import JobFilter
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.internalDatacenter.DataEnum import DataEnum
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.types.MovementFailError import \
    MovementFailError
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

class CollectAllMapResources(AbstractBehavior):
    
    class errors(Enum):
        MAP_CHANGED = auto()
        PLAYER_DEAD = auto()
        FULL_PODS = auto()
        
    RESOURCES_TO_COLLECT_SELL = {
        DataEnum.FISH_TYPE_ID: 100, 
        DataEnum.WOOD_TYPE_ID: 100, 
        DataEnum.ORES_TYPE_ID: 100,
        DataEnum.PLANTS_TYPE_ID: 100
    }

    def __init__(self, jobFilters: List[JobFilter]=[]):
        super().__init__()
        self.jobFilters = jobFilters
        self.currentTarget: CollectableResource = None
        self.forbiddenActions = set()
        self._stop_sig = threading.Event()
        self.inFight = threading.Event()

    def run(self, *args, **kwargs):
        self.initListeners()
        self.main()

    def stop(self, clear_callback=False):
        self._stop_sig.set()

    def initListeners(self):
        self.on(KernelEvent.FightStarted, self._on_fight)

    def _on_fight(self, event=None):
        Logger().warning(f"Player entered in a fight.")
        KernelEventsManager().clear_all_by_origin(self)
        self.stop_children(True)
        self.inFight.set()

    def _on_roleplay_started_after_fight(self, event=None):
        Logger().debug(f"Player ended fight and started roleplay")
        self.initListeners()
        self.inFight.clear()
        self.once_map_rendered(self._on_map_rendered_after_fight)

    def _on_map_rendered_after_fight(self):
        curr_vertex = PlayedCharacterManager().currVertex.mapId
        if self.currentVertex != curr_vertex:
            error_text = f"Vertex loaded after fight {curr_vertex}, is not the vertex player was on when farming the resources!"
            Logger().warning(error_text)
            return self.finish(self.errors.MAP_CHANGED, error_text)
        Kernel().defer(self.main)

    def main(self, event_code=None, error=None):
        Logger().debug(f"Farmer main loop called")

        if self._stop_sig.is_set():
            Logger().warning("User wanted to stop CollectAllMapResources!")
            self.stop_children(True)
            return self.finish(0)

        if not self.running.is_set():
            Logger().error(f"CollectAllMapResources is not running anymore!")
            return

        if self.inFight.is_set():
            Logger().warning("Stopping farm loop because we entered a fight!")
            return

        if PlayedCharacterManager().is_dead():
            return self.finish(self.errors.PLAYER_DEAD, "Can't collect resources when Player is dead!")

        if PlayedCharacterManager().isPodsFull():
            return self.finish(self.errors.FULL_PODS, "Inventory is almost full")

        if UseItemsByType.has_items(DataEnum.RESOURCE_BAGS_TYPE_ID):
            self.use_items_of_type(DataEnum.RESOURCE_BAGS_TYPE_ID, lambda *_: self.main())
            return True

        self._collect_resources()

    def _collect_resources(self):
        available_resources = self.getAvailableResources()
        farmable_resources = [r for r in available_resources if r.canFarm(self.jobFilters)]
        nonForbiddenResources = [r for r in farmable_resources if r.uid not in self.forbiddenActions]
        if len(nonForbiddenResources) == 0:
            Logger().info("No farmable resource found")
            self.finish(0)
        else:
            nonForbiddenResources.sort(key=lambda r: r.distance)
            self.logResourcesTable(nonForbiddenResources)
            self.currentTarget = nonForbiddenResources[0]
            self.currentVertex = PlayedCharacterManager().currVertex
            self.use_skill(
                elementId=self.currentTarget.resource.id,
                skilluid=self.currentTarget.resource.interactiveSkill.skillInstanceUid,
                cell=self.currentTarget.nearestCell.cellId,
                callback=self._on_resource_collected
            )

    def _on_resource_collected(self, code, error, iePosition=None):
        if not self.running.is_set():
            return

        if error:
            if code in [UseSkill.ELEM_BEING_USED, UseSkill.ELEM_TAKEN]:
                Logger().warning(f"Error while collecting resource: {error}, not a fatal error, restarting.")
                return self.requestMapData(callback=lambda code, err: self.main())
            if code in [
                UseSkill.CANT_USE,
                UseSkill.USE_ERROR,
                UseSkill.NO_ENABLED_SKILLS,
                UseSkill.ELEM_UPDATE_TIMEOUT,
                MovementFailError.MOVE_REQUEST_REJECTED,
            ]:
                Logger().warning(f"Error while collecting resource: {error}, will exclude the resource.")
                self.forbiddenActions.add(self.currentTarget.uid)
                return Kernel().defer(self.main)
            return self.send(KernelEvent.ClientShutdown, error)
        BenchmarkTimer(0.25, self.main).start()

    def getAvailableResources(self) -> list[CollectableResource]:
        if not Kernel().interactiveFrame:
            Logger().error("No interactive frame found")
            return None

        collectables = Kernel().interactiveFrame.collectables.values()
        resources_ids = [it.skill.gatheredRessource.id for it in collectables]
        ResourceTracker().update_vertex_resources(PlayedCharacterManager().currVertex, resources_ids)
        collectableResources = [CollectableResource(it) for it in collectables]
        return collectableResources

    def logResourcesTable(self, resources: list[CollectableResource]):
        if resources:
            headers = ["jobName", "resourceName", "enabled", "reachable", "canFarm", ]
            summaryTable = PrettyTable(headers)
            for e in resources:
                summaryTable.add_row(
                    [
                        e.resource.skill.parentJob.name,
                        e.resource.skill.gatheredRessource.name,
                        e.resource.enabled,
                        e.reachable,
                        e.canFarm(self.jobFilters)
                    ]
                )
            Logger().debug(f"Available resources :\n{summaryTable}")
