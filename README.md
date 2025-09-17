# .MD3 support for Blender  

Updated version of [blender-md3](https://github.com/neumond/blender-md3) addon for working with Quake 3 model format (md3).  
Now works with Blender ≥ 4.1.0  

Can work with animations in any form (no need to bake to Shape Keys), textures and md3 tags (added as Empty objects).  

Used [this](http://www.icculus.org/homepages/phaethon/q3a/formats/md3format.html) format reference.  

## Manual for Playermodel exporting:  
CONSTRAINTS do not work! (unless animation is baked - not confirmed) Parenting does!  
(Naming is not enforced in blender stage of modeling but recommended ->  
Names with .001 and alike will be ommited that will result in throwing away data in Maverick and only using the first! Npherno keeps identical names.)  

What the export addon handles:  

1. Selected mesh <objects> (object names doesn't matter, it doesn't expect h_, u_, l_ names to exist, they can be assigned in maverick or npherno - but can be assigned in blender via OBJECT names) - Q3 MD3 XU only: Addon triangulates meshes with BEAUTY - Floating edges or vertices will be omited - If nothing is selected, the whole scene will be attempted for export. Unhandled object types will be ignored.  
				
2. Selected empty <objects> of Arrows type. (empty type can be changed in blender) (empty names doesn't matter, it doesn't expect tag_* names to exist, they can be assigned in maverick or npherno - but can be assigned in blender via OBJECT names)- does not throw any error if there is no empty or empty type is different. If empty attached to bone as tag, the animation should be baked or at least so I heard.  
   
3. One UV Map (first will be chosen) per object - does not throw error if uvmap not found.  

4. Material name will be used as path for quake 3 material / texture. (Note - You must export texture as Targa RAW for quake 3.) - Throws error if there are no materials.  

## Supported versions  

4.1 and up for a while. This addon will probably not work with versions before 4.0   
