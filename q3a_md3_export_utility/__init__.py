bl_info = {
    "name": "Q3A MD3 Export Utility",
    "author": "Vitaly Verhovodov, Aleksander Marhall, Uzugijin",
    "version": (0, 3, 0),
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

class Q3AnimationConfigProperties(bpy.types.PropertyGroup):
    selected_object: bpy.props.PointerProperty(name="Target object to import actions to", type=bpy.types.Object, description="Recommended for single skeleton, otherwise leave blank to generate a dummy")
    fixedtorso: bpy.props.BoolProperty(name="Fixed Torso", default=False, description="Don't rotate torso pitch when looking up or down")
    fixedlegs: bpy.props.BoolProperty(name="Fixed Legs", default=False, description="Don't rotate legs (always align with torso)")
    fill_dead: bpy.props.BoolProperty(name="Fill Dead", default=True, description="Create _DEAD strips for every _DEATH")
    trim_ends: bpy.props.BoolProperty(name="Trim Strips", default=True, description="Cut the end of loop strips in the NLA track")
    offset_cgf_by_1: bpy.props.BoolProperty(name="Offset By 1", default=False, description="Offsets animation sequence forward by 1 frame")
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
    export_defined: bpy.props.EnumProperty(
        items=[
            ("export md3_anim", "MD3+Animation.cfg", ""),
            ("export md3", "MD3", ""),
            ("export anim", "Animation.cfg", ""),
        ],
        name="Export",
        default="export md3_anim",
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

        #row = layout.row()
        #row.label(text="NLA Track Target:")
        row = layout.row()
        row.prop(q3_props, "selected_object", text="Target")
        row = layout.row()
        row.prop(context.scene.q3_animation_config, "trim_ends", text="Trim Loops", toggle=False)
        row = layout.row()
        #row.prop(context.scene.q3_animation_config, "auto_create_missing", text="Auto Create Missing Actions", toggle=False)
        #if q3_props.auto_create_missing:
            #row = layout.row()
        row.prop(context.scene.q3_animation_config, "fill_dead", text="Create _DEAD Frames", toggle=False)
        #row.prop(context.scene.q3_animation_config, "no_team_arena", text="No Team Arena Actions", toggle=False)
        row = layout.row()
        row.operator("q3.import_actions", text="(Re)Build NLA")

        row = layout.row()
        row.label(text="Animation Config:")
        row = layout.row()
        row.prop(q3_props, "sex_defined")
        row = layout.row()
        row.prop(q3_props, "footsteps_defined")

        row = layout.row()
        row.prop(context.scene.q3_animation_config, "fixedtorso", text="Fixed Torso", toggle=False)
        row.prop(context.scene.q3_animation_config, "fixedlegs", text="Fixed Legs", toggle=False)
        row = layout.row()
        row.prop(context.scene.q3_animation_config, "offset_cgf_by_1", text="Offset Sequence", toggle=False)
        row = layout.row()
        row.prop(q3_props, "export_defined")

        row = layout.row()
        row.operator("export_scene.md3", text="Export")
        row = layout.row()
        row.operator("q3.open_cheatsheet", text="Open Cheatsheet")

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

    def parse_action_name(action_name):
        looping_anims = [
            'LEGS_WALKCR',
            'LEGS_WALK',
            'LEGS_RUN',
            'LEGS_BACK',
            'LEGS_SWIM',
            'LEGS_IDLE',
            'LEGS_IDLECR',
            'LEGS_TURN'
        ]

        dead_anims = [
            'BOTH_DEATH1',
            'BOTH_DEATH2',
            'BOTH_DEATH3'
        ]

        parts = action_name.split('.')
        name = parts[0]
        fps = bpy.context.scene.render.fps
        looping_frames = 0
        is_dead = False

        if name in looping_anims:
            looping_frames = num_frames  # Placeholder to indicate looping frames should match num_frames

        if name in dead_anims:
            is_dead = False

        for part in parts[1:]:
            if part.isdigit():
                fps = int(part)

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
    output += "// animation config file generated by q3animcfg blender3d extension\n\n"
    output += f"{q3_props.sex_defined}\n"
    output += f"{q3_props.footsteps_defined}\n"
    if q3_props.fixedtorso:
        output += "fixedtorso\n"
    if q3_props.fixedlegs:
        output += "fixedlegs\n"
    output += "\n// first frame, num frames, looping frames, frames per second\n\n"

    # Iterate through all NLA tracks
    objects = [q3_props.selected_object] if q3_props.selected_object else bpy.data.objects
    for obj in objects:
        if obj and obj.animation_data and obj.animation_data.nla_tracks:
            for track in obj.animation_data.nla_tracks:
                for strip in track.strips:
                    start_frame = int(strip.frame_start)
                    if q3_props.offset_cgf_by_1:
                        start_frame += 1
                    end_frame = int(strip.frame_end)
                    num_frames = end_frame - start_frame

                    name, fps, looping_frames, is_dead = parse_action_name(strip.name)
                    if looping_frames == -1:
                        looping_frames = num_frames

                        # Write the formatted output to the file
                    output += f"{start_frame}\t{num_frames}\t{looping_frames}\t{fps}\t\t// {name}\n"

                    if is_dead:
                        dead_name = rename_to_dead(name)
                        output += f"{end_frame - 1}\t1\t0\t{fps}\t\t// {dead_name}\n"
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
    bl_description = "Compile Actions to NLA for export and animation sequence read."
    def execute(self, context):
        scene = context.scene
        q3_props = scene.q3_animation_config
        selected_objects = bpy.context.selected_objects
        check = bpy.data.objects.get("NLA-Compiler")
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

        existing_cube = bpy.data.objects.get(frame_buddy_name)
        if existing_cube:
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

        if q3_props.fill_dead:
            death_actions = ["BOTH_DEATH1", "BOTH_DEATH2", "BOTH_DEATH3"]
            for death_action_name in death_actions:
                death_action = bpy.data.actions.get(death_action_name)
                if death_action:
                    last_frame = death_action.frame_range[1]
                    new_action_name = f"BOTH_DEAD{death_actions.index(death_action_name) + 1}"
                    new_action = bpy.data.actions.new(new_action_name)
                    new_action.frame_range = (last_frame, last_frame)
                    new_action.use_fake_user = True  # Set to True to prevent deletion
                    new_action["auto_created"] = True
        else: 
            for action in bpy.data.actions:
                if "auto_created" in action and action["auto_created"]:
                    bpy.data.actions.remove(action)

        actions = [
            "BOTH_DEATH1", "BOTH_DEAD1", "BOTH_DEATH2", "BOTH_DEAD2", "BOTH_DEATH3", "BOTH_DEAD3",
            "TORSO_GESTURE", "TORSO_ATTACK", "TORSO_ATTACK2", "TORSO_DROP", "TORSO_RAISE", "TORSO_STAND",
            "TORSO_STAND2", "LEGS_WALKCR", "LEGS_WALK", "LEGS_RUN", "LEGS_BACK", "LEGS_SWIM", "LEGS_JUMP",
            "LEGS_LAND", "LEGS_JUMPB", "LEGS_LANDB", "LEGS_IDLE", "LEGS_IDLECR", "LEGS_TURN",
            "TORSO_GETFLAG", "TORSO_GUARDBASE", "TORSO_PATROL", "TORSO_FOLLOWME", "TORSO_AFFIRMATIVE", "TORSO_NEGATIVE"
        ]

        track = obj.animation_data.nla_tracks.new(prev=None)
        track.name = "Q3ANIM"
        frame_offset = 0

        trim_actions = [
            "TORSO_STAND", "TORSO_STAND2", "LEGS_WALKCR", "LEGS_WALK", "LEGS_RUN", "LEGS_BACK", "LEGS_SWIM", "LEGS_IDLE", "LEGS_IDLECR", "LEGS_TURN"
        ]

        for action_name in actions:
            action = bpy.data.actions.get(action_name)
            if action:
                strip = track.strips.new(action_name, int(frame_offset), action)
                strip.action = action

                # Trim ends if enabled and action is in trim_actions list
                if q3_props.trim_ends and action_name in trim_actions and strip.frame_end - strip.frame_start > 1:
                    strip.frame_end -= 1

                frame_offset += strip.frame_end - strip.frame_start
        bpy.context.scene.frame_end = int(frame_offset)

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
        props = bpy.context.scene.q3_animation_config
        export_defined = props.export_defined
        if export_defined == 'export md3' or export_defined == 'export md3_anim':
            self.filename_ext = ".md3"
        elif export_defined == 'export anim':
            self.filename_ext = ".cfg"
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
            export_defined = props.export_defined
            
            if export_defined == 'export md3':
                if not bpy.context.selected_objects:
                    bpy.ops.object.select_all(action='SELECT')
                    self.report({'WARNING'}, "Assuming all objects")
                MD3Exporter(context)(self.properties.filepath)
            elif export_defined == 'export md3_anim':
                if not bpy.context.selected_objects:
                    bpy.ops.object.select_all(action='SELECT')
                    self.report({'WARNING'}, "Assuming all objects")
                MD3Exporter(context)(self.properties.filepath)
                animation_cfg_path = filepath.replace('.md3', '_animation.cfg')
                with open(animation_cfg_path, 'w') as f:
                    f.write(save_animation_config(context))
            elif export_defined == 'export anim':
                animation_cfg_path = self.properties.filepath
                with open(animation_cfg_path, 'w') as f:
                    f.write(save_animation_config(context))
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
