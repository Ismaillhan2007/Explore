"""Living room with a TV wall (photo: pipeline/photos/living_room_tv.jpg, kept local).
Same approach as build_room.py: original procedural geometry, Cycles-baked radiance atlases.
Run from the repository root:  Blender -b -t 8 -P tools/room/build_living_room_tv.py
(ROOM_PREVIEW=1 renders docs/living-room-tv-blender.png only, for a quick layout check.)
Coordinates: X right, Y into the room (Unity z), Z up (Unity y). Room 4.6 x 5.0 x 3.0 m,
centred on the origin. Pickables (book, mug, lamp) are NOT baked; BuildLivingRoomTV.cs places them.
"""
import bpy, math, random, os
from mathutils import Vector, Matrix
random.seed(41)
ROOT=os.getcwd(); OUT=os.path.join(ROOT,'Assets/_Project/Models/LivingRoomTV'); os.makedirs(OUT,exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32
scene.cycles.use_denoising=True; scene.world.color=(.22,.25,.30)
if os.environ.get('ROOM_PREVIEW'): scene.cycles.samples=12
scene.view_settings.view_transform='Standard'; scene.view_settings.look='None'

# ---- helpers, same as build_room.py
def mat(name,color,rough=.7,texture=None):
 m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
 n=m.node_tree.nodes; l=m.node_tree.links; p=n.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*color,1); p.inputs['Roughness'].default_value=rough
 if texture:
  tex=n.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value=1; tex.inputs['Detail'].default_value=3
  coord=n.new('ShaderNodeAttribute'); coord.attribute_name='RoomGenerated'; mapping=n.new('ShaderNodeVectorMath'); mapping.operation='MULTIPLY'; mapping.inputs[1].default_value=texture
  l.new(coord.outputs['Vector'],mapping.inputs[0]); l.new(mapping.outputs[0],tex.inputs['Vector'])
  ramp=n.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position=.15; ramp.color_ramp.elements[0].color=(*(c*(.94 if 'plaster' in name or 'Linen' in name else .72) for c in color),1); ramp.color_ramp.elements[1].position=.85; ramp.color_ramp.elements[1].color=(*(min(c*(1.04 if 'plaster' in name or 'Linen' in name else 1.15),1) for c in color),1)
  l.new(tex.outputs['Fac'],ramp.inputs[0]); l.new(ramp.outputs[0],p.inputs['Base Color'])
  bump=n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value=.16; bump.inputs['Distance'].default_value=.0004 if 'Linen' in name or 'plaster' in name else .001; l.new(tex.outputs['Fac'],bump.inputs['Height']); l.new(bump.outputs[0],p.inputs['Normal'])
 return m
def cube(name,pos,size,ma,bevel=.012):
 bpy.ops.mesh.primitive_cube_add(size=1,location=pos); o=bpy.context.object; o.name=name; o.dimensions=size; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bevel:
  mod=o.modifiers.new('Soft manufactured edges','BEVEL'); mod.width=bevel; mod.segments=3; bpy.context.view_layer.objects.active=o; bpy.ops.object.modifier_apply(modifier=mod.name)
  mod=o.modifiers.new('Weighted normals','WEIGHTED_NORMAL'); bpy.ops.object.modifier_apply(modifier=mod.name)
 return o

def cylinder(name,pos,radius,depth,ma,r2=None):
 bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=radius,radius2=radius if r2 is None else r2,depth=depth,location=pos); o=bpy.context.object; o.name=name; o.data.materials.append(ma)
 bevel=o.modifiers.new('Edge','BEVEL'); bevel.width=.006; bevel.segments=2; bpy.ops.object.modifier_apply(modifier=bevel.name)
 for p in o.data.polygons:p.use_smooth=True
 return o

def cushion(name,pos,size,ma):
 o=cube(name,pos,size,ma,min(size)*.3)
 sub=o.modifiers.new('Cloth subdivisions','SUBSURF'); sub.levels=2; bpy.context.view_layer.objects.active=o; bpy.ops.object.modifier_apply(modifier=sub.name)
 tex=bpy.data.textures.new(name+' folds',type='CLOUDS'); tex.noise_scale=.19; d=o.modifiers.new('Subtle cloth folds','DISPLACE'); d.texture=tex; d.strength=.018; bpy.ops.object.modifier_apply(modifier=d.name)
 for p in o.data.polygons:p.use_smooth=True
 return o

def rod(name,a,b,r,ma):
 a,b=Vector(a),Vector(b); o=cylinder(name,(a+b)/2,r,(b-a).length,ma); o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler(); return o


