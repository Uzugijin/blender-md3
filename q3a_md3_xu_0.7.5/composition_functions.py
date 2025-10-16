import bpy
from .assembly_map import *

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

def get_group_frame_range(scene, group_data, modeltype, timeline_method):
    """Get the appropriate frame range for export (group-aware or single-file)"""
    if group_data and group_data.get('action_strips'):
        if timeline_method == "nla":
        # Group export with specific strips
            return get_frames_from_strips(group_data['action_strips'])
        else:
            return get_frames_from_markers(group_data['action_strips'])
    elif modeltype == "static":
        # Static model - just frame 0
        return [0]
    else:
        # Original animated export - full range
        return list(range(scene.frame_start, scene.frame_end + 1))

def get_q3anim_object():
    """Find the object with Q3ANIM track"""
    for obj in bpy.data.objects:
        if obj.animation_data and "Q3ANIM" in obj.animation_data.nla_tracks:
            return obj
    return None

def get_frames_from_strips(strip_indices):
    """Get frame ranges from strips and provide animation info lookup"""
    q3anim_obj = get_q3anim_object()
    if not q3anim_obj:
        return [0], lambda i: ("Unknown", 0)
    
    q3anim_track = q3anim_obj.animation_data.nla_tracks["Q3ANIM"]
    all_strips = list(q3anim_track.strips)
    
    all_frames = set()
    strip_ranges = []  # Store (strip, start_frame, end_frame) for lookup
    
    for strip_idx in strip_indices:
        if strip_idx < len(all_strips):
            strip = all_strips[strip_idx]
            start_frame = max(0, int(strip.frame_start) + 0)
            end_frame = int(strip.frame_end)
            
            # Add frames to set
            for frame in range(start_frame, end_frame + 1):
                all_frames.add(frame)
            
            # Store strip range for lookup
            strip_ranges.append((strip, start_frame, end_frame))
    
    # Create lookup function
    def get_animation_info(i):
        for strip, start, end in strip_ranges:
            if start <= i <= end:
                local_frame = i - start
                return strip.name, int(local_frame)
        return "Unknown", 0
    
    return sorted(list(all_frames)), get_animation_info

def get_frames_from_markers(marker_indices):
    """Get frame ranges from markers and provide animation info lookup"""
    scene = bpy.context.scene
    markers = scene.timeline_markers
    
    if not markers:
        return [0], lambda i: ("Unknown", 0)
    
    sorted_markers = sorted(markers, key=lambda m: m.frame)
    
    if marker_indices is None:
        marker_indices = list(range(len(sorted_markers)))
    
    all_frames = set()
    marker_ranges = []  # Store (marker, start_frame, end_frame) for lookup
    
    # Create ranges between specified marker indices
    for i in range(len(marker_indices) - 1):
        current_idx = marker_indices[i]
        next_idx = marker_indices[i + 1]
        
        if current_idx < len(sorted_markers) and next_idx < len(sorted_markers):
            current_marker = sorted_markers[current_idx]
            next_marker = sorted_markers[next_idx]
            
            start_frame = int(current_marker.frame)
            end_frame = int(next_marker.frame) - 1
            
            # Add frames to set
            for frame in range(start_frame, end_frame + 1):
                all_frames.add(frame)
            
            # Store marker range for lookup
            marker_ranges.append((current_marker, start_frame, end_frame))
    
    # Handle last marker range
    if marker_indices and marker_indices[-1] < len(sorted_markers):
        last_marker = sorted_markers[marker_indices[-1]]
        start_frame = int(last_marker.frame)
        end_frame = scene.frame_end
        
        for frame in range(start_frame, end_frame + 1):
            all_frames.add(frame)
        
        marker_ranges.append((last_marker, start_frame, end_frame))
    
    # Create lookup function
    def get_animation_info(i):
        for marker, start, end in marker_ranges:
            if start <= i <= end:
                local_frame = i - start
                return marker.name, int(local_frame)
        return "Unknown", 0
    
    return sorted(list(all_frames)), get_animation_info