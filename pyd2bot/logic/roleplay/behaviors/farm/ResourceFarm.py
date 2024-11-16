from typing import List
from prettytable import PrettyTable

from pyd2bot.logic.roleplay.behaviors.farm.AbstractFarmBehavior import \
    AbstractFarmBehavior
from pyd2bot.logic.roleplay.behaviors.farm.CollectableResource import \
    CollectableResource
from pyd2bot.logic.roleplay.behaviors.farm.ResourcesTracker import ResourceTracker
from pyd2bot.logic.roleplay.behaviors.mount.PutPetsMount import PutPetsMount
from pyd2bot.logic.roleplay.behaviors.quest.UseItemsByType import UseItemsByType
from pyd2bot.logic.roleplay.behaviors.skill.UseSkill import UseSkill
from pyd2bot.farmPaths.AbstractFarmPath import AbstractFarmPath
from pyd2bot.data.models import JobFilter
from pyd2bot.logic.roleplay.behaviors.updates.CollectStats import CollectStats
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent

from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import \
    ItemWrapper
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.game.common.managers.PlayedCharacterManager import \
    PlayedCharacterManager
from pydofus2.com.ankamagames.dofus.logic.game.roleplay.types.MovementFailError import \
    MovementFailError
from pydofus2.com.ankamagames.dofus.network.enums.PlayerStatusEnum import \
    PlayerStatusEnum
from pydofus2.com.ankamagames.dofus.network.types.game.context.roleplay.GuildInformations import \
    GuildInformations
from pydofus2.com.ankamagames.jerakine.benchmark.BenchmarkTimer import \
    BenchmarkTimer
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger

class ResourceFarm(AbstractFarmBehavior):
    RESOURCE_BAGS_TYPE_ID = 100
    
    def __init__(self, path: AbstractFarmPath, jobFilters: List[JobFilter], timeout=None):
        super().__init__(timeout)
        self.jobFilters = jobFilters
        self.path = path
        self.deadEnds = set()
        self.resource_tracker = ResourceTracker(expiration_days=30)
        self.session_paused = False  # Track session pause state locally

    def init(self):
        self.path.init()
        self.currentTarget: CollectableResource = None
        self.current_session_id = self.resource_tracker.start_farm_session(self.path.name)
        self.session_resources = {}
        CollectStats().sessionStats.currentPathName = self.path.name
        CollectStats().onPlayerUpdate(KernelEvent.FarmPathStart)

    def onPartyInvited(self, event, partyId, partyType, fromId, fromName):
        Logger().warning(f"Player invited to party {partyId} by {fromName}")
        Kernel().partyFrame.sendPartyInviteCancel(fromId)

    def onGuildInvited(self, event, guildInfo: GuildInformations, recruterName):
        Logger().warning(f"Player invited to guild {guildInfo.guildName} by {recruterName}")
        Kernel().guildDialogFrame.guildInvitationAnswer(False)

    def _specific_checks(self):
        if self._check_has_resources_bags():
            return True
        if self._check_solo_mod():
            return True
        if not PlayedCharacterManager().isPetsMounting and PutPetsMount.has_items():
            Logger().debug("player has available non equiped pet mount")
            PutPetsMount().start(callback=lambda *_: self.main())
            return True
        return False
    
    def _check_solo_mod(self):
        if Kernel().socialFrame._current_mod != PlayerStatusEnum.PLAYER_STATUS_SOLO:
            Kernel().socialFrame.updateStatus(PlayerStatusEnum.PLAYER_STATUS_SOLO, self._on_player_solo_mod)
            return True
        return False

    def _check_has_resources_bags(self):
        if UseItemsByType.has_items(self.RESOURCE_BAGS_TYPE_ID):
            self.use_items_of_type(self.RESOURCE_BAGS_TYPE_ID, lambda *_: self.main())
            return True
        return False
        
    def _on_full_pods(self):
        # Pause session timing during inventory management
        if self.current_session_id is not None:
            self.session_paused = True
            self.resource_tracker.pause_session(self.current_session_id)

        self.retrieve_sell({39: 100}, callback=self._on_selling_over)
    
    def _on_selling_over(self, code, error):
        # Resume session timing after inventory management
        if self.current_session_id is not None:
            self.session_paused = False
            self.resource_tracker.resume_session(self.current_session_id)
            
        if error:
            return self.finish(code, error)
        self.main()  # Continue farming
    
    def _on_player_solo_mod(self, code, error):
        if error:
            Logger().error(error)
        self.main()  # Continue farming
    
    def finish(self, code, error):
        # after shutdown save how much collected during the session
        if self.current_session_id is not None:
            self.resource_tracker.end_farm_session(
                self.current_session_id,
                self.session_resources
            )
        super().finish(code, error)

    def makeAction(self):
        '''
        This function is called when the bot is ready to make an action. 
        It will select the next resource to farm and move to it.
        '''
        available_resources = self.getAvailableResources()
        possibleOutgoingEdges = [e for e in self.path.outgoingEdges() if e not in self.deadEnds]
        if len(available_resources) == 0 and len(possibleOutgoingEdges) == 1:
            Logger().warning("Farmer found dead end")
            self.deadEnds.add(self._currEdge)
            self._move_to_next_step()
            return
        farmable_resources = [r for r in available_resources if r.canFarm(self.jobFilters)]
        nonForbiddenResources = [r for r in farmable_resources if r.uid not in self.forbiddenActions]
        nonForbiddenResources.sort(key=lambda r: r.distance)
        if len(nonForbiddenResources) == 0:
            Logger().info("No farmable resource found")
            self._move_to_next_step()
        else:
            self.logResourcesTable(nonForbiddenResources)
            self.currentTarget = nonForbiddenResources[0]
            self.use_skill(
                elementId=self.currentTarget.resource.id,
                skilluid=self.currentTarget.resource.interactiveSkill.skillInstanceUid,
                cell=self.currentTarget.nearestCell.cellId,
                callback=self.onResourceCollectEnd
            )
        
    def onObjectAdded(self, event, iw: ItemWrapper, qty: int):
        if self.session_paused:
            return
        
        resource_id = str(iw.objectGID)
        self.session_resources[resource_id] = self.session_resources.get(resource_id, 0) + qty
        averageKamasWon = (
            Kernel().averagePricesFrame.getItemAveragePrice(iw.objectGID) * qty
        )
        Logger().debug(f"Average kamas won: {averageKamasWon}")
        
        if self.current_session_id is not None:
            self.resource_tracker.update_session_collected_resources(self.current_session_id, resource_id, qty)
            
        self.send(KernelEvent.ObjectObtainedInFarm, iw.objectGID, qty, averageKamasWon)

    def onResourceCollectEnd(self, code, error, iePosition=None):
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
        BenchmarkTimer(0.5, self.main).start()

    def getAvailableResources(self) -> list[CollectableResource]:
        if not Kernel().interactiveFrame:
            Logger().error("No interactive frame found")
            return None
        collectables = Kernel().interactiveFrame.collectables.values()

         # Track resources for current vertex
        resources_ids = [it.skill.gatheredRessource.id for it in collectables]
        self.resource_tracker.update_vertex_resources(PlayedCharacterManager().currVertex, resources_ids)
        
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