def ellipsoid(name,pos,scale,ma,rot=(0,0,0),segments=24,rings=14):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,radius=1,location=pos); o=bpy.context.object; o.name=name
 o.scale=scale; o.rotation_euler=rot; o.data.materials.append(ma)
 for p in o.data.polygons:p.use_smooth=True
 return o

def cloth_panel(name,x,y0,y1,z0,z1,folds,depth,ma):
 """Vertical curtain hanging in the YZ plane at x, with sinusoidal folds along y."""
 verts=[];faces=[];ny,nz=90,30
 for k in range(nz):
  z=z0+(z1-z0)*k/(nz-1)
  for j in range(ny):
   t=j/(ny-1); y=y0+(y1-y0)*t
   verts.append((x+depth*math.sin(t*folds*math.tau)*(0.75+0.25*k/(nz-1)),y,z))
 for k in range(nz-1):
  for j in range(ny-1):
   a=k*ny+j;faces.append((a,a+1,a+ny+1,a+ny))
 mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
 o=bpy.data.objects.new(name,mesh);scene.collection.objects.link(o);o.data.materials.append(ma)
 sol=o.modifiers.new('Thickness','SOLIDIFY');sol.thickness=.006;bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=sol.name)
 for p in mesh.polygons:p.use_smooth=True
 return o

# ---- materials (colours read off the photo)
wall=mat('Warm white plaster',(.80,.78,.74),.95,(100,100,100))
trim=mat('White trim',(.84,.83,.80))
slat=mat('Light oak slat',(.62,.48,.34),.5,(4,4,60)); cabinet_oak=mat('Light oak cabinet',(.66,.55,.43),.5,(5,70,4))
carpet=mat('Woven ivory carpet',(.66,.64,.60),1,(300,300,120))
screen=mat('TV glass',(.01,.01,.012),.08); soundbar=mat('Matte black',(.03,.03,.03),.6)
armchair=mat('Linen tweed armchair',(.42,.41,.38),.95,(260,260,260))
cane=mat('Whitewashed oak',(.68,.64,.58),.6,(5,70,4)); seat_white=mat('Linen white seat',(.82,.81,.78),.95,(160,160,160))
concrete=mat('Pale concrete top',(.50,.49,.46),.8,(30,30,30)); dark_wood=mat('Smoked oak',(.20,.19,.17),.6,(5,70,4))
brass=mat('Brushed brass',(.52,.38,.16),.3)
book_dark=mat('Book dark cover',(.10,.10,.11),.7); vase=mat('White vase',(.80,.79,.76),.35); vase_black=mat('Black vase',(.05,.05,.05),.4)
leaf_red=mat('Autumn leaves',(.35,.10,.04),.7); branch=mat('Branch',(.12,.08,.05),.8)
art=mat('Dark landscape print',(.09,.10,.12),1,(3,3,6)); paper=mat('Mat board',(.85,.84,.82),1)
blind=mat('Linen roman blind',(.82,.81,.78),.95,(120,120,120))
shelf_decor=[mat('Decor '+str(i),c,.6) for i,c in enumerate([(.62,.48,.20),(.15,.15,.15),(.70,.68,.62),(.45,.32,.18)])]

