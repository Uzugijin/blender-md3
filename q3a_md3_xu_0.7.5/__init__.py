bl_info = {
    "name": "Q3A MD3 Export Utility",
    "author": "Vitaly Verhovodov, Aleksander Marhall, Uzugijin",
    "version": (0, 7, 5),
    "blender": (4, 00, 0),
    "category": "Import-Export",
    "location": "Nonlinear Animation > Side panel (N) > Q3A MD3 XU",
    "description": (
        "Export addon focusing on playermodels for Quake 3 Arena"
    ),
    "doc_url": "https://github.com/Uzugijin/blender-md3",
}

import bpy
import struct
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper
from .assembly_map import *
from .composition_functions import *

class Q3AnimationConfigProperties(bpy.types.PropertyGroup):
    selected_object: bpy.props.PointerProperty(name="Target object to import actions to", type=bpy.types.Object, description="Recommended for single skeleton, otherwise leave blank to generate a dummy")
    fixedtorso: bpy.props.BoolProperty(name="Fixed Torso", default=False, description="Don't rotate torso pitch when looking up or down")
    fixedlegs: bpy.props.BoolProperty(name="Fixed Legs", default=False, description="Don't rotate legs (always align with torso)")
    mark_frames: bpy.props.BoolProperty(name="Mark Actions", default=False, description="Mark the first frame of every strip in the NLA track")
    anim_cfg_enabled: bpy.props.BoolProperty(name="Animation Config", default=True, description="Generate animation.cfg on export")
    skin_enabled: bpy.props.BoolProperty(name="Skin Config", default=True, description="Generate .skin file templates on export")
    scale_multiplier: bpy.props.IntProperty(name="Model Scale", default=10, description="Scale up model by a multiplier")
    timeline_method: bpy.props.EnumProperty(
        items=[
            ("nla", "NLA strips", "Process NLA strips for frame packing and frame information"),
            ("markers", "Markers", "Process the range between markers for frame packing and frame information"),
            ("simple", "Timeline", "Process the timeline range for frame packing.")
        ],
        name="Sequence",
        default="nla",
    )
    sex_defined: bpy.props.EnumProperty(
        items=[
            ("sex n", "Neutral", ""),
            ("sex m", "Male", ""),
            ("sex f", "Female", ""),
        ],
        name="Sex",
        default="sex n",
    )
    footsteps_defined: bpy.props.EnumProperty(
        items=[
            ("footsteps normal", "Normal", ""),
            ("footsteps boot", "Boots", ""),
            ("footsteps flesh", "Flesh", ""),
            ("footsteps mech", "Mech", ""),
            ("footsteps energy", "Energy", ""),
        ],
        name="Footsteps",
        default="footsteps normal",
    )
    modeltype: bpy.props.EnumProperty(
        items=[
            ("assembly", "Separate Groups", "Processes objects and frames separately based on group composition. Makes multiple MD3 files. Supports skin and precise animation config file generation."),
            ("animated", "Linearly Animated", "Exports objects with linear processing of timeline as a single MD3 file, supports skin (requires groups) and animation config file generation."),
            ("static", "Snapshot", "Exports the current frame as a single MD3 file.")
        ],
        name="Mode",
        default="assembly",
    )
    gen_bbox: bpy.props.BoolProperty(name="Bbox", default=True, description="Generate BBox")
    gen_actions: bpy.props.BoolProperty(name="Actions", default=True, description="Generate Actions")
    gen_tag: bpy.props.BoolProperty(name="Tag", default=True, description="Generate Tag")


