"""Original, deterministic Blender room. Run from repository root with Blender -b -t 8 -P tools/room/build_room.py.
Coordinates: X right, Y into room, Z up. Unity FBX conversion supplies Y up.
Baked Cycles radiance is shared with Unity, avoiding expensive runtime GI on Quest.
"""
import bpy, math, random, os
from mathutils import Vector
random.seed(71)
ROOT=os.getcwd(); OUT=os.path.join(ROOT,'Assets/_Project/Models/RenderedRoom'); os.makedirs(OUT,exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32
scene.cycles.use_denoising=True; scene.world.color=(.22,.25,.30)
scene.view_settings.view_transform='Standard'; scene.view_settings.look='Medium High Contrast' if False else 'None'

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
wood=mat('Honey oak',(.38,.22,.105),.48,(5,70,4)); wall=mat('Warm plaster',(.66,.63,.55),.95,(100,100,100)); linen=mat('Linen ivory',(.72,.69,.59),.95,(140,140,140)); rug=mat('Woven wool',(.53,.50,.42),1,(240,240,100)); green=mat('Sage linen',(.32,.35,.25),.95,(80,80,80)); trim=mat('Painted ivory',(.78,.77,.69)); dark=mat('Charcoal',(.065,.07,.063)); leaf=mat('Leaves',(.09,.18,.07)); ceramic=mat('Earthenware',(.65,.59,.45),.4); paper=mat('Book pages',(.72,.68,.56)); brass=mat('Aged brass',(.25,.17,.07),.3)
books=[mat('Book '+str(i),c) for i,c in enumerate([(.25,.29,.23),(.60,.55,.42),(.34,.28,.20),(.73,.71,.63),(.20,.25,.26)])]

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

def plant(x,y,z,s=1):
 cylinder('Plant pot',(x,y,z+.07*s),.085*s,.14*s,ceramic,.07*s)
 for i in range(15):
  a=random.random()*math.tau; h=random.uniform(.15,.34)*s; end=(x+math.cos(a)*.12*s,y+math.sin(a)*.12*s,z+h)
  rod('Stem',(x,y,z+.1*s),end,.002*s,leaf)
  bpy.ops.mesh.primitive_uv_sphere_add(segments=10,ring_count=6,radius=1,location=end); o=bpy.context.object; o.name='Leaf'; o.scale=(.035*s,.07*s,.012*s); o.rotation_euler=(.5,a,a); o.data.materials.append(leaf)

# Room 4.2 x 5.6 x 3.5 m, tall window on back wall.
for i in range(21):
 for j in range(5):
  cube('Oak floor plank',(-2.0+i*.2,-2.8+(j+.5)*1.12, -.035),(.198,1.118,.07),wood,.002)
cube('Wall left',(-2.18,0,1.75),(.16,5.76,3.5),wall)
cube('Wall right',(2.18,0,1.75),(.16,5.76,3.5),wall)
cube('Wall back left',(-1.85,2.88,1.75),(.66,.16,3.5),wall)
cube('Wall back right',(1.13,2.88,1.75),(2.1,.16,3.5),wall)
cube('Wall below window',(-.72,2.88,.35),(1.6,.16,.7),wall)
cube('Wall above window',(-.72,2.88,3.37),(1.6,.16,.26),wall)
cube('Wall front left',(-.7,-2.88,1.75),(2.96,.16,3.5),wall)
cube('Wall front right',(1.98,-2.88,1.75),(.4,.16,3.5),wall)
cube('Wall over doorway',(1.28,-2.88,2.88),(1.02,.16,1.24),wall)
cube('Ceiling',(0,0,3.56),(4.5,5.9,.12),wall)
for x in [-2.08,2.08]:cube('Skirting',(x,0,.07),(.045,5.6,.14),trim,.004)
cube('Back skirting',(0,2.77,.07),(4.2,.045,.14),trim,.004)
for x in [-1.54,.1]:cube('Window casing',(x,2.73,1.99),(.07,.10,2.63),trim,.004)
for z in [.7,1.95,3.28]:cube('Window rail',(-.72,2.72,z),(1.72,.12,.065),trim,.004)
cube('Window sill',(-.72,2.66,.71),(1.85,.27,.065),trim)
for i in range(54):
 o=cube('Venetian blind slat',(-.72,2.75,.77+i*.046),(1.58,.055,.013),trim,.004); o.rotation_euler.x=.22
for x in [-1.28,-.18]:cube('Blind cord',(x,2.70,2),(.008,.008,2.53),paper,.001)
# Rug and bed.
cube('Wool area rug',(-.1,.15,.012),(3.25,3.35,.024),rug,.025)
cube('Oak bed frame',(-1.28,-.1,.23),(1.48,2.36,.24),wood,.04)
for x in [-1.88,-.68]:
 for y in [-1.16,.96]:cube('Bed foot',(x,y,.12),(.09,.09,.24),wood)
cube('Headboard',(-1.28,1.09,.60),(1.5,.10,.60),wood,.04)
cushion('Mattress',(-1.28,-.1,.43),(1.43,2.28,.24),linen)
# Duvet with longitudinal wrinkles, draping down both sides and foot.
verts=[]; faces=[]; nx,ny=65,85
for j in range(ny):
 t=j/(ny-1); y=-1.38+t*2.18
 for i in range(nx):
  s=i/(nx-1); x=-1.28+(s-.5)*1.83
  drop=max(0,abs(s-.5)-.36)*2.6 + max(0,.10-t)*2.8
  z=.595-drop+.006*math.sin(s*95+t*15)+.004*math.sin(t*99+s*25)+.009*math.sin(s*44-t*18)
  verts.append((x,y,z))
for j in range(ny-1):
 for i in range(nx-1):
  a=j*nx+i;faces.append((a,a+1,a+nx+1,a+nx))
mesh=bpy.data.meshes.new('Duvet');mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new('Soft draped duvet',mesh);scene.collection.objects.link(o);o.data.materials.append(linen)
for p in mesh.polygons:p.use_smooth=True
for x in [-1.61,-.95]:
 o=cushion('Bed pillow',(x,.69,.67),(.63,.48,.18),linen);o.rotation_euler.z=random.uniform(-.10,.1)
# Sofa against back wall, facing entrance.
for x in [.33,1.63]:
 for y in [1.75,2.40]:cylinder('Sofa oak foot',(x,y,.12),.045,.24,wood)
cushion('Sofa base',(.98,2.08,.31),(1.64,.86,.30),linen)
for x in [.58,1.35]:cushion('Seat cushion',(x,1.99,.52),(.75,.73,.20),linen)
cushion('Sofa back',(.98,2.47,.77),(1.68,.22,.88),linen)
for x in [.13,1.83]:cushion('Sofa rolled arm',(x,2.09,.64),(.23,.93,.58),linen)
for x,ma in [(.45,green),(1.45,linen)]:
 o=cushion('Loose sofa pillow',(x,2.27,.86),(.47,.18,.46),ma);o.rotation_euler=(.18,.16,.07)
# Round tables.
def table(x,y,r,h):
 cylinder('Round oak tabletop',(x,y,h-.025),r,.05,wood)
 cylinder('Lower table shelf',(x,y,.16),r*.83,.035,wood)
 for a in [0,math.tau/3,math.tau*2/3]:
  xx=x+math.cos(a)*r*.77; yy=y+math.sin(a)*r*.77;rod('Table leg',(xx,yy,.025),(xx,yy,h-.045),.027,wood)
table(.65,.78,.39,.49);table(-.53,1.85,.32,.59)
# Lamp beside bed, and small plant.
cylinder('Lamp base',(-.58,1.89,.64),.105,.09,ceramic,.065);rod('Lamp stem',(-.58,1.89,.68),(-.58,1.89,.91),.016,brass)
shade=mat('Lampshade linen',(.82,.67,.43),.9,(80,80,50)); p=shade.node_tree.nodes.get('Principled BSDF');p.inputs['Emission Color'].default_value=(1,.66,.26,1);p.inputs['Emission Strength'].default_value=.25
cylinder('Lamp shade',(-.58,1.89,1.02),.20,.29,shade,.18);plant(-.34,1.81,.59,.6)
# Bookcase on right, angled toward the doorway.
case_before=set(scene.objects)
cube('Bookcase back',(2.03,1.89,1.02),(.06,.83,1.94),wood)
for y in [1.46,2.32]:cube('Bookcase side',(1.86,y,1.02),(.4,.045,1.94),wood)
for z in [.08,.47,.87,1.27,1.68,2.01]:cube('Bookcase shelf',(1.85,1.89,z),(.42,.88,.045),wood)
for z in [.10,.49,.89,1.29,1.70]:
 for k in range(9):
  h=random.uniform(.19,.30);cube('Book spine',(1.84,1.53+k*.077,z+h/2),(.25,.048,h),random.choice(books),.002)
plant(1.87,1.87,2.04,.9)
from mathutils import Matrix
pivot=Vector((1.86,1.89,0)); rot=Matrix.Rotation(math.radians(90),4,'Z')
for o in set(scene.objects)-case_before:
 o.location=pivot+rot.to_3x3()@(o.location-pivot)+Vector((-.20,-.65,0)); o.rotation_euler=(rot.to_3x3()@o.rotation_euler.to_matrix()).to_euler()
# Writing desk along right wall, chair.
cube('Desk top',(1.76,-.69,.77),(.65,1.55,.065),wood)
for y in [-1.36,-.01]:
 for x in [1.51,2.01]:cube('Desk leg',(x,y,.38),(.055,.055,.76),wood)
cube('Drawer pedestal',(1.77,-1.16,.37),(.55,.48,.69),wood)
for z in [.20,.43,.65]:
 cube('Drawer face',(1.475,-1.16,z),(.025,.43,.18),wood);cylinder('Drawer knob',(1.45,-1.16,z),.018,.025,brass).rotation_euler.y=math.pi/2
cushion('Chair seat',(1.15,-.61,.46),(.51,.50,.09),dark)
cushion('Chair back',(.91,-.61,.73),(.07,.51,.49),dark)
for x in [.93,1.35]:
 for y in [-.83,-.39]:rod('Chair leg',(x,y,.02),(x,y,.45),.025,wood)
cube('Closed notebook',(1.73,-.48,.82),(.32,.23,.025),paper)
cube('Laptop',(1.76,-.96,.817),(.37,.26,.018),dark)
cylinder('Task lamp base',(1.86,-.07,.83),.10,.025,brass);rod('Task lamp neck',(1.86,-.07,.85),(1.83,-.09,1.22),.012,brass);cylinder('Task lamp shade',(1.77,-.09,1.22),.085,.12,brass,.03).rotation_euler.y=-.6
# Woven basket and folded throw beside the desk.
wicker=mat('Wicker',(.33,.22,.11),.8,(65,65,8))
for j in range(17):
 bpy.ops.mesh.primitive_torus_add(major_radius=.21+j*.001,minor_radius=.008,major_segments=48,minor_segments=6,location=(1.78,.57,.035+j*.018));o=bpy.context.object;o.name='Woven basket coil';o.data.materials.append(wicker)
for i in range(32):
 a=i*math.tau/32;rod('Basket vertical weave',(1.78+math.cos(a)*.21,.57+math.sin(a)*.21,.03),(1.78+math.cos(a)*.226,.57+math.sin(a)*.226,.33),.006,wicker)
cushion('Blanket in basket',(1.78,.57,.25),(.34,.34,.16),dark)
# Framed muted landscape.
cube('Picture frame',(1.04,2.76,1.90),(.61,.045,.73),wood,.006)
art=mat('Quiet landscape',(.57,.53,.42),1,(2,2,6));cube('Landscape canvas',(1.04,2.729,1.90),(.55,.014,.67),art,.001)
# Books on coffee table, keeping the right-hand side free for the existing mug.
cube('Coffee table book',(.51,.82,.512),(.23,.18,.035),paper,.003)
cube('Book cover',(.51,.82,.532),(.24,.19,.006),books[0],.002)
# Soft daylight through opening, practical pool of warm lamp light.
def area(name,pos,target,power,color,size):
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.color=color;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=pos;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area('Window daylight',(-.72,2.95,2.1),(-.1,-1,0),180,(.80,.88,1),1.7)
area('Warm lamp',(-.58,1.89,1.0),(-1,1.7,.5),12,(1,.66,.32),.25)
area('Interior bounce',(0,-.8,3.25),(0,1,0),30,(1,.88,.70),3)
# Luminous overcast exterior behind the blind.
sky=mat('Overcast exterior',(.8,.87,1)); sp=sky.node_tree.nodes.get('Principled BSDF');sp.inputs['Emission Color'].default_value=(.8,.87,1,1);sp.inputs['Emission Strength'].default_value=.8
cube('Exterior daylight',(-.72,3.07,2),(1.8,.025,2.7),sky,0)
# Preserve each object's procedural coordinates when meshes are joined for the atlas.
# Blender Generated coordinates otherwise change to the combined room bounds.
for obj in scene.objects:
 if obj.type!='MESH':continue
 coords=[v.co for v in obj.data.vertices]
 low=Vector(tuple(min(v[i] for v in coords) for i in range(3)))
 high=Vector(tuple(max(v[i] for v in coords) for i in range(3)))
 attr=obj.data.attributes.new('RoomGenerated','FLOAT_VECTOR','POINT')
 for v,item in zip(coords,attr.data):item.vector=tuple((v[i]-low[i])/max(high[i]-low[i],.000001) for i in range(3))
# Render camera for reference checks.
bpy.ops.object.camera_add(location=(.95,-2.62,1.85));camera=bpy.context.object;camera.rotation_euler=(Vector((-.12,.85,1.05))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=22;scene.camera=camera
scene.render.resolution_x=1000;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT,'tools/room/RenderedRoom.blend'))
scene.render.filepath=os.path.join(ROOT,'docs/room-blender.png');bpy.ops.render.render(write_still=True)
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
scene.render.filepath=os.path.join(ROOT,'docs/room-baked-blender.png');bpy.ops.render.render(write_still=True)
print('ROOM_EXPORT_COMPLETE')
