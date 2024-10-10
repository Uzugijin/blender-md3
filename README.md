# .MD3 support for Blender

Updated version of [blender-md3](https://github.com/neumond/blender-md3) addon for working with Quake 3 model format (md3).
Now works with Blender ≥ 4.1.0

Can work with animations in any form (no need to bake to Shape Keys), textures and md3 tags (added as Empty objects).

Used [this](http://www.icculus.org/homepages/phaethon/q3a/formats/md3format.html) format reference.

## Manual for Playermodel exporting:
CONSTRAINTS do not work! Parenting does!  
(Naming is not enforced in blender stage of modeling but recommended ->  
Names with .001 and alike will be ommited that will result in throwing away data in Maverick and only using the first! Npherno keeps identical names.)  

What the export addon handles:

1. Selected (fully triangulated!] mesh <objects> (object names doesn't matter, it doesn't expect h_, u_, l_ names to exist, they can be assigned in maverick or npherno - but can be assigned in blender via OBJECT names) - throws error if selected is not triangles fully (floating edges or vertexes will be omited) - doesn't throw error if nothing is selected or selected type is unhandled.  
				
2. Selected empty <objects> of Arrows type <or> no tags at all (empty type can be changed in blender) (empty names doesn't matter, it doesn't expect tag_* names to exist, they can be assigned in maverick or npherno - but can be assigned in blender via OBJECT names)- does not throw any error if there is no empty or empty type is different.  
   
3. One UV Map (first will be chosen) per object (UVmap name does not matter but keep it in sync with texture name) - does not throw error if uvmap not found.  

It does not seem to care about materials for some reason, only about blank materials on the mesh - textures will be mapped onto mesh if uvmap exists (uvmap name drives what texture name to look for). (can be assigned in Maverick or Npherno)
For multiple textures, uvmap should be named something else, idk what happens if two meshes have same named uvs but with differnt layout, which textures they are gonna use then?

## Supported versions

4.1 and up. This addon will probably not work with versions before 4.0 
API changed in how vertex normals are calculated. This broke backwards compatibility...
If I'm wrong let me know, maybe we can fix it!
