"""Living room with a grey sofa (photo: pipeline/photos/living_room_sofa.jpg, kept local).
Same approach as build_room.py: original procedural geometry, Cycles-baked radiance atlases.
Run from the repository root:  Blender -b -t 8 -P tools/room/build_living_room_sofa.py
(ROOM_PREVIEW=1 renders docs/living-room-sofa-blender.png only, for a quick layout check.)
Coordinates: X right, Y into the room (Unity z), Z up (Unity y). Room 4.2 x 4.8 x 2.7 m,
centred on the origin. Pickables (mug, book, lamp) are NOT baked; BuildLivingRoomSofa.cs places them.
"""
import bpy, math, random, os
from mathutils import Vector
random.seed(23)
ROOT=os.getcwd(); OUT=os.path.join(ROOT,'Assets/_Project/Models/LivingRoomSofa'); os.makedirs(OUT,exist_ok=True)
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
wall=mat('Soft grey plaster',(.70,.72,.69),.95,(100,100,100))
trim=mat('White trim',(.80,.81,.79))
oak=mat('Pale oak',(.55,.42,.28),.5,(5,70,4))
walnut=mat('Ribbed walnut',(.30,.17,.08),.45,(4,4,60))
sofa=mat('Linen grey sofa',(.50,.51,.50),.95,(140,140,140))
pillow_white=mat('Linen white pillow',(.78,.77,.73),.95,(160,160,160))
pillow_grey=mat('Linen grey pillow',(.42,.43,.43),.95,(150,150,150))
pillow_dark=mat('Linen charcoal pillow',(.13,.14,.14),.95,(150,150,150))
throw=mat('Linen white throw',(.80,.80,.78),.95,(220,220,220))
rug=mat('Woven grey rug',(.55,.55,.53),1,(240,240,100))
knit=mat('Chunky knit cotton',(.60,.54,.43),1,(380,380,380))
curtain=mat('Linen sheer curtain',(.72,.73,.74),.9,(90,90,90))
curtain_blue=mat('Linen blue-grey curtain',(.36,.43,.52),.9,(90,90,90))
paper=mat('Poster paper',(.80,.80,.78),1)
print_a=mat('Print aircraft',(.55,.58,.60),1,(3,3,6)); print_b=mat('Print tower',(.70,.71,.71),1,(3,3,6))
leaf=mat('Leaves',(.10,.20,.08)); snake=mat('Snake plant leaf',(.15,.26,.10),.6,(3,3,40))
pot_blue=mat('Blue glazed pot',(.12,.25,.50),.3); pot_dark=mat('Charcoal pot',(.07,.07,.07),.5)
ceramic=mat('White ceramic',(.80,.79,.76),.35); brass=mat('Brushed brass',(.45,.33,.15),.35)
lampshade=mat('Lampshade linen',(.85,.75,.58),.9,(80,80,50))
sp=lampshade.node_tree.nodes.get('Principled BSDF');sp.inputs['Emission Color'].default_value=(1,.72,.40,1);sp.inputs['Emission Strength'].default_value=.6

# ---- architecture: 4.2 x 4.8 x 2.7 m. Window opening on the left wall from y .6 to 2.2.
W,D,Hc=4.2,4.8,2.7
for i in range(15):
 for j in range(4):
  cube('Oak floor plank',(-W/2+(i+.5)*.28,-D/2+(j+.5)*1.2,-.035),(.278,1.198,.07),oak,.002)
