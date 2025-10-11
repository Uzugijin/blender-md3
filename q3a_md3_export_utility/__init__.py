bl_info = {
    "name": "Q3A MD3 Export Utility",
    "author": "Vitaly Verhovodov, Aleksander Marhall, Uzugijin",
    "version": (0, 6, 0),
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

class Q3AnimationConfigProperties(bpy.types.PropertyGroup):
    selected_object: bpy.props.PointerProperty(name="Target object to import actions to", type=bpy.types.Object, description="Recommended for single skeleton, otherwise leave blank to generate a dummy")
    fixedtorso: bpy.props.BoolProperty(name="Fixed Torso", default=False, description="Don't rotate torso pitch when looking up or down")
    fixedlegs: bpy.props.BoolProperty(name="Fixed Legs", default=False, description="Don't rotate legs (always align with torso)")
    mark_frames: bpy.props.BoolProperty(name="Mark Actions", default=False, description="Mark the first frame of every strip in the NLA track")
    offset_cgf_by_1: bpy.props.BoolProperty(name="Offset By 1", default=True, description="Offsets animation sequence forward by 1 frame for marker and animation.cfg (Recommended)")
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
            ("animated", "Animated", ""),
            ("static", "Static", ""),
        ],
        name="Type",
        default="animated",
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
        row.operator("q3.open_cheatsheet", text="Open Cheatsheet")

def save_skin_file(context):

    objects = bpy.context.selected_objects

    head_text = "tag_head,\n"
    if "tag_flag" in objects:
        upper_text = "tag_head,\ntag_torso,\ntag_weapon,\ntag_flag,\n"
    else:
        upper_text = "tag_head,\ntag_torso,\ntag_weapon,\n"
    if "tag_floor" in objects:
        lower_text = "tag_torso,\ntag_floor,\n"
    else:
        lower_text = "tag_torso,\n"

    is_head = False
    is_upper = False
    is_lower = False

    blend_filename = bpy.path.display_name(bpy.context.blend_data.filepath)

    for object in objects:
        if object.name.startswith("h_"):
            print(f"Head: {object.name}")
            head_text += f"h_{object.name[2:]},models/players/{blend_filename.lower()}/<texture>.tga\n"
            is_head = True
        elif object.name.startswith("l_"):
            print(f"Lower: {object.name}")
            lower_text += f"l_{object.name[2:]},models/players/{blend_filename.lower()}/<texture>.tga\n"
            is_lower = True
        elif object.name.startswith("u_"):
            print(f"Upper: {object.name}")
            upper_text += f"u_{object.name[2:]},models/players/{blend_filename.lower()}/<texture>.tga\n"
            is_upper = True

    return head_text, upper_text, lower_text, is_head, is_upper, is_lower

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
                    if q3_props.offset_cgf_by_1:
                        start_frame += 1
                    end_frame = int(strip.frame_end)
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

        #existing_cube = bpy.data.objects.get(frame_buddy_name)
        #if existing_cube:
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

                    #track = obj.animation_data.nla_tracks
                    #track.name = "Q3ANIM"
                    # Iterate over the NLA strips
                    current_frame = bpy.context.scene.frame_current
                    for strip in track.strips:
                        # Calculate the new Y and Z positions
                        new_y = y_offset * y_direction
                        new_z = z_offset * z_direction

                        # Set the current frame to the strip's start frame
                        if q3_props.offset_cgf_by_1:
                            bpy.context.scene.frame_set(int(strip.frame_start)+1)
                        else:
                            bpy.context.scene.frame_set(int(strip.frame_start))

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
        try:
            from .export_md3 import MD3Exporter
            props = bpy.context.scene.q3_animation_config
            # ADD CONDITION TO CHECK IF THERE IS EVEN AN ACTIVE OBJECT??
            if bpy.context.view_layer.objects.active is not None:
                bpy.ops.object.mode_set(mode='OBJECT')
            ##########
            
            filepath = self.properties.filepath
            
            if not bpy.context.selected_objects:
                bpy.ops.object.select_all(action='SELECT')
                self.report({'WARNING'}, "Assuming all objects")

            MD3Exporter(context)(self.properties.filepath)
            if props.anim_cfg_enabled and not props.modeltype == "static":
                animation_cfg_path = filepath.replace('.md3', '_animation.cfg')
                with open(animation_cfg_path, 'w') as f:
                    f.write(save_animation_config(context))
            if props.skin_enabled and not props.modeltype == "animated":
                head_text, upper_text, lower_text, is_head, is_upper, is_lower = save_skin_file(context)
                if is_head:
                    with open(self.properties.filepath.replace('.md3', '_head_default.skin'), 'w') as f:
                        f.write(head_text)

                if is_upper:
                    with open(self.properties.filepath.replace('.md3', '_upper_default.skin'), 'w') as f:
                        f.write(upper_text)

                if is_lower:
                    with open(self.properties.filepath.replace('.md3', '_lower_default.skin'), 'w') as f:
                        f.write(lower_text)

            self.report({'INFO'}, "Export complete!")
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