class Q3AnimationConfigPanel(bpy.types.Panel):
    bl_label = "Q3A MD3 Export Utility"
    bl_idname = "VIEW3D_PT_q3_animation_config"
    bl_space_type = 'NLA_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Q3A MD3 XU'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        q3_props = scene.q3_animation_config
        version_str = "{}.{}.{}".format(bl_info["version"][0], bl_info["version"][1], bl_info["version"][2])

        row = layout.row()
        row.label(text="Version "+version_str)
        row = layout.row()
        row.prop(q3_props, "scale_multiplier", text="Model Scale Multiplier")
        row = layout.row()
        row.prop(q3_props, "modeltype")

        if not q3_props.modeltype == "static":
            row = layout.row()
            row.prop(q3_props, "timeline_method")
            if q3_props.timeline_method == "nla":
                row = layout.row()
                row.prop(q3_props, "selected_object", text="Target")
                row = layout.row()
                row.prop(q3_props, "mark_frames", text="Mark First Frame of Strips", toggle=False)
                row = layout.row()
                row.operator("q3.import_actions", text="(Re)Build NLA")

        row = layout.row()
        box = layout.box()
        row = box.row()
        row.label(text="Animation.cfg:")
        if q3_props.modeltype == "static" or q3_props.timeline_method == "simple":
            row.label(text="-")
        else:
            row.prop(q3_props, "anim_cfg_enabled", text="Generate", toggle=False)

            if q3_props.anim_cfg_enabled:
                row = box.row()
                row.prop(q3_props, "sex_defined")
                row = box.row()
                row.prop(q3_props, "footsteps_defined")

                row = box.row()
                row.prop(q3_props, "fixedtorso", text="Fixed Torso", toggle=False)
                row.prop(q3_props, "fixedlegs", text="Fixed Legs", toggle=False)

        box = layout.box()
        row = box.row()
        row.label(text="Skin Template:")
        if not q3_props.modeltype == "static":
            row.prop(q3_props, "skin_enabled", text="Generate", toggle=False)
        else:
            row.label(text="-")

        row = layout.row()
        row.operator("export_scene.md3", text="Export", icon="EXPORT")
        row = layout.row()
        row = layout.row()
        row = layout.row()
        row.operator("q3.open_cheatsheet", text="Open Cheatsheet")

        box = layout.box()
        box.operator("q3.generate_template", text="Generate Template")
        row = box.row()
        row.prop(q3_props, "gen_bbox", text="Bbox", toggle=False)
        row.prop(q3_props, "gen_actions", text="Actions", toggle=False)
        row.prop(q3_props, "gen_tag", text="Tag", toggle=False)


def generate_group_skin(group_data):
    """Generate skin file content for a specific group"""
    print(f"DEBUG Group: {[obj.name for obj in group_data['collected_objects']]}")
    
    skin_lines = []
    added_objects = set()
    
    # Add tags and meshes, avoiding duplicates
    for obj in group_data['collected_objects']:
        if obj.name in added_objects:
            continue
            
        added_objects.add(obj.name)
        
        if obj.type == 'MESH':
            if obj.data.materials:
                material_name = obj.data.materials[0].name
                skin_lines.append(f"{obj.name}, {material_name}")
            else:
                skin_lines.append(f"{obj.name},")
        else:  # It's a tag
            skin_lines.append(f"{obj.name},")

    tags = [line for line in skin_lines if line.startswith('tag_')]
    meshes = [line for line in skin_lines if not line.startswith('tag_')]
    
    return "\n".join(tags + meshes)