cube('Wall right',(2.18,0,Hc/2),(.16,D+.16,Hc),wall)
cube('Wall back',(0,2.48,Hc/2),(W+.32,.16,Hc),wall)
cube('Wall left front',(-2.18,-.98,Hc/2),(.16,3.16+.16,Hc),wall)
cube('Wall left back corner',(-2.18,2.36,Hc/2),(.16,.32,Hc),wall)
cube('Wall below window',(-2.18,1.4,.075),(.16,1.6,.15),wall)
cube('Wall above window',(-2.18,1.4,2.6),(.16,1.6,.2),wall)
cube('Wall front left',(-.6,-2.48,Hc/2),(3.32,.16,Hc),wall)
cube('Wall front right',(2.13,-2.48,Hc/2),(.26,.16,Hc),wall)
cube('Wall over doorway',(1.5,-2.48,2.4),(1.0,.16,.6),wall)
cube('Ceiling',(0,0,Hc+.06),(W+.32,D+.32,.12),wall)
for x in [-2.08,2.08]:cube('Skirting',(x,-.9 if x<0 else 0,.06),(.03,3.0 if x<0 else D,.12),trim,.003)
cube('Back skirting',(0,2.385,.06),(W,.03,.12),trim,.003)
# Window frame, mullion and bright exterior.
for y in [.6,2.2]:cube('Window jamb',(-2.12,y,1.3),(.08,.06,2.3),trim,.003)
for z in [.15,2.45]:cube('Window head and sill',(-2.12,1.4,z),(.08,1.66,.06),trim,.003)
cube('Window mullion',(-2.14,1.4,1.3),(.04,.04,2.3),trim,.002)
sky=mat('Bright exterior',(.85,.90,.95)); ep=sky.node_tree.nodes.get('Principled BSDF');ep.inputs['Emission Color'].default_value=(.85,.90,.95,1);ep.inputs['Emission Strength'].default_value=1.4
cube('Exterior daylight',(-2.34,1.4,1.3),(.02,1.7,2.4),sky,0)
# Curtains: a gathered blue-grey panel at the back of the window, a sheer at the front.
cube('Curtain rod',(-1.98,1.35,2.52),(.025,2.3,.025),brass,.004)
cloth_panel('Gathered curtain',-1.96,1.85,2.32,.02,2.5,5,.035,curtain_blue)
cloth_panel('Sheer curtain',-1.96,.45,.95,.02,2.5,4,.03,curtain)

# ---- sofa against the back wall
SX=.25
for x in [SX-1.0,SX+1.0]:
 for y in [1.62,2.30]:cylinder('Sofa oak foot',(x,y,.06),.03,.12,oak,.022)
cushion('Sofa base',(SX,1.98,.27),(2.25,.86,.26),sofa)
for dx in [-.51,.51]:cushion('Seat cushion',(SX+dx,1.93,.47),(1.0,.72,.16),sofa)
cushion('Sofa back',(SX,2.30,.70),(2.25,.22,.50),sofa)
for dx in [-1.18,1.18]:cushion('Sofa arm',(SX+dx,1.98,.50),(.24,.86,.38),sofa)
for x,ma,r in [(-.65,pillow_white,.12),(-.35,pillow_grey,-.05),(.70,pillow_grey,.10),(1.05,pillow_dark,-.15)]:
 o=cushion('Loose sofa pillow',(x,2.13,.74),(.46,.16,.44),ma);o.rotation_euler=(.22,0,r)
cushion('Throw on seat',(.80,1.88,.57),(.85,.70,.04),throw)
cushion('Throw drape',(.80,1.52,.38),(.85,.04,.36),throw)
# Two framed posters above the sofa.
for x,z,w,h,ma in [(-.35,1.50,.56,.76,print_a),(.48,1.53,.60,.82,print_b)]:
 cube('Poster frame',(x,2.385,z),(w,.03,h),oak,.004)
 cube('Poster mat',(x,2.368,z),(w-.06,.006,h-.06),paper,0)
 cube('Poster print',(x,2.363,z+.02),(w-.20,.004,h-.26),ma,0)

# ---- floor lamp left of the sofa (static; its warm light is baked)
cylinder('Floor lamp base',(-1.35,2.15,.015),.14,.03,brass)
rod('Floor lamp pole',(-1.35,2.15,.03),(-1.35,2.15,1.40),.012,brass)
cylinder('Floor lamp shade',(-1.35,2.15,1.55),.17,.34,lampshade,.15)

# ---- plants
cube('Plant stool',(-1.78,1.55,.30),(.30,.30,.03),trim,.004)
for dx in [-.11,.11]:
 for dy in [-.11,.11]:rod('Stool leg',(-1.78+dx,1.55+dy,0),(-1.78+dx,1.55+dy,.29),.012,oak)
cylinder('Blue pot',(-1.78,1.55,.40),.09,.17,pot_blue,.11)
for i in range(18):
 a=random.random()*math.tau; h=random.uniform(.18,.38); end=(-1.78+math.cos(a)*.16,1.55+math.sin(a)*.16,.48+h)
 rod('Stem',(-1.78,1.55,.47),end,.003,leaf)
 ellipsoid('Leaf',end,(.05,.025,.006),leaf,(.6,a,a),10,6)
