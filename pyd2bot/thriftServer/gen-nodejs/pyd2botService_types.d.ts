//
// Autogenerated by Thrift Compiler (0.16.0)
//
// DO NOT EDIT UNLESS YOU ARE SURE THAT YOU KNOW WHAT YOU ARE DOING
//
import thrift = require('thrift');
import Thrift = thrift.Thrift;
import Q = thrift.Q;
import Int64 = require('node-int64');


declare enum SessionStatus {
  CRASHED = 0,
  TERMINATED = 1,
  RUNNING = 2,
  DISCONNECTED = 3,
  AUTHENTICATING = 4,
  FIGHTING = 5,
  ROLEPLAYING = 6,
  LOADING_MAP = 7,
  PROCESSING_MAP = 8,
  OUT_OF_ROLEPLAY = 9,
  IDLE = 10,
}

declare enum SessionType {
  FIGHT = 0,
  FARM = 1,
  SELL = 3,
  TREASURE_HUNT = 4,
  MIXED = 5,
}

declare enum TransitionType {
  SCROLL = 1,
  SCROLL_ACTION = 2,
  MAP_EVENT = 4,
  MAP_ACTION = 8,
  MAP_OBSTACLE = 16,
  INTERACTIVE = 32,
  NPC_ACTION = 64,
}

declare enum UnloadType {
  BANK = 0,
  STORAGE = 1,
  SELLER = 2,
}

declare enum PathType {
  RandomSubAreaFarmPath = 0,
  RandomAreaFarmPath = 2,
  CyclicFarmPath = 1,
}

declare class Vertex {
    public mapId: number;
    public zoneId: number;
    public onlyDirections?: boolean;

      constructor(args?: { mapId: number; zoneId: number; onlyDirections?: boolean; });
  }

declare class JobFilter {
    public jobId: number;
    public resoursesIds: number[];

      constructor(args?: { jobId: number; resoursesIds: number[]; });
  }

declare class RunSummary {
    public login: string;
    public startTime: Int64;
    public totalRunTime: Int64;
    public sessionId: string;
    public leaderLogin?: string;
    public numberOfRestarts: number;
    public status: string;
    public statusReason?: string;
    public earnedKamas: number;
    public nbrFightsDone: number;
    public earnedLevels: number;

      constructor(args?: { login: string; startTime: Int64; totalRunTime: Int64; sessionId: string; leaderLogin?: string; numberOfRestarts: number; status: string; statusReason?: string; earnedKamas: number; nbrFightsDone: number; earnedLevels: number; });
  }

declare class CharacterDetails {
    public level: number;
    public hp: number;
    public vertex: Vertex;
    public kamas: Int64;
    public areaName: string;
    public subAreaName: string;
    public cellId: number;
    public mapX: number;
    public mapY: number;
    public inventoryWeight: number;
    public shopWeight: number;
    public inventoryWeightMax: number;

      constructor(args?: { level: number; hp: number; vertex: Vertex; kamas: Int64; areaName: string; subAreaName: string; cellId: number; mapX: number; mapY: number; inventoryWeight: number; shopWeight: number; inventoryWeightMax: number; });
  }

declare class Server {
    public id: number;
    public name: string;
    public status: number;
    public completion: number;
    public charactersCount: number;
    public charactersSlots: number;
    public date: number;
    public isMonoAccount: boolean;
    public isSelectable: boolean;

      constructor(args?: { id: number; name: string; status: number; completion: number; charactersCount: number; charactersSlots: number; date: number; isMonoAccount: boolean; isSelectable: boolean; });
  }

declare class Breed {
    public id: number;
    public name: string;

      constructor(args?: { id: number; name: string; });
  }

declare class Path {
    public id: string;
    public type: PathType;
    public startVertex?: Vertex;
    public transitionTypeWhitelist?: TransitionType[];
    public subAreaBlacklist?: number[];

      constructor(args?: { id: string; type: PathType; startVertex?: Vertex; transitionTypeWhitelist?: TransitionType[]; subAreaBlacklist?: number[]; });
  }

declare class Spell {
    public id: number;
    public name: string;

      constructor(args?: { id: number; name: string; });
  }

declare class Character {
    public name: string;
    public id: number;
    public level: number;
    public breedId: number;
    public breedName: string;
    public serverId: number;
    public serverName: string;
    public login?: string;
    public accountId?: number;

      constructor(args?: { name: string; id: number; level: number; breedId: number; breedName: string; serverId: number; serverName: string; login?: string; accountId?: number; });
  }

declare class Session {
    public id: string;
    public leader: Character;
    public followers?: Character[];
    public type: SessionType;
    public unloadType: UnloadType;
    public seller?: Character;
    public path?: Path;
    public monsterLvlCoefDiff?: number;
    public jobFilters?: JobFilter[];

      constructor(args?: { id: string; leader: Character; followers?: Character[]; type: SessionType; unloadType: UnloadType; seller?: Character; path?: Path; monsterLvlCoefDiff?: number; jobFilters?: JobFilter[]; });
  }

declare class DofusError extends Thrift.TException {
    public code: number;
    public message: string;

      constructor(args?: { code: number; message: string; });
  }
