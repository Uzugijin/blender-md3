# grouping to surfaces must done by UV maps also, not only normals
# TODO: merge surfaces with same uv maps and texture
# TODO: check bounding sphere calculation
#line 158 "return co" modified to "return co * 10" 
#line 337 added static variable

import re
from collections import defaultdict
from math import sqrt

import bpy
import mathutils
import bmesh
from . import fmt_md3 as fmt
from .utils import OffsetBytesIO
from .assembly_map import get_group_frame_range, get_frames_from_strips, get_q3anim_object

nums = re.compile(r'\.\d{3}$')

def prepare_name(name):
    if nums.findall(name):
        return name[:-4]  # cut off blender's .001 .002 etc
    return name

def get_textures(material):
    textures = []
    if material is None:
        return textures
    if material.node_tree:
        for tex in material.node_tree.nodes:
            if tex.type=='TEX_IMAGE':
                textures.append(tex)
    return textures

def gather_shader_info(mesh):
    'Returning uvmap name, texture name list'
    uv_maps = mesh.uv_layers
    materials = []
    for material in mesh.materials:
        textures = get_textures(material)
        materials.append(material.name)
        
        for texture_slot in textures:
            if (
                texture_slot is None
            ):
                continue

            # one UV map can be used by many textures
    if len(uv_maps) <= 0:
        print('Warning: No UV maps found, zero filling will be used')
        return None, []
    elif len(uv_maps) == 1 or len(materials) == 1:
        return uv_maps.active.name, materials[0]
    else:
        print('Warning: Multiple UV maps found, only one will be chosen')
        return uv_maps.active.name, materials[0]

def gather_vertices(mesh, uvmap_data=None):
    md3vert_to_loop_map = []
    loop_to_md3vert_map = []
    index = {}
    for i, loop in enumerate(mesh.loops):
        key = (
            loop.vertex_index,
            tuple(loop.normal),
            None if uvmap_data is None else tuple(uvmap_data[i].uv),
        )
        md3id = index.get(key, None)
        if md3id is None:
            md3id = len(md3vert_to_loop_map)
            index[key] = md3id
            md3vert_to_loop_map.append(i)
        loop_to_md3vert_map.append(md3id)

    return md3vert_to_loop_map, loop_to_md3vert_map

def interp(a, b, t):
    return (b - a) * t + a

def find_interval(vs, t):
    a, b = 0, len(vs) - 1
    if t < vs[a]:
        return None, a
    if t > vs[b]:
        return b, None
    while b - a > 1:
        c = (a + b) // 2
        if vs[c] > t:
            b = c
        else:
            a = c
    assert vs[a] <= t <= vs[b]
    return a, b