# ---- architecture: 4.6 x 5.0 m, 3.0 m to the ceiling, coffered beams down to 2.75 m.
W,D,Hc=4.6,5.0,3.0
cube('Ivory carpet',(0,0,-.02),(W,D,.04),carpet,.005)
cube('Wall left',(-2.38,0,Hc/2),(.16,D+.16,Hc),wall)
cube('Wall right',(2.38,0,Hc/2),(.16,D+.16,Hc),wall)
# Back (TV) wall with a window on its left part and a recessed shelf niche.
NX0,NX1=-.95,-.35          # niche x range, 0.35 m deep, from z .45 to 2.2
WX0,WX1=-2.05,-1.25        # window x range, z .75 to 2.35
cube('Wall back right',((NX1+W/2+.16)/2,2.58,Hc/2),(W/2+.16-NX1,.16,Hc),wall)
cube('Wall back between',((WX1+NX0)/2,2.58,Hc/2),(NX0-WX1,.16,Hc),wall)
cube('Wall back far left',((-W/2-.16+WX0)/2,2.58,Hc/2),(WX0+W/2+.16,.16,Hc),wall)
cube('Wall below window',((WX0+WX1)/2,2.58,.375),(WX1-WX0,.16,.75),wall)
cube('Wall above window',((WX0+WX1)/2,2.58,(2.35+Hc)/2),(WX1-WX0,.16,Hc-2.35),wall)
cube('Wall below niche',((NX0+NX1)/2,2.58,.225),(NX1-NX0,.16,.45),wall)
cube('Wall above niche',((NX0+NX1)/2,2.58,(2.2+Hc)/2),(NX1-NX0,.16,Hc-2.2),wall)
cube('Wall niche back',((NX0+NX1)/2,2.93,(.45+2.2)/2),(NX1-NX0+.32,.16,1.75+.16),wall)
for x in [NX0-.08,NX1+.08]:cube('Wall niche side',(x,2.76,(.45+2.2)/2),(.16,.36,1.75),wall)
cube('Wall niche top',((NX0+NX1)/2,2.76,2.28),(NX1-NX0,.36,.16),wall)
cube('Wall niche floor',((NX0+NX1)/2,2.76,.37),(NX1-NX0,.36,.16),wall)
cube('Wall front',(0,-2.58,Hc/2),(W+.32,.16,Hc),wall)
cube('Ceiling',(0,0,Hc+.06),(W+.32,D+.32,.12),wall)
for i in range(1,4):cube('Ceiling beam',(-W/2+i*W/4,0,Hc-.12),(.22,D,.24),trim,.01)
for j in range(1,4):cube('Ceiling beam',(0,-D/2+j*D/4,Hc-.1175),(W,.22,.235),trim,.01)  # 5 mm shallower: no coplanar faces where beams cross
for x in [-2.28,2.28]:cube('Skirting',(x,0,.06),(.03,D,.12),trim,.003)
cube('Crown moulding',(0,2.48,Hc-.05),(W,.06,.10),trim,.004)
# Window with a roman blind and a bright exterior.
for x in [WX0,WX1]:cube('Window casing',(x,2.49,1.55),(.07,.06,1.66),trim,.003)
for z in [.75,2.35]:cube('Window casing',((WX0+WX1)/2,2.485,z),(WX1-WX0+.07,.07,.07),trim,.003)
for x in [WX0,WX1]:cube('Window reveal',(x+(.02 if x==WX0 else -.02),2.58,1.55),(.04,.16,1.6),trim,.002)
for z in [.75,2.35]:cube('Window reveal',((WX0+WX1)/2,2.58,z+(.02 if z<1 else -.02)),(WX1-WX0,.16,.04),trim,.002)
for k in range(5):cube('Roman blind fold',((WX0+WX1)/2,2.47,2.30-k*.07),(WX1-WX0-.04,.05,.075),blind,.02)
sky=mat('Bright exterior',(.88,.92,.95)); ep=sky.node_tree.nodes.get('Principled BSDF');ep.inputs['Emission Color'].default_value=(.88,.92,.95,1);ep.inputs['Emission Strength'].default_value=1.5
cube('Exterior daylight',((WX0+WX1)/2,2.74,1.55),(WX1-WX0+.5,.02,2.0),sky,0)
# Brass wall sconce between window and niche.
cube('Sconce plate',(-1.10,2.49,1.80),(.06,.02,.16),brass,.003)
cylinder('Sconce tube',(-1.10,2.44,1.80),.025,.22,brass)
# Niche shelves with small decor.
for z in [.85,1.25,1.65,2.0]:
 cube('Niche shelf',((NX0+NX1)/2,2.78,z),(NX1-NX0,.32,.03),cabinet_oak,.003)
 for k in range(3):
  ma=shelf_decor[(int(z*10)+k)%4]; x=NX0+.1+k*.2
  if (k+int(z*10))%2: cube('Shelf box',(x,2.78,z+.07),(.10,.14,.12),ma,.006)
  else: cylinder('Shelf vase',(x,2.78,z+.09),.04,.16,ma,.03)

# ---- TV wall: slatted oak panel, TV, low oak cabinet with soundbar.
TVX=.65
for i in range(40):cube('Oak slat',(TVX-1.0+i*.05+.02,2.48,(Hc-.25)/2),(.032,.04,Hc-.25),slat,.004)
cube('Slat backing',(TVX,2.495,(Hc-.25)/2),(2.0,.01,Hc-.25),dark_wood,0)
cube('TV screen',(TVX,2.43,1.38),(1.45,.04,.84),screen,.006)
cube('Oak cabinet',(TVX,2.24,.275),(2.2,.45,.55),cabinet_oak,.01)
for x in [TVX-.55,TVX,TVX+.55]:cube('Cabinet door gap',(x,2.013,.30),(.006,.004,.46),dark_wood,0)
cube('Soundbar',(TVX,2.25,.585),(.9,.10,.07),soundbar,.01)