def save_animation_config(context):
    scene = context.scene
    q3_props = scene.q3_animation_config
    
    def parse_action_name(actual_name):
        """Parse flags from the actual strip/marker name using dot notation"""
        fps = scene.render.fps
        looping_frames = 0
        is_dead = False
        
        # Remove numeric prefixes like 00., 01. etc.
        clean_name = actual_name
        if '.' in actual_name:
            # Split by dots and remove the first part if it's numeric
            parts = actual_name.split('.')
            if parts[0].isdigit():
                clean_name = '.'.join(parts[1:])
        
        # Check for flags in the name using dot notation
        name_parts = clean_name.lower().split('.')
        if 'loop' in name_parts:
            looping_frames = -1  # Will be replaced with actual frame count
        if 'dead' in name_parts:
            is_dead = True
            
        # Reconstruct the clean name without flags
        clean_parts = [part for part in name_parts if part not in ['loop', 'dead']]
        clean_name = '.'.join(clean_parts)
            
        return clean_name, fps, looping_frames, is_dead

    # Open a file to write the output
    output = ""
    output += "// animation config file generated by q3a-md3-xu blender3d extension\n\n"
    output += f"{q3_props.sex_defined}\n"
    output += f"{q3_props.footsteps_defined}\n"
    if q3_props.fixedtorso:
        output += "fixedtorso\n"
    if q3_props.fixedlegs:
        output += "fixedlegs\n"
    output += "\n// first frame, num frames, looping frames, frames per second\n\n"
    output += "\n// ff -- nf --- lf --- fps\n\n"

    # Get available ranges based on timeline method
    available_ranges = {}
    
    if q3_props.timeline_method == "markers":
        # Create a mapping of marker index to frame range
        scene = bpy.context.scene
        markers = sorted(scene.timeline_markers, key=lambda m: m.frame)
        
        # Process all markers, including the last one
        for i in range(len(markers)):
            current_marker = markers[i]
            start_frame = int(current_marker.frame)
            
            # Determine end frame
            if i < len(markers) - 1:
                # Range goes to next marker - 1
                next_marker = markers[i + 1]
                end_frame = int(next_marker.frame) - 1
            else:
                # Last marker goes to end of scene
                end_frame = scene.frame_end
            
            num_frames = end_frame - start_frame + 1
            
            # Use marker INDEX to determine which action it represents
            action_num = i
            
            # Store the range for this action number
            available_ranges[action_num] = (start_frame, num_frames, end_frame, current_marker.name)
    
    else:  # NLA strips method
        # Get all strips and map by their order
        strips = get_q3anim_object().animation_data.nla_tracks["Q3ANIM"].strips
        for i, strip in enumerate(strips):
            start_frame = int(strip.frame_start)
            end_frame = int(strip.frame_end)
            num_frames = end_frame - start_frame + 1
            
            # Use strip INDEX to determine which action it represents
            action_num = i
            
            # Store the range for this action number
            available_ranges[action_num] = (start_frame, num_frames, end_frame, strip.name)

    # Process actions until we run out of available ranges
    for action_data in ACTIONS:
        action_num = action_data[0]
        
        # Stop processing if we've run out of available ranges
        if action_num not in available_ranges:
            break
        
        # Get the range data
        start_frame, num_frames, end_frame, actual_name = available_ranges[action_num]
        frames = list(range(start_frame, end_frame + 1))
        
        # Parse action properties from actual name
        name, fps, looping_frames, is_dead = parse_action_name(actual_name)
        
        # Set looping frames to match num_frames if it's a loop action
        if looping_frames == -1:
            looping_frames = num_frames

        # Write the main animation line
        output += f"{start_frame}\t{num_frames}\t{looping_frames}\t{fps}\t\t// {name}\n"

        # Add dead frame if this is a death animation
        if is_dead:
            dead_name = name + " (dead)"
            output += f"{end_frame}\t1\t0\t{fps}\t\t// {dead_name}\n"

    return output

class Q3OpenCheatsheetOperator(bpy.types.Operator):
    bl_idname = "q3.open_cheatsheet"
    bl_label = "Open Cheatsheet"
    bl_description = "https://icculus.org/gtkradiant/documentation/Model_Manual/model_manual.htm"

    def execute(self, context):
        bpy.ops.wm.url_open(url="https://icculus.org/gtkradiant/documentation/Model_Manual/model_manual.htm")
        return {'FINISHED'}