cylinder('Snake plant pot',(1.85,2.12,.20),.17,.40,pot_dark,.14)
for i in range(14):
 a=i/14*math.tau+random.uniform(-.2,.2); lean=random.uniform(.05,.28); h=random.uniform(.55,1.0)
 base=Vector((1.85+math.cos(a)*.06,2.12+math.sin(a)*.06,.40))
 ellipsoid('Snake leaf',base+Vector((math.cos(a)*lean*h*.5,math.sin(a)*lean*h*.5,h/2)),(.035,.006,h/2),snake,(math.sin(a)*lean,-math.cos(a)*lean,a),12,8)

# ---- rug, coffee table, side table, pouf
cube('Woven area rug',(.05,.95,.01),(3.0,2.6,.02),rug,.02)
CT=(-.15,.95)   # ribbed walnut drum coffee table, top at z .42
cylinder('Coffee table body',(CT[0],CT[1],.20),.36,.40,walnut,.45)
for k in range(13):
 z=.02+k*.03; r=.36+(.45-.36)*(z/.40)
 bpy.ops.mesh.primitive_torus_add(major_radius=r,minor_radius=.012,major_segments=64,minor_segments=8,location=(CT[0],CT[1],z));o=bpy.context.object;o.name='Coffee table rib';o.data.materials.append(walnut)
cylinder('Coffee table top',(CT[0],CT[1],.41),.45,.02,walnut)
cylinder('Tray',(-.38,1.08,.428),.14,.016,ceramic)
cylinder('Succulent pot',(-.38,1.08,.47),.045,.07,ceramic,.04)
for i in range(9):
 a=i/9*math.tau; ellipsoid('Succulent leaf',(-.38+math.cos(a)*.03,1.08+math.sin(a)*.03,.525),(.03,.015,.012),leaf,(0,.5,a),8,5)
ST=(-1.0,.95)    # hourglass walnut side table, top at z .53
cylinder('Side table lower',(ST[0],ST[1],.13),.24,.26,walnut,.16)
cylinder('Side table upper',(ST[0],ST[1],.39),.16,.26,walnut,.24)
for k in range(17):
 z=.02+k*.03; r=.16+.08*abs(z-.26)/.26
 bpy.ops.mesh.primitive_torus_add(major_radius=r,minor_radius=.008,major_segments=48,minor_segments=6,location=(ST[0],ST[1],z));o=bpy.context.object;o.name='Side table rib';o.data.materials.append(walnut)
cylinder('Side table top',(ST[0],ST[1],.515),.25,.03,walnut)
ellipsoid('Knitted pouf',(.95,.38,.19),(.34,.34,.19),knit,(0,0,0),32,16)

# ---- lights
def area(name,pos,target,power,color,size):
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.color=color;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=pos;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area('Window daylight',(-2.30,1.4,1.4),(1,1.2,0),260,(.88,.92,1),1.8)
area('Interior bounce',(0,-.5,2.6),(0,.8,0),45,(1,.95,.88),3)
area('Floor lamp glow',(-1.35,2.15,1.50),(-1.35,2.15,0),18,(1,.75,.45),.25)

# ---- reference camera matching the photo (wide lens, ~1 m high, slightly down and to the left)
bpy.ops.object.camera_add(location=(.35,-1.75,1.05));camera=bpy.context.object
camera.rotation_euler=(Vector((-.30,2.4,.70))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=22;scene.camera=camera
scene.render.resolution_x=1000;scene.render.resolution_y=1500;scene.render.resolution_percentage=100
# Preserve each object's procedural coordinates when meshes are joined for the atlas.
# Blender Generated coordinates otherwise change to the combined room bounds.
for obj in scene.objects:
 if obj.type!='MESH':continue
 coords=[v.co for v in obj.data.vertices]
 low=Vector(tuple(min(v[i] for v in coords) for i in range(3)))
 high=Vector(tuple(max(v[i] for v in coords) for i in range(3)))
 attr=obj.data.attributes.new('RoomGenerated','FLOAT_VECTOR','POINT')
 for v,item in zip(coords,attr.data):item.vector=tuple((v[i]-low[i])/max(high[i]-low[i],.000001) for i in range(3))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT,'tools/room/LivingRoomSofa.blend'))
scene.render.filepath=os.path.join(ROOT,'docs/living-room-sofa-blender.png');bpy.ops.render.render(write_still=True)
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
scene.render.filepath=os.path.join(ROOT,'docs/living-room-sofa-baked-blender.png');bpy.ops.render.render(write_still=True)
print('ROOM_EXPORT_COMPLETE')