# ---- right wall art
cube('Art frame',(2.29,.6,1.55),(.03,1.0,1.3),paper,.004)
cube('Art print',(2.275,.6,1.60),(.006,.70,.92),art,0)

# ---- grey swivel armchair, front right, turned toward the room
def armchair_at(x,y,yaw):
 parts=[]
 parts.append(cylinder('Swivel base',(x,y,.06),.28,.12,soundbar,.30))
 parts.append(cushion('Armchair body',(x,y,.30),(.82,.80,.36),armchair))
 parts.append(cushion('Armchair seat',(x,y-.05,.52),(.62,.62,.14),armchair))
 parts.append(cushion('Armchair back',(x,y+.32,.72),(.82,.20,.56),armchair))
 for dx in [-.36,.36]:parts.append(cushion('Armchair arm',(x+dx,y,.56),(.14,.78,.32),armchair))
 parts.append(cushion('Armchair pillow',(x,y+.18,.74),(.46,.16,.40),armchair))
 pivot=Vector((x,y,0)); turn=Matrix.Translation(pivot)@Matrix.Rotation(yaw,4,'Z')@Matrix.Translation(-pivot)
 for o in parts:o.matrix_world=turn@o.matrix_world
armchair_at(1.40,.95,math.radians(-25))   # front turned toward the room centre

# ---- whitewashed accent chair by the niche, facing the room
def accent_chair(x,y):
 for dx in [-.24,.24]:
  for dy in [-.22,.22]:rod('Chair leg',(x+dx,y+dy,0),(x+dx*.9,y+dy*.9,.40),.02,cane)
 cube('Chair seat frame',(x,y,.42),(.56,.52,.05),cane,.01)
 cushion('Chair seat cushion',(x,y-.02,.49),(.50,.46,.10),seat_white)
 cube('Chair back',(x,y+.25,.70),(.56,.04,.50),cane,.01)
 for dx in [-.27,.27]:cube('Chair arm',(x+dx,y,.62),(.04,.50,.04),cane,.006)
accent_chair(-.55,1.55)

# ---- small brass side table between the chairs, top at .55
GT=(.10,1.60)
cylinder('Side table top',(GT[0],GT[1],.54),.22,.02,brass)
cylinder('Side table shelf',(GT[0],GT[1],.10),.20,.015,brass)
for a in [0,math.tau/3,math.tau*2/3]:
 xx=GT[0]+math.cos(a)*.19; yy=GT[1]+math.sin(a)*.19; rod('Side table leg',(xx,yy,0),(xx,yy,.53),.01,brass)
cylinder('Candle',(GT[0]-.08,GT[1]+.06,.59),.03,.08,vase)

# ---- tiered square coffee table, front left, top at .42
CT=(-.30,.10)
for z,s,ma in [(.06,.86,dark_wood),(.24,.92,dark_wood),(.405,1.0,concrete)]:cube('Coffee table tier',(CT[0],CT[1],z),(s,s,.03 if z>.3 else .06),ma,.008)
cube('Coffee table core',(CT[0],CT[1],.22),(.50,.50,.36),dark_wood,.006)
for k,(dx,dy) in enumerate([(-.25,.20),(-.24,.23)]):cube('Coffee table book',(CT[0]+dx,CT[1]+dy,.435+k*.03),(.30,.22,.03),book_dark,.004)
# A second, lower table at the far left with a vase of autumn branches.
LT=(-1.75,.55)
cube('Low table',(LT[0],LT[1],.36),(.90,.80,.04),concrete,.008)
cube('Low table base',(LT[0],LT[1],.17),(.70,.60,.34),dark_wood,.006)
cylinder('Branch vase',(LT[0]+.10,LT[1]+.05,.50),.08,.24,vase_black,.05)
for i in range(12):
 a=random.random()*math.tau; h=random.uniform(.35,.70); tip=Vector((LT[0]+.10+math.cos(a)*random.uniform(.15,.40),LT[1]+.05+math.sin(a)*random.uniform(.15,.40),.62+h))
 rod('Branch',(LT[0]+.10,LT[1]+.05,.60),tip,.005,branch)
 for j in range(6):
  p=Vector((LT[0]+.10,LT[1]+.05,.60)).lerp(tip,.4+j*.1)+Vector((random.uniform(-.05,.05),random.uniform(-.05,.05),random.uniform(-.03,.03)))
  ellipsoid('Autumn leaf',p,(.035,.018,.004),leaf_red,(random.random(),random.random(),random.random()),8,5)