class Q3GenerateTemplate(bpy.types.Operator):
    bl_idname = "q3.generate_template"
    bl_label = "Generate Template"
    bl_description = "Generates action names, bounding boxes and tags"

    def execute(self, context):
        scene = context.scene
        q3_props = scene.q3_animation_config
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            self.report({'ERROR'}, "Not in Object Mode!")
            return {'CANCELLED'}
        
        jj2 = 0

        if q3_props.gen_bbox:
            jj2 = 1
                # Create the two bounding boxes (only if they don't exist)
            if "Player_Bounds" not in bpy.data.objects:
                self.create_bounding_box("Player_Bounds", (3, 3, 6), (0, 0, 0.5986))
            else:
                print("Player_Bounds already exists, skipping...")
                
            if "Max_Bounds" not in bpy.data.objects:
                self.create_bounding_box("Max_Bounds", (102.39, 102.39, 102.39), (0, 0, 0))
            else:
                print("Max_Bounds already exists, skipping...")

            if "Front_Direction" not in bpy.data.objects:
                # Create empty arrow
                self.create_empty_front("Front_Direction", (1.50109, 0, -2.39969))
            else:
                print("Front_Direction already exists, skipping...")
        
        # Generate actions from assembly map (only if they don't exist)
        if q3_props.gen_actions:
            jj2 = 1
            self.generate_actions()
        
        if q3_props.gen_tag:
            jj2 = 1
        # Create tag mesh (always create, allow multiple tags)
            self.create_tag_mesh("template", (0, 0, 4.2))  # Place above player bounds

        if jj2 == 0:
            self.report({'INFO'}, "Spaz ate the dopefish.")

        return {'FINISHED'}

    def create_bounding_box(self, name, dimensions, location):
        """Create a wireframe bounding box that's unselectable"""
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        box = bpy.context.active_object
        box.name = name
        box.dimensions = dimensions
        box.display_type = 'BOUNDS'
        box.hide_select = True

    def create_empty_front(self, name, location):
        """Create an empty arrow for front direction"""
        bpy.ops.object.empty_add(type='SINGLE_ARROW', radius=1, align='WORLD', location=location, scale=(1, 1, 1))
        
        arrow = bpy.context.active_object
        arrow.name = name
        arrow.hide_select = True
        arrow.empty_display_size = 2
        
        # Rotate 90 degrees on Y axis
        arrow.rotation_euler = (0, 1.5708, 0)  # 90 degrees in radians

    def generate_actions(self):
        """Generate action datablocks from the ACTIONS list in assembly_map"""
        existing_action_names_lower = {action.name.lower() for action in bpy.data.actions}

        for action_data in ACTIONS:
            action_num = action_data[0]
            action_name = action_data[1]
            
            # Create the formatted action name with dots
            if len(action_data) > 2:
                special_flag = action_data[2]
                if special_flag == 1:  # die
                    formatted_name = f"{action_num:02d}.{action_name}.dead"
                elif special_flag == 8:  # loop
                    formatted_name = f"{action_num:02d}.{action_name}.loop"
                else:
                    formatted_name = f"{action_num:02d}.{action_name}"
            else:
                formatted_name = f"{action_num:02d}.{action_name}"
            
            # Check if action already exists
            if formatted_name.lower() not in existing_action_names_lower:
                # Use the formatted action name including dots
                action = bpy.data.actions.new(name=formatted_name)
                action.use_fake_user = True  # Prevent deletion
                print(f"Created action: {formatted_name}")
            else:
                print(f"Action '{formatted_name}' already exists, skipping...")

    def create_tag_mesh(self, name, location):
        """Create a tag mesh with the specified vertex positions"""
        # Create mesh and object
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        
        # Link object to scene
        bpy.context.collection.objects.link(obj)
        
        # Create vertices
        vertices = [
            (0, 0, 0),           # Origin
            (0, -0.491417, 0),   # X axis (left)
            (0.981796, 0, 0)     # Y axis (forward)
        ]
        
        # Create face (triangle)
        faces = [(0, 1, 2)]
        
        # Build mesh
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        
        # Set location (above player bounds)
        obj.location = location
        
        # Make it a proper tag by naming it with tag_ prefix
        obj.name = f"tag_{name}"
        obj.show_name = True

        return obj
    
