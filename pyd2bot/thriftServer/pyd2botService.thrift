typedef i32 int

struct Vertex {
    1: double mapId,
    2: int zoneId,
    3: optional bool onlyDirections
}

enum SessionStatus {
    CRASHED = 0
    TERMINATED = 1
    RUNNING = 2
    DISCONNECTED = 3
    AUTHENTICATING = 4
    FIGHTING = 5
    ROLEPLAYING = 6
    LOADING_MAP = 7
    PROCESSING_MAP = 8
    OUT_OF_ROLEPLAY = 9
    IDLE = 10
}

struct JobFilter {
    1: i32 jobId,
    2: list<i32> resoursesIds
}

struct RunSummary {
    1: string login,
    2: i64 startTime,
    3: i64 totalRunTime,
    4: string sessionId,
    5: optional string leaderLogin,
    6: i32 numberOfRestarts,
    7: string status,
    8: optional string statusReason,
    9: required int earnedKamas,
    10: required int nbrFightsDone,
    11: required int earnedLevels,
}

struct CharacterDetails {
    1: required int level,
    2: required int hp,
    3: required Vertex vertex,
    4: required i64 kamas,
    5: required string areaName,
    6: required string subAreaName,
    7: required int cellId,
    8: required int mapX,
    9: required int mapY,
    10: required int inventoryWeight,
    11: required int shopWeight,
    12: required int inventoryWeightMax,
}

struct Server {
    1: int id,
    2: string name,
    3: int status,
    4: int completion,
    5: int charactersCount,
    6: int charactersSlots,
    7: double date,
    8: bool isMonoAccount,
    9: bool isSelectable,
}

struct Breed {
    1: int id,
    2: string name
}

enum SessionType {
    FIGHT = 0,
    FARM = 1,
    SELL = 3,
    TREASURE_HUNT = 4,
    MIXED = 5,
    MULE_FIGHT = 6,
    MULTIPLE_PATHS_FARM = 7,
}

enum TransitionType {
    SCROLL = 1,
    SCROLL_ACTION = 2,
    MAP_EVENT = 4,
    MAP_ACTION = 8,
    MAP_OBSTACLE = 16,
    INTERACTIVE = 32,
    NPC_ACTION = 64
}

enum UnloadType {
    BANK = 0,
    STORAGE = 1,
    SELLER = 2
}

enum PathType {
    RandomSubAreaFarmPath = 0,
    RandomAreaFarmPath=2,
    CyclicFarmPath = 1,
    CustomRandomFarmPath = 3,
}

struct Path {
    1: string id,
    2: PathType type,
    3: optional Vertex startVertex,
    4: optional list<TransitionType> transitionTypeWhitelist,
    5: optional list<int> subAreaBlacklist,
    6: optional list<int> mapIds,
}

struct Spell {
    1:int id,
    2:string name
}

struct Character {
    1: string name,
    2: double id,
    3: int level,
    4: int breedId,
    5: string breedName,
    6: int serverId,
    7: string serverName,
    8: optional string login,
    9: optional int accountId,
}

struct Certificate {
    1: int id,
    2: string hash,
}

struct Session {
    1: string id,
    2: optional Character leader,
    3: optional list<Character> followers,
    4: SessionType type,
    5: UnloadType unloadType,
    6: optional Character seller,
    7: optional Path path,
    8: optional double monsterLvlCoefDiff,
    9: optional list<JobFilter> jobFilters,
    10: string apikey,
    11: Character character,
    12: optional Certificate cert,
    13: optional list<Path> pathsList,
}

exception DofusError {
    1: int code,
    2: string message
}

service Pyd2botService {
    string ping() throws (1: DofusError error),
    list<Character> fetchCharacters(1: string token) throws (1: DofusError error),
    list<Server> fetchUsedServers(1: string token) throws (1: DofusError error),
    void runSession(1: string token, 6:Session session) throws (1: DofusError error),
    list<Spell> fetchBreedSpells(1: int breedId) throws (1: DofusError error),
    string fetchJobsInfosJson() throws (1: DofusError error),
    bool deleteCharacter(1: string token, 2: int serverId, 3: int characterId) throws (1: DofusError error),
    Character createCharacter(1: string token, 2: int serverId, 3: string name, 4: int breedId, 5: bool sex, 6: bool moveOutOfIncarnam) throws (1: DofusError error)
    list<Breed> getBreeds() throws (1: DofusError error),
    list<Server> getServers(1: string token) throws (1: DofusError error),
    CharacterDetails fetchCharacterDetails(1: string token, 2: i32 serverId, 3: i32 characterId) throws (1: DofusError error)
    bool addSession(1: Session session) throws (1: DofusError error),
    bool startSession(1: Session session) throws (1: DofusError error),
    bool stopSession(1: string sessionId) throws (1: DofusError error),
    list<RunSummary> getRunSummary() throws (1: DofusError error),
    RunSummary getCharacterRunSummary(1: string login) throws (1: DofusError error),
    list<RunSummary> getSessionRunSummary(1: string sessionId) throws (1: DofusError error)
}
       
    