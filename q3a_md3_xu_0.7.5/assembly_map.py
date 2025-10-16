#Example = [
#    object group,
#    parent tag,
#    child tags,
#    frame strips
#]

WEAPON = [
    "w_",
    "tag_weapon",
    ["tag_barrel", "tag_flash"],
    None
]

WEAPON_BARREL = [
    "wb_",
    "tag_barrel",
    ["tag_weapon","tag_flash"],
    None
]

WEAPON_FLASH = [
    "wf_",
    "tag_weapon",
    ["tag_barrel", "tag_flash"],
    None
]

WEAPON_HAND = [
    "wh_",
    "tag_weapon",
    ["tag_barrel", "tag_flash"],
    [0, 1, 2]
]

HEAD = [
    "h_",
    "tag_head",
    None,
    None
]

UPPER = [
    "u_",
    "tag_torso", 
    ["tag_head", "tag_weapon", "tag_flag"],
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 22, 23, 24, 25, 26, 27]
    
]

LOWER = [
    "l_",
    "tag_floor", 
    "tag_torso",
    [0, 1, 2, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
]

#Action list for template generation and for animation.cfg mapping.
#strip number, name, special command (1=make dead from last frame, 8=loop frames)
ACTIONS = [
    [0, "BOTH_DEATH1", 1],
    [1, "BOTH_DEATH2", 1],
    [2, "BOTH_DEATH3", 1],
    [3, "TORSO_GESTURE"],
    [4, "TORSO_ATTACK"],
    [5, "TORSO_ATTACK2"],
    [6, "TORSO_DROP"],
    [7, "TORSO_RAISE"],
    [8, "TORSO_STAND"],
    [9, "TORSO_STAND2"],
    [10, "LEGS_WALKCR", 8],
    [11, "LEGS_WALK", 8],
    [12, "LEGS_RUN", 8],
    [13, "LEGS_BACK", 8],
    [14, "LEGS_SWIM", 8],
    [15, "LEGS_JUMP"],
    [16, "LEGS_LAND"],
    [17, "LEGS_JUMPB"],
    [18, "LEGS_LANDB"],
    [19, "LEGS_IDLE", 8],
    [20, "LEGS_IDLECR", 8],
    [21, "LEGS_TURN", 8],
    [22, "TORSO_GETFLAG"],
    [23, "TORSO_GUARDBASE"],
    [24, "TORSO_PATROL"],
    [25, "TORSO_FOLLOWME"],
    [26, "TORSO_AFFIRMATIVE"],
    [27, "TORSO_NEGATIVE"]
]

ASSEMBLY_RULES = [HEAD, UPPER, LOWER, WEAPON, WEAPON_BARREL, WEAPON_FLASH, WEAPON_HAND]