class MD3Exporter:
    def __init__(self, context, group_data=None):
        self.context = context
        self.scene = context.scene
        self.group_data = group_data
        self.scale_multiplier = self.scene.q3_animation_config.scale_multiplier
        self.strip_indices = group_data.get('action_strips', []) if group_data else []
        self.modeltype = self.scene.q3_animation_config.modeltype
        #self.export_frames = get_group_frame_range(self.scene, self.group_data, self.modeltype)
    
    def pack_tag(self, name):
        obj = self.scene.objects[name]
        
        # === HANDLE MESH TAGS ===
        if obj.type == 'MESH' and obj.name.startswith('tag_'):
            # Calculate tag transform from animated mesh geometry
            tag_matrix = self.calculate_tag_matrix_from_animated_mesh(obj)
            origin = tag_matrix.to_translation()
            m = tag_matrix.to_3x3().transposed()
        else:
            # Regular empty tag
            origin = tuple(obj.location)
            m = obj.matrix_basis.transposed()
                        
        return fmt.Tag.pack(
            name=prepare_name(obj.name),
            origin=origin,
            axis=sum([tuple(m[j].xyz) for j in range(3)], ()),
        )

    def calculate_tag_matrix_from_animated_mesh(self, mesh_obj):
        """Calculate tag transform from animated mesh geometry for current frame"""
        # Get evaluated mesh (with armature deformation applied)
        dg = bpy.context.evaluated_depsgraph_get()
        mesh_eval = mesh_obj.evaluated_get(dg).to_mesh()
        
        if len(mesh_eval.polygons) == 0:
            print(f"Warning: Tag mesh {mesh_obj.name} has no polygons, using object transform")
            return mesh_obj.matrix_world
        
        # Get the first polygon (the L-shaped triangle)
        poly = mesh_eval.polygons[0]
        
        if len(poly.vertices) != 3:
            print(f"Warning: Tag mesh {mesh_obj.name} is not a triangle, using object transform")
            mesh_eval = mesh_obj.evaluated_get(dg).to_mesh_clear()
            return mesh_obj.matrix_world
        
        # Get vertex positions in world space (with animation applied)
        verts_world = [mesh_obj.matrix_world @ mesh_eval.vertices[i].co for i in poly.vertices]
        
        # === EDGE LENGTH ANALYSIS ===
        # Calculate all three edges and their lengths
        edges = [
            (0, 1, (verts_world[1] - verts_world[0]).length),  # Edge 0-1
            (1, 2, (verts_world[2] - verts_world[1]).length),  # Edge 1-2
            (2, 0, (verts_world[0] - verts_world[2]).length)   # Edge 2-0
        ]
        
        # Sort edges by length
        edges.sort(key=lambda x: x[2])
        
        # Identify edges:
        shortest_idx = edges[0]  # (v0, v1, length) - MD3 Y axis
        middle_idx = edges[1]    # (v0, v1, length) - MD3 X axis  
        longest_idx = edges[2]   # (v0, v1, length) - Ignored (hypotenuse)
        
        print(f"Edge lengths: Shortest={shortest_idx[2]:.3f}, Middle={middle_idx[2]:.3f}, Longest={longest_idx[2]:.3f}")
        
        # Find the common vertex (the corner of the L)
        all_vertices = set(range(3))
        shortest_vertices = {shortest_idx[0], shortest_idx[1]}
        middle_vertices = {middle_idx[0], middle_idx[1]}
        
        # The common vertex should be in both shortest and middle edges
        common_vertices = shortest_vertices.intersection(middle_vertices)
        
        if len(common_vertices) == 1:
            origin_idx = common_vertices.pop()
            origin = verts_world[origin_idx]
            
            # Get the other vertices for each edge
            short_other_idx = shortest_idx[1] if shortest_idx[0] == origin_idx else shortest_idx[0]
            middle_other_idx = middle_idx[1] if middle_idx[0] == origin_idx else middle_idx[0]
            
            # Calculate axes FROM origin TO other vertices
            y_axis_vec = verts_world[short_other_idx] - origin  # Shortest = Y axis
            x_axis_vec = verts_world[middle_other_idx] - origin  # Middle = X axis
            
        else:
            # Fallback - use the vertex that's NOT in the longest edge
            longest_vertices = {longest_idx[0], longest_idx[1]}
            possible_origins = all_vertices - longest_vertices
            
            if len(possible_origins) == 1:
                origin_idx = possible_origins.pop()
                origin = verts_world[origin_idx]
                
                # Find which edges contain the origin and get the other vertices
                for edge in [shortest_idx, middle_idx]:
                    if edge[0] == origin_idx:
                        if edge == shortest_idx:
                            y_axis_vec = verts_world[edge[1]] - origin
                        else:
                            x_axis_vec = verts_world[edge[1]] - origin
                    elif edge[1] == origin_idx:
                        if edge == shortest_idx:
                            y_axis_vec = verts_world[edge[0]] - origin
                        else:
                            x_axis_vec = verts_world[edge[0]] - origin
            else:
                # Last resort fallback
                print(f"Warning: Could not determine L-corner for tag {mesh_obj.name}, using vertex 0 as origin")
                origin = verts_world[0]
                x_axis_vec = verts_world[1] - origin
                y_axis_vec = verts_world[2] - origin
        
        # Normalize axes
        x_axis = x_axis_vec.normalized()
        y_axis = y_axis_vec.normalized()
        
        # Calculate Z axis (normal) - use polygon normal for consistent orientation
        z_axis = poly.normal.copy()
        z_axis.normalize()
               
        # Re-orthogonalize axes against the consistent Z
        x_axis = x_axis - z_axis * x_axis.dot(z_axis)
        x_axis.normalize()
        y_axis = z_axis.cross(x_axis)
        y_axis.normalize()
        
        # === MD3 COORDINATE SYSTEM ===
        md3_x_axis = x_axis  # Middle edge = MD3 X (forward)
        md3_y_axis = y_axis  # Shortest edge = MD3 Y (left) 
        md3_z_axis = z_axis   # Polygon normal = MD3 Z (up)
        
        scaled_origin = origin * self.scale_multiplier

        # Create transformation matrix with MD3 axes
        tag_matrix = mathutils.Matrix((
            (md3_x_axis.x, md3_y_axis.x, md3_z_axis.x, scaled_origin.x),
            (md3_x_axis.y, md3_y_axis.y, md3_z_axis.y, scaled_origin.y), 
            (md3_x_axis.z, md3_y_axis.z, md3_z_axis.z, scaled_origin.z),
            (0, 0, 0, 1)
        ))
        
        # Clean up evaluated mesh
        mesh_eval = mesh_obj.evaluated_get(dg).to_mesh_clear()
        
        return tag_matrix

    def pack_animated_tags(self, static):
        tags_bin = []
        for i, actual_frame in enumerate(self.export_frames):  # Use actual frames
            if static:
                self.scene.frame_set(self.scene.frame_current)
            else:
                self.scene.frame_set(actual_frame)  # Jump to actual frame
            for name in self.tagNames:
                tags_bin.append(self.pack_tag(name))
        return b''.join(tags_bin)

    def pack_surface_shader(self, i):
        return fmt.Shader.pack(
            name=prepare_name(self.mesh_shader_list),
            index=i,
        )

    def pack_surface_triangle(self, i):
        polygon = self.mesh.polygons[i]
        print(f"Polygon {i} has {polygon.loop_total} loops")
        if polygon.loop_total != 3:
            print(f"Warning: Non-triangular polygon found at index {i}")
            # Handle non-triangular polygons
            # You could either skip this polygon or try to triangulate it
            return
        assert self.mesh.polygons[i].loop_total == 3
        start = self.mesh.polygons[i].loop_start
        a, b, c = (self.mesh_loop_to_md3vert[j] for j in range(start, start + 3))
        return fmt.Triangle.pack(a, c, b)  # swapped c/b

    def get_evaluated_vertex_co(self, frame, i):
        co = self.mesh.vertices[i].co.copy()

        if self.mesh_sk_rel is not None:
            bco = co.copy()
            for ki, k in enumerate(self.mesh.shape_keys.key_blocks):
                co += (k.data[i].co - bco) * self.mesh_sk_rel[ki]
        elif self.mesh_sk_abs is not None:
            kbs = self.mesh.shape_keys.key_blocks
            a, b, t = self.mesh_sk_abs
            co = interp(kbs[a].data[i].co, kbs[b].data[i].co, t)

        co = self.mesh_matrix @ co
        self.mesh_vco[frame].append(co)
        return co * self.scale_multiplier

    def pack_surface_vert(self, frame, i):
        loop_id = self.mesh_md3vert_to_loop[i]
        vert_id = self.mesh.loops[loop_id].vertex_index
        return fmt.Vertex.pack(
            *self.get_evaluated_vertex_co(frame, vert_id),
            normal=tuple(self.mesh.loops[loop_id].normal))

    def pack_surface_ST(self, i):
        if self.mesh_uvmap_name is None:
            s, t = 0.0, 0.0
        else:
            loop_idx = self.mesh_md3vert_to_loop[i]
            s, t = self.mesh.uv_layers[self.mesh_uvmap_name].data[loop_idx].uv
        return fmt.TexCoord.pack(s, t)

    def surface_start_frame(self, i, static):
        actual_frame = self.export_frames[i]  # Get the actual frame number
        
        if static:
            self.scene.frame_set(self.scene.frame_current)
        else:
            self.scene.frame_set(actual_frame)  # Jump to actual frame
        obj = bpy.context.view_layer.objects.active
        self.mesh_matrix = obj.matrix_world
        obj.update_from_editmode()
        dg = bpy.context.evaluated_depsgraph_get()
        ob_eval = obj.evaluated_get(dg)
        self.mesh = ob_eval.to_mesh()

        self.mesh_sk_rel = None
        self.mesh_sk_abs = None

        shape_keys = self.mesh.shape_keys
        if shape_keys is not None:
            kblocks = shape_keys.key_blocks
            if shape_keys.use_relative:
                self.mesh_sk_rel = [k.value for k in kblocks]
            else:
                e = shape_keys.eval_time / 100.0
                a, b = find_interval([k.frame for k in kblocks], e)
                if a is None:
                    self.mesh_sk_abs = (b, b, 0.0)
                elif b is None:
                    self.mesh_sk_abs = (a, a, 0.0)
                else:
                    self.mesh_sk_abs = (a, b, (e - kblocks[a].frame) / (kblocks[b].frame - kblocks[a].frame))

    def pack_surface(self, surf_name, static):
        obj = self.scene.objects[surf_name]
        bpy.context.view_layer.objects.active = obj
        
        dg = bpy.context.evaluated_depsgraph_get()
        self.mesh = obj.to_mesh(preserve_all_data_layers=True, depsgraph=dg)

        self.mesh_uvmap_name, self.mesh_shader_list = gather_shader_info(self.mesh)
        self.mesh_md3vert_to_loop, self.mesh_loop_to_md3vert = gather_vertices(
            self.mesh,
            None if self.mesh_uvmap_name is None else self.mesh.uv_layers[self.mesh_uvmap_name].data)

        nShaders = len(self.mesh_shader_list)
        nVerts = len(self.mesh_md3vert_to_loop)
        
        # Use bmesh for proper triangulation that matches Blender's behavior
        bm = bmesh.new()
        bm.from_mesh(self.mesh)
        
        # Ensure we're working with triangles using Blender's triangulation
        bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='BEAUTY', ngon_method='BEAUTY')
        
        # Now build our triangle list from the triangulated bmesh
        nTris_actual = 0
        triangulated_faces = []
        
        # Create a mapping from original loops to md3vert indices
        loop_to_md3vert_map = {}
        for md3vert_idx, loop_idx in enumerate(self.mesh_md3vert_to_loop):
            loop_to_md3vert_map[loop_idx] = md3vert_idx
        
        # Process each face in the triangulated mesh
        for face in bm.faces:
            if len(face.verts) != 3:
                continue  # Shouldn't happen after triangulation, but just in case
      
            # Get the loop indices for this face
            loop_indices = []
            for loop in face.loops:
                # Find the original loop index that corresponds to this bmesh loop
                # This is a bit complex because we need to map back to the original mesh
                for orig_loop_idx, md3vert_idx in enumerate(self.mesh_loop_to_md3vert):
                    if (self.mesh.loops[orig_loop_idx].vertex_index == loop.vert.index and
                        orig_loop_idx in loop_to_md3vert_map):
                        loop_indices.append(orig_loop_idx)
                        break
            
            if len(loop_indices) == 3:
                # Convert loop indices to md3vert indices
                a = loop_to_md3vert_map.get(loop_indices[0], loop_indices[0])
                b = loop_to_md3vert_map.get(loop_indices[1], loop_indices[1])
                c = loop_to_md3vert_map.get(loop_indices[2], loop_indices[2])
                
                triangulated_faces.append((a, c, b))  # swapped c/b
                nTris_actual += 1
        bm.free()
        
        f = OffsetBytesIO(start_offset=fmt.Surface.size)
        f.mark('offShaders')
        f.write(b''.join([self.pack_surface_shader(i) for i in range(nShaders)]))
        f.mark('offTris')
        
        # Write all triangles
        triangle_data = b''.join([fmt.Triangle.pack(a, b, c) for a, b, c in triangulated_faces])
        f.write(triangle_data)
        
        f.mark('offST')
        f.write(b''.join([self.pack_surface_ST(i) for i in range(nVerts)]))
        f.mark('offVerts')

        for frame in range(self.nFrames):
            self.surface_start_frame(frame, static)
            f.write(b''.join([self.pack_surface_vert(frame, i) for i in range(nVerts)]))

        f.mark('offEnd')

        print('Surface {}: nVerts={}{} nTris={}{} nShaders={}{}'.format(
            surf_name,
            nVerts, ' (Too many!)' if nVerts > 4096 else '',
            nTris_actual, ' (Too many!)' if nTris_actual > 8192 else '',
            nShaders, ' (Too many!)' if nShaders > 256 else '',
        ))

        return fmt.Surface.pack(
            magic=fmt.MAGIC,
            name=prepare_name(obj.name),
            flags=0,  # ignored
            nFrames=self.nFrames,
            nShaders=nShaders,
            nVerts=nVerts,
            nTris=nTris_actual,
            **f.getoffsets()
        ) + f.getvalue()

    def get_frame_data(self, i):
        center = mathutils.Vector((0.0, 0.0, 0.0))
        x1, x2, y1, y2, z1, z2 = [0.0] * 6
        first = True
        for co in self.mesh_vco[i]:
            if first:
                x1, x2 = co.x, co.x
                y1, y2 = co.y, co.y
                z1, z2 = co.z, co.z
            else:
                x1, y1, z1 = min(co.x, x1), min(co.y, y1), min(co.z, z1)
                x2, y2, z2 = max(co.x, x2), max(co.y, y2), max(co.z, z2)
            first = False
            center += co
        if len(self.mesh_vco[i]):  # issue #9
            center /= len(self.mesh_vco[i])  # TODO: can be very distorted
        r = 0.0
        for co in self.mesh_vco[i]:
            r = max(r, (co - center).length_squared)
        r = sqrt(r)
        return {
            'minBounds': (x1, y1, z1),
            'maxBounds': (x2, y2, z2),
            'radius': r,  # TODO: not sure the radius is measured from center, and not localOrigin
        }

    def pack_frame(self, i):
        track_name = "Q3ANIM"
        frame_name = 'Unknown'
        
        # Find object with Q3ANIM track
        obj = next((o for o in bpy.data.objects 
                if o.animation_data and track_name in o.animation_data.nla_tracks), None)
        
        if obj:
            q3anim_track = obj.animation_data.nla_tracks.get(track_name)
            if q3anim_track:
                # Find the strip that is active at the current frame
                active_strip = next((strip for strip in q3anim_track.strips 
                                    if strip.frame_start <= i <= strip.frame_end), None)
                if active_strip:
                    # Calculate the frame number within the strip
                    frame_number = i - active_strip.frame_start
                    # Use the name and frame number of the active strip as the frame name
                    frame_name = f"{active_strip.name}_{int(frame_number)}"
        
        # Pack the frame with the determined name
        return fmt.Frame.pack(
            localOrigin=(0.0, 0.0, 0.0),
            name=frame_name,
            **self.get_frame_data(i)
        )

    def __call__(self, filename):
        static = False
        if self.modeltype == "static":
            static = True

        if self.group_data:
            # Group-aware export - use objects from group_data
            self.surfNames = [obj.name for obj in self.group_data['collected_objects'] 
                        if obj.type == 'MESH' and not obj.name.startswith('tag_') and not obj.hide_get()]
            self.tagNames = [obj.name for obj in self.group_data['collected_objects'] 
                       if ((obj.type == 'EMPTY' and obj.empty_display_type == 'ARROWS') or 
                           (obj.type == 'MESH' and obj.name.startswith('tag_'))) and not obj.hide_get()]

            # Handle frame strips if provided
            if self.group_data.get('action_strips'):
                self.export_frames = get_frames_from_strips(self.group_data['action_strips'])
            else:
                self.export_frames = [0]  # No animation
        else:
            # Old behavior - use all selected objects
            self.surfNames = []
            self.tagNames = []
            for o in bpy.context.selected_objects:
                if o.hide_get():
                    continue
                if o.type == 'MESH' and not o.name.startswith('tag_'):
                    self.surfNames.append(o.name)
                elif o.type == 'EMPTY' and o.empty_display_type == 'ARROWS' or o.type == 'MESH' and o.name.startswith('tag_') and not o.hide_get():
                    self.tagNames.append(o.name)
            
            if static:
                self.export_frames = [0]
            else:
                self.export_frames = range(self.scene.frame_start, self.scene.frame_end + 1)

        self.nFrames = len(self.export_frames)
        self.mesh_vco = defaultdict(list)

        tags_bin = self.pack_animated_tags(static)
        surfaces_bin = [self.pack_surface(name, static) for name in self.surfNames]
        frames_bin = [self.pack_frame(actual_frame) for actual_frame in self.export_frames]

        if len(surfaces_bin) == 0:
            print("WARNING: There're no visible surfaces to export")

        f = OffsetBytesIO(start_offset=fmt.Header.size)
        f.mark('offFrames')
        f.write(b''.join(frames_bin))
        f.mark('offTags')
        f.write(tags_bin)
        f.mark('offSurfaces')
        f.write(b''.join(surfaces_bin))
        f.mark('offEnd')

        with open(filename, 'wb') as file:
            file.write(fmt.Header.pack(
                magic=fmt.MAGIC,
                version=fmt.VERSION,
                modelname=self.scene.name,
                flags=0,  # ignored
                nFrames=self.nFrames,
                nTags=len(self.tagNames),
                nSurfaces=len(surfaces_bin),
                nSkins=0,  # count of skins, ignored
                **f.getoffsets()
            ))
            file.write(f.getvalue())
            print('nFrames={} nSurfaces={}'.format(self.nFrames, len(surfaces_bin)))