cylinder('Small white jug',(LT[0]+.30,LT[1]-.15,.45),.05,.14,vase,.04)

# ---- lights
def area(name,pos,target,power,color,size):
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.color=color;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=pos;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area('Window daylight',((WX0+WX1)/2,2.70,1.6),(-.6,-1,.0),220,(.90,.93,1),1.2)
area('Interior bounce',(0,-.8,2.85),(0,.8,0),70,(1,.96,.90),3.5)
area('Sconce glow',(-1.10,2.40,1.95),(-1.10,2.40,3),6,(1,.80,.55),.1)
for x,y in [(-1.15,-1.25),(1.15,-1.25),(-1.15,1.25),(1.15,1.25)]:
 area('Recessed downlight',(x,y,Hc-.26),(x,y,0),14,(1,.94,.86),.12)

# ---- reference camera matching the photo (low, wide, looking at the TV wall)
bpy.ops.object.camera_add(location=(.55,-1.75,1.10));camera=bpy.context.object
camera.rotation_euler=(Vector((-.10,2.5,1.05))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=20;scene.camera=camera
scene.render.resolution_x=1000;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
# Preserve each object's procedural coordinates when meshes are joined for the atlas.
# Blender Generated coordinates otherwise change to the combined room bounds.
for obj in scene.objects:
 if obj.type!='MESH':continue
 coords=[v.co for v in obj.data.vertices]
 low=Vector(tuple(min(v[i] for v in coords) for i in range(3)))
 high=Vector(tuple(max(v[i] for v in coords) for i in range(3)))
 attr=obj.data.attributes.new('RoomGenerated','FLOAT_VECTOR','POINT')
 for v,item in zip(coords,attr.data):item.vector=tuple((v[i]-low[i])/max(high[i]-low[i],.000001) for i in range(3))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT,'tools/room/LivingRoomTV.blend'))
scene.render.filepath=os.path.join(ROOT,'docs/living-room-tv-blender.png');bpy.ops.render.render(write_still=True)
if os.environ.get('ROOM_PREVIEW'):  # quick layout check: render only, no bake/export
 print('ROOM_PREVIEW_DONE'); import sys; sys.exit(0)
# Keep walls independently tintable. Bake geometry into two economical radiance atlases.
meshes=[o for o in scene.objects if o.type=='MESH'];groups=[('Architecture',[o for o in meshes if o.name.startswith('Wall') or o.name=='Ceiling'],2048),('Furnishings',[o for o in meshes if not(o.name.startswith('Wall') or o.name=='Ceiling')],4096)]
for name,objects,res in groups:
 bpy.ops.object.select_all(action='DESELECT')
 for o in objects:o.select_set(True)
 bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();o=bpy.context.object;o.name=name
 bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
 bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=1.15,island_margin=.003);bpy.ops.object.mode_set(mode='OBJECT')
 image=bpy.data.images.new(name+'Radiance',width=res,height=res)
 for m in o.data.materials:
  if m:
   n=m.node_tree.nodes.new('ShaderNodeTexImage');n.image=image;m.node_tree.nodes.active=n
 scene.render.bake.margin=16;scene.render.bake.margin_type='EXTEND';scene.cycles.samples=12
 print('BAKE_START '+name,flush=True)
 bpy.ops.object.bake(type='COMBINED')
 print('BAKE_END '+name,flush=True)
 image.filepath_raw=os.path.join(OUT,name+'.png');image.file_format='PNG';image.save()
 baked=bpy.data.materials.new(name+' Baked');baked.use_nodes=True;n=baked.node_tree.nodes;l=baked.node_tree.links;n.clear();tex=n.new('ShaderNodeTexImage');tex.image=image;em=n.new('ShaderNodeEmission');output=n.new('ShaderNodeOutputMaterial');l.new(tex.outputs[0],em.inputs[0]);l.new(em.outputs[0],output.inputs[0]);o.data.materials.clear();o.data.materials.append(baked)
 for p in o.data.polygons:p.material_index=0
 bpy.ops.export_scene.fbx(filepath=os.path.join(OUT,name+'.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Z',axis_up='Y',bake_space_transform=True,add_leaf_bones=False)
scene.render.filepath=os.path.join(ROOT,'docs/living-room-tv-baked-blender.png');bpy.ops.render.render(write_still=True)
print('ROOM_EXPORT_COMPLETE')
