#Example = [
#    group,
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

ACTIONS = [
    "[00]BOTH_DEATH1[die]",
    "[01]BOTH_DEATH2[die]",
    "[02]BOTH_DEATH3[die]",
    "[03]TORSO_GESTURE",
    "[04]TORSO_ATTACK",
    "[05]TORSO_ATTACK2",
    "[06]TORSO_DROP",
    "[07]TORSO_RAISE",
    "[08]TORSO_STAND",
    "[09]TORSO_STAND2",
    "[10]LEGS_WALKCR[loop]",
    "[11]LEGS_WALK[loop]",
    "[12]LEGS_RUN[loop]",
    "[13]LEGS_BACK[loop]",
    "[14]LEGS_SWIM[loop]",
    "[15]LEGS_JUMP",
    "[16]LEGS_LAND",
    "[17]LEGS_JUMPB",
    "[18]LEGS_LANDB",
    "[19]LEGS_IDLE[loop]",
    "[20]LEGS_IDLECR[loop]",
    "[21]LEGS_TURN[loop]",
    "[22]TORSO_GETFLAG",  # TA
    "[23]TORSO_GUARDBASE",  # TA
    "[24]TORSO_PATROL",  # TA
    "[25]TORSO_FOLLOWME",  # TA
    "[26]TORSO_AFFIRMATIVE",  # TA
    "[27]TORSO_NEGATIVE"  # TA
]

ASSEMBLY_RULES = [HEAD, UPPER, LOWER, WEAPON, WEAPON_BARREL, WEAPON_FLASH, WEAPON_HAND]

# Collection function
def collect_assembly_groups(all_objects):
    """Collect objects into groups based on assembly rules"""
    groups = {}
    
    # Convert objects to dictionary for easy lookup
    object_dict = {obj.name: obj for obj in all_objects}
    
    for rule in ASSEMBLY_RULES:
        prefix, parent_tag_name, child_tags, action_strips = rule
        group_name = prefix.rstrip('_')  # "u_" -> "u"
        
        # Find all objects with this prefix
        prefix_objects = [obj for obj in all_objects if obj.name.startswith(prefix)]
        
        # Skip group if no prefix objects found
        if not prefix_objects:
            continue
            
        # Initialize group
        groups[group_name] = {
            'collected_objects': prefix_objects[:],
            'parent_tag': None,
            'child_tags': [],
            'action_strips': action_strips
        }
        
        # Add parent tag if required and exists
        if parent_tag_name and parent_tag_name in object_dict:
            parent_obj = object_dict[parent_tag_name]
            groups[group_name]['collected_objects'].append(parent_obj)
            groups[group_name]['parent_tag'] = parent_obj
        elif parent_tag_name:
            print(f"WARNING: Group '{group_name}' missing parent tag '{parent_tag_name}'")
        
        # Add child tags if they exist
        if child_tags:
            child_tag_list = child_tags if isinstance(child_tags, list) else [child_tags]
            for child_name in child_tag_list:
                if child_name in object_dict:
                    child_obj = object_dict[child_name]
                    groups[group_name]['collected_objects'].append(child_obj)
                    groups[group_name]['child_tags'].append(child_obj)
    
    return groups

# Helper functions
def print_assembly_groups(groups):
    """Print the collected groups in a readable format"""
    for group_name, group_data in groups.items():
        print(f"\n{group_name.upper()} Group:")
        print(f"  collected_objects: {[obj.name for obj in group_data['collected_objects']]}")
        print(f"  parent_tag: {group_data['parent_tag'].name if group_data['parent_tag'] else None}")
        print(f"  child_tags: {[child.name for child in group_data['child_tags']]}")
        print(f"  action_strips: {group_data['action_strips']}")

def get_character_groups(groups):
    """Get only character groups (head, upper, lower)"""
    character_groups = {}
    for group_name in ['h', 'u', 'l', 'w', 'wb', 'wf', 'wh']:
        if group_name in groups:
            character_groups[group_name] = groups[group_name]
    return character_groups

def get_group_frame_range(scene, group_data, modeltype):
    """Get the appropriate frame range for export (group-aware or single-file)"""
    if group_data and group_data.get('action_strips'):
        # Group export with specific strips
        return get_frames_from_strips(group_data['action_strips'])
    elif modeltype == "static":
        # Static model - just frame 0
        return [0]
    else:
        # Original animated export - full range
        return list(range(scene.frame_start, scene.frame_end + 1))

def get_frames_from_strips(strip_indices):
    """Get all frames from the specified NLA strip indices"""
    if not strip_indices:
        return [0]  # No animation strips - just frame 0
    
    # Find the Q3ANIM object
    q3anim_obj = get_q3anim_object()
    if not q3anim_obj:
        return [0]  # No Q3ANIM object found
    
    q3anim_track = q3anim_obj.animation_data.nla_tracks["Q3ANIM"]
    all_strips = list(q3anim_track.strips)
    
    # Get frames only from the strips specified for this group
    all_frames = set()
    for strip_idx in strip_indices:
        if strip_idx < len(all_strips):
            strip = all_strips[strip_idx]
            # Subtract 1 from start frame, keep end frame the same
            start_frame = max(0, int(strip.frame_start) + 1)  # Ensure we don't go below 0
            end_frame = int(strip.frame_end)
            
            # Add all frames in this adjusted range
            for frame in range(start_frame, end_frame + 1):
                all_frames.add(frame)
    
    return sorted(list(all_frames)) if all_frames else [0]

import bpy
def get_q3anim_object():
    """Find the object with Q3ANIM track"""
    for obj in bpy.data.objects:
        if obj.animation_data and "Q3ANIM" in obj.animation_data.nla_tracks:
            return obj
    return None