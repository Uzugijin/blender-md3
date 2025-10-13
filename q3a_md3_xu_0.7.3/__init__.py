bl_info = {
    "name": "Q3A MD3 Export Utility",
    "author": "Vitaly Verhovodov, Aleksander Marhall, Uzugijin",
    "version": (0, 7, 3),
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
import re
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper
from .assembly_map import *

class Q3AnimationConfigProperties(bpy.types.PropertyGroup):
    selected_object: bpy.props.PointerProperty(name="Target object to import actions to", type=bpy.types.Object, description="Recommended for single skeleton, otherwise leave blank to generate a dummy")
    fixedtorso: bpy.props.BoolProperty(name="Fixed Torso", default=False, description="Don't rotate torso pitch when looking up or down")
    fixedlegs: bpy.props.BoolProperty(name="Fixed Legs", default=False, description="Don't rotate legs (always align with torso)")
    mark_frames: bpy.props.BoolProperty(name="Mark Actions", default=False, description="Mark the first frame of every strip in the NLA track")
    anim_cfg_enabled: bpy.props.BoolProperty(name="Animation Config", default=True, description="Generate animation.cfg on export")
    skin_enabled: bpy.props.BoolProperty(name="Skin Config", default=True, description="Generate .skin file templates on export")
    scale_multiplier: bpy.props.IntProperty(name="Model Scale", default=10, description="Scale up model by a multiplier")
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
            ("assembly", "Composite", "Exports multiple MD3 files based on group composition. Supports skin and animation config file generation."),
            ("animated", "Single Animated", "Exports selection with animation as a single MD3 file, supports skin (requires groups) and animation config file generation."),
            ("static", "Snapshot", "Exports the current frame as a single MD3 file.")
        ],
        name="Type",
        default="assembly",
    )

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
        row.prop(q3_props, "modeltype")
        row = layout.row()
        row.prop(q3_props, "scale_multiplier", text="Scale")
        if not q3_props.modeltype == "static":
            row = layout.row()
            row.prop(q3_props, "selected_object", text="Target")
            row = layout.row()
            row.prop(q3_props, "mark_frames", text="Mark First Frame of Strips", toggle=False)
            row = layout.row()
            row.prop(q3_props, "offset_cgf_by_1", text="Offset Sequence by 1", toggle=False)
            row = layout.row()

            row = layout.row()
            row.operator("q3.import_actions", text="(Re)Build NLA")

        row = layout.row()
        box = layout.box()
        row = box.row()
        row.label(text="Animation.cfg:")
        if not q3_props.modeltype == "static":
            row.prop(q3_props, "anim_cfg_enabled", text="Generate", toggle=False)

            if q3_props.anim_cfg_enabled:
                row = box.row()
                row.prop(q3_props, "sex_defined")
                row = box.row()
                row.prop(q3_props, "footsteps_defined")

                row = box.row()
                row.prop(q3_props, "fixedtorso", text="Fixed Torso", toggle=False)
                row.prop(q3_props, "fixedlegs", text="Fixed Legs", toggle=False)
        else:
            row.label(text="-")

        box = layout.box()
        row = box.row()
        row.label(text="Skin Template:")
        if not q3_props.modeltype == "static":
            row.prop(q3_props, "skin_enabled", text="Generate", toggle=False)
        else:
            row.label(text="-")

        row = layout.row()
        row.operator("export_scene.md3", text="Export")
        row = layout.row()
        row = layout.row()
        row.operator("q3.open_cheatsheet", text="Open Cheatsheet")
        row = layout.row()
        row.operator("q3.generate_template", text="Generate Template")

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
    restore = q3_props.selected_object
    obj = q3_props.selected_object
    if obj is None:
        obj = bpy.data.objects.get("NLA-Compiler")
        if obj is not None:
            q3_props.selected_object = obj
        else:
            print({'ERROR'}, "Please select an armature or create an object named 'NLA-Compiler'!")
            return None

    def parse_action_name(action_name, psuedo_name):
        parts = action_name.split('.')
        name = parts[0]
        fps = bpy.context.scene.render.fps
        looping_frames = 0
        is_dead = False

        if 'loop' in name.lower():
            looping_frames = num_frames  # Placeholder to indicate looping frames should match num_frames

        if 'die' in name.lower():
            is_dead = True

        for part in parts[1:]:
            if part.isdigit():
                fps = int(part)
        name = psuedo_name
        return name, fps, looping_frames, is_dead

    def rename_to_dead(name):
        parts = name.split('_')
        if len(parts) > 1:
            base = parts[0]
            number = ''.join(filter(str.isdigit, parts[1]))
            return f"{base}_DEAD{number}"
        return name

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

    # Iterate through all NLA tracks
    objects = [q3_props.selected_object] if q3_props.selected_object else bpy.data.objects
    for obj in objects:
        if obj and obj.animation_data and obj.animation_data.nla_tracks:
            for track in obj.animation_data.nla_tracks:
                for strip in track.strips:
                    original_action_name = strip.action.name
                    start_frame = int(strip.frame_start)
                    end_frame = int(strip.frame_end) - 1
                    
                    # Ensure we don't go below start frame
                    if end_frame < start_frame:
                        end_frame = start_frame

                    num_frames = end_frame - start_frame
                    if num_frames == 0:
                        num_frames = 1
                    else:
                        num_frames += 1

                    name, fps, looping_frames, is_dead = parse_action_name(original_action_name, strip.name)
                    if looping_frames == -1:
                        looping_frames = num_frames

                        # Write the formatted output to the file
                    output += f"{start_frame}\t{num_frames}\t{looping_frames}\t{fps}\t\t// {name}\n"

                    if is_dead:
                        dead_name = rename_to_dead(name)
                        output += f"{end_frame - 0}\t1\t0\t{fps}\t\t// {dead_name}\n"
    q3_props.selected_object = restore
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
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            self.report({'ERROR'}, "Not in Object Mode!")
            return {'CANCELLED'}
        
            # Create the two bounding boxes (only if they don't exist)
        if "Player_Bounds" not in bpy.data.objects:
            self.create_bounding_box("Player_Bounds", (3, 3, 6), (0, 0, 0.5986))
        else:
            print("Player_Bounds already exists, skipping...")
            
        if "Max_Bounds" not in bpy.data.objects:
            self.create_bounding_box("Max_Bounds", (102.39, 102.39, 102.39), (0, 0, 0))
        else:
            print("Max_Bounds already exists, skipping...")
        
        # Generate actions from assembly map (only if they don't exist)
        self.generate_actions()
        
        # Create tag mesh (always create, allow multiple tags)
        self.create_tag_mesh("template", (0, 0, 4.2))  # Place above player bounds

        if "Front_Direction" not in bpy.data.objects:
                # Create empty arrow
            self.create_empty_front("Front_Direction", (1.50109, 0, -2.39969))
        else:
            print("Front_Direction already exists, skipping...")

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
        from .assembly_map import ACTIONS

        existing_action_names_lower = {action.name.lower() for action in bpy.data.actions}

        for action_name in ACTIONS:
            # Check if action already exists
            if action_name.lower() not in existing_action_names_lower:
                # Use the action name exactly as-is including brackets
                action = bpy.data.actions.new(name=action_name)
                action.use_fake_user = True  # Prevent deletion
                print(f"Created action: {action_name}")
            else:
                print(f"Action '{action_name}' already exists, skipping...")

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

        ### Make list from all actions in order with numeric prefixes like: 0_BOTH_DEATH1, 1_BOTH_DEATH2, etc
        all_actions = []
        print("All Actions:")
        
        for action in bpy.data.actions:
            if '[' in action.name and ']' in action.name:
                prefix = action.name.split("[")[1].split("]")[0]
                if prefix.isdigit():
                    all_actions.append(action.name)
        all_actions.sort(key=lambda x: int(x.split("[")[1].split("]")[0]))
        print(all_actions)
        all_actions_without_brackets = [re.sub(r'\[.*?\]', '', action) for action in all_actions]

        print("All Actions without prefix:")
        print(all_actions_without_brackets)
        ###

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
        frame_offset = 0

        for action_name in all_actions:
            action = bpy.data.actions.get(action_name)
            if action:
                action_name_without_brackets = re.sub(r'\[.*?\]', '', action_name)
                strip = track.strips.new(action_name, int(frame_offset), action)
                strip.name = action_name_without_brackets
                strip.action = action
                frame_offset += strip.frame_end - strip.frame_start
        bpy.context.scene.frame_end = int(frame_offset)
     
        if q3_props.mark_frames:

                    bpy.ops.object.empty_add(type='ARROWS', location=(0, 0, 0))
                    cube = bpy.context.active_object
                    cube.name = frame_buddy_name + " Marker"
                    cube.animation_data_create()
                    # Create an action for the cube
                    cube_action = bpy.data.actions.new(frame_buddy_name + " Marked Frames")
                    # Initialize variables
                    y_offset = 14
                    z_offset = 35
                    y_direction = 1
                    z_direction = 1

                    cube.animation_data_create()
                    cube.animation_data.action = cube_action

                    # Iterate over the NLA strips
                    current_frame = bpy.context.scene.frame_current
                    for strip in track.strips:
                        # Calculate the new Y and Z positions
                        new_y = y_offset * y_direction
                        new_z = z_offset * z_direction

                        # Set the current frame to the strip's start frame
                        bpy.context.scene.frame_set(int(strip.frame_start)+1)

                        # Insert a keyframe for the cube's position
                        cube.location = (0, new_y, new_z)
                        #bpy.ops.anim.keyframe_insert(type='Location')
                        cube.keyframe_insert(data_path="location")

                        # Update the Y and Z directions for the next strip
                        y_direction *= -1
                        z_direction *= -1
                        if z_direction == -1:
                            z_offset = 23
                        else:
                            z_offset = 35

                    bpy.context.scene.frame_set(current_frame)

                    fcurve_x = cube.animation_data.action.fcurves.find('location', index=0)
                    fcurve_y = cube.animation_data.action.fcurves.find('location', index=1)
                    fcurve_z = cube.animation_data.action.fcurves.find('location', index=2)

                    for kp in fcurve_x.keyframe_points:
                        kp.interpolation = 'CONSTANT'
                    for kp in fcurve_y.keyframe_points:
                        kp.interpolation = 'CONSTANT'
                    for kp in fcurve_z.keyframe_points:
                        kp.interpolation = 'CONSTANT'

        if bpy.context.object is not None:
            if bpy.context.object.mode == 'OBJECT':
                bpy.ops.object.select_all(action='DESELECT')
        for obj in selected_objects:
            if obj is not check:
                obj.select_set(True)
        
        return {'FINISHED'}

def has_animation_strips(context):
    """Check if there are any Q3ANIM animation strips in the scene"""
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

            # Animation CFG: Only create if there are animation strips
            if props.anim_cfg_enabled and not props.modeltype == "static" and has_animation_strips(context):
                animation_cfg_path = filepath.replace('.md3', '_animation.cfg')
                with open(animation_cfg_path, 'w') as f:
                    f.write(save_animation_config(context))
            else:
                error_counter += 1
            
            # Skin files: Only create if in assembly mode AND there are groups
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