class Q3ImportActionsOperator(bpy.types.Operator):
    bl_idname = "q3.import_actions"
    bl_label = "Import Actions"
    bl_description = "Compile Actions to NLA for export and animation sequence read. Action format: [num]NAME[loop][die]"

    def execute(self, context):
        scene = context.scene
        q3_props = scene.q3_animation_config
        selected_objects = bpy.context.selected_objects
        check = bpy.data.objects.get("NLA-Compiler")
        
        # Offset variables
        STRIP_OFFSET = 0    # Offset for all strips
        MARKER_OFFSET = 0    # Offset for markers relative to strip start (except first strip)
        if q3_props.modeltype == "assembly":
            STRIP_GAP = 1        # Gap between strips
        else:
            STRIP_GAP = 0

        ### Make list from all actions in order with numeric prefixes like: 0_BOTH_DEATH1, 1_BOTH_DEATH2, etc
        all_actions = []
        print("All Actions:")

        for action in bpy.data.actions:
            # Check for dot notation (00.name, 01.name, etc.)
            if '.' in action.name:
                prefix = action.name.split(".")[0]
                if prefix.isdigit():
                    all_actions.append(action.name)
        all_actions.sort(key=lambda x: int(x.split(".")[0]))

        if q3_props.selected_object is check:
            q3_props.selected_object = None
        obj = q3_props.selected_object

        for obj2 in bpy.data.objects:
            if obj2.animation_data is not None:
                for track in obj2.animation_data.nla_tracks:
                    if track.name == "Q3ANIM":
                        obj2.animation_data.nla_tracks.remove(track)

            # Check if a cube object already exists
        frame_buddy_name = "NLA-Compiler"

            # Delete the existing cube object and its associated data
        for obj2 in bpy.data.objects:
            if frame_buddy_name in obj2.name:
                bpy.data.objects.remove(obj2)

            # Delete actions
        for action in bpy.data.actions:
            if frame_buddy_name in action.name:
                bpy.data.actions.remove(action)

        if obj is None:
            active_object_at_the_time = bpy.context.active_object
            if bpy.context.object is not None:
                if bpy.context.object.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
            cube = bpy.context.active_object
            cube.name = frame_buddy_name
            cube.animation_data_create()
            obj = cube
            if active_object_at_the_time is not None:
                bpy.context.view_layer.objects.active = bpy.data.objects[active_object_at_the_time.name]

        track = obj.animation_data.nla_tracks.new(prev=None)
        track.name = "Q3ANIM"
        frame_offset = STRIP_OFFSET  # Use strip offset

        for action_name in all_actions:
            action = bpy.data.actions.get(action_name)
            if action:
                strip = track.strips.new(action_name, int(frame_offset), action)
                strip.name = action_name
                strip.action = action
                if q3_props.modeltype == "assembly":
                # Check if action has only 1 keyframe (start and end are the same or very close)
                    if action.frame_range[1] - action.frame_range[0] < 1.0:
                        # Single keyframe action - make it very short
                        strip.frame_end_ui = strip.frame_start + 0.1  # 0.1 frames duration
                
                frame_offset += strip.frame_end - strip.frame_start
                frame_offset += STRIP_GAP  # Add gap after each strip
        
        # Set scene end frame without additional offset (subtract the last gap since it's after the last strip)
        bpy.context.scene.frame_end = int(frame_offset) - STRIP_GAP
     
        if q3_props.mark_frames:
            # Clear ALL existing markers
            markers = context.scene.timeline_markers
            markers.clear()
            
            # Create timeline markers for each strip with special marker logic
            for i, strip in enumerate(track.strips):
                if i == 0:  # First strip - no offset
                    marker_frame = int(strip.frame_start)
                else:  # All other strips - apply marker offset
                    marker_frame = int(strip.frame_start) + MARKER_OFFSET
                marker = markers.new(name=strip.name, frame=marker_frame)
            
            # Deselect all markers after creation
            for marker in markers:
                marker.select = False
        else:
            # If mark_frames is false, remove all markers
            markers = context.scene.timeline_markers
            markers.clear()

        if bpy.context.object is not None:
            if bpy.context.object.mode == 'OBJECT':
                bpy.ops.object.select_all(action='DESELECT')
        for obj in selected_objects:
            if obj is not check:
                obj.select_set(True)
        
        return {'FINISHED'}
    
def has_animation_strips(context):
    """Check if there are any Q3ANIM animation strips OR markers in the scene"""
    scene = context.scene
    q3_props = scene.q3_animation_config
        
    if q3_props.timeline_method == "markers":
        # Check if there are any timeline markers
        return len(scene.timeline_markers) > 0
    else:
        # Check if there are Q3ANIM strips
        q3anim_obj = get_q3anim_object()
        if not q3anim_obj:
            return False    
        q3anim_track = q3anim_obj.animation_data.nla_tracks.get("Q3ANIM")
        if not q3anim_track:
            return False    
        return len(q3anim_track.strips) > 0

class ExportMD3(bpy.types.Operator, ExportHelper):
    '''Export a Quake 3 Model MD3 file'''
    bl_idname = "export_scene.md3"
    bl_label = 'Export MD3'
    filename_ext = ".md3"
    filter_glob = StringProperty(default="*.md3;*.cfg", options={'HIDDEN'})

    def invoke(self, context, event):
        self.filename_ext = ".md3"
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        error_counter = 0
        props = bpy.context.scene.q3_animation_config      
        try:
            from .export_md3 import MD3Exporter          

            if bpy.context.view_layer.objects.active is not None:
                bpy.ops.object.mode_set(mode='OBJECT')
            
            filepath = self.properties.filepath
            
            if not bpy.context.selected_objects:
                bpy.ops.object.select_all(action='SELECT')
                self.report({'WARNING'}, "Assuming all objects")

            # Detect groups
            all_objects = bpy.context.selected_objects
            all_groups = collect_assembly_groups(all_objects)
            character_groups = get_character_groups(all_groups)
            
            if character_groups and props.modeltype == "assembly":
                # Export each group separately
                base_path = filepath.replace('.md3', '')
                for group_name, group_data in character_groups.items():
                    group_filepath = f"{base_path}_{group_name}.md3"
                    MD3Exporter(context, group_data)(group_filepath)
            else:                
                # Single file export (old behavior)
                MD3Exporter(context, group_data=None)(filepath)  # group_data=None

            if props.modeltype == "static" or props.timeline_method == "simple":
                pass
            else:
            # Animation CFG: Only create if there are animation strips
                if props.anim_cfg_enabled and has_animation_strips(context):
                    animation_cfg_path = filepath.replace('.md3', '_animation.cfg')
                    with open(animation_cfg_path, 'w') as f:
                        f.write(save_animation_config(context))
                else:
                    error_counter += 1

        # Skin files: Only create if in assembly mode AND there are groups
            if props.modeltype == "static":
                pass
            else:
                if (props.skin_enabled and props.modeltype == "animated") or (props.modeltype == "assembly" and character_groups):
                    # Export skin files for each character group
                    for group_name, group_data in character_groups.items():
                        skin_text = generate_group_skin(group_data)
                        if skin_text:  # Only write if there's content
                            skin_path = filepath.replace('.md3', f'_{group_name}_default.skin')
                            with open(skin_path, 'w') as f:
                                f.write(skin_text)
                else:
                    error_counter += 2

            if error_counter == 0:
                self.report({'INFO'}, "Export complete!")
            elif error_counter == 1:
                self.report({'WARNING'}, "Export complete but anim.cfg file failed! No strips on NLA!")
            elif error_counter == 2:
                self.report({'WARNING'}, "Export complete but skin file failed! No groups found!")
            else:
                self.report({'WARNING'}, "Export complete but anim.cfg and skin files failed! No groups and strips on NLA!")
            print(error_counter)
            return {'FINISHED'}
        except struct.error:
            self.report({'ERROR'}, "Mesh does not fit within the MD3 model space. Vertex axies locations must be below 512 blender units.")
        except ValueError as e:
            self.report({'ERROR'}, str(e))
        return {'CANCELLED'}

def menu_func_export(self, context):
    self.layout.operator(ExportMD3.bl_idname, text="Quake 3 Model (.md3)")

classes = (
    ExportMD3,
    Q3AnimationConfigProperties,
    Q3AnimationConfigPanel,
    Q3OpenCheatsheetOperator,
    Q3ImportActionsOperator,
    Q3GenerateTemplate
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.Scene.q3_animation_config = bpy.props.PointerProperty(type=Q3AnimationConfigProperties)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    del bpy.types.Scene.q3_animation_config

if __name__ == "__main__":
    register()
