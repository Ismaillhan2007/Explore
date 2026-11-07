using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Interactables;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Teleportation;

namespace RoomVR.EditorTools
{
    public static class BuildRenderedRoom
    {
        public const string ScenePath = "Assets/_Project/Scenes/RenderedRoom.unity";
        const string Models = "Assets/_Project/Models/RenderedRoom/";
        const string Samples = "Assets/Samples/XR Interaction Toolkit/3.7.0/";
        static GameObject Instantiate(string path)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (!prefab) throw new InvalidOperationException("Missing asset: " + path);
            return (GameObject)PrefabUtility.InstantiatePrefab(prefab);
        }
        [MenuItem("RoomVR/Build Rendered Room")]
        public static void Run()
        {
            AssetDatabase.Refresh();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            foreach (var name in new[] { "Architecture", "Furnishings" })
            {
                var texturePath = Models + name + ".png";
                var importer = (TextureImporter)AssetImporter.GetAtPath(texturePath);
                if (importer == null) throw new InvalidOperationException("Run Blender room export first");
                importer.maxTextureSize = name == "Furnishings" ? 4096 : 2048;
                importer.textureCompression = TextureImporterCompression.CompressedHQ;
                importer.mipmapEnabled = true; importer.anisoLevel = 4; importer.SaveAndReimport();
                var modelImporter = (ModelImporter)AssetImporter.GetAtPath(Models + name + ".fbx");
                modelImporter.materialImportMode = ModelImporterMaterialImportMode.None;
                modelImporter.SaveAndReimport();
                var materialPath = Models + name + ".mat";
                var material = AssetDatabase.LoadAssetAtPath<Material>(materialPath);
                if (!material) { material = new Material(Shader.Find("Universal Render Pipeline/Unlit")); AssetDatabase.CreateAsset(material, materialPath); }
                material.SetTexture("_BaseMap", AssetDatabase.LoadAssetAtPath<Texture2D>(texturePath));
                material.SetColor("_BaseColor", Color.white);
                var root = Instantiate(Models + name + ".fbx");
                root.name = name + " — Blender baked radiance";
                // FBX right-handed export imports with X/Z reversed in Unity.
                root.transform.rotation = Quaternion.Euler(0,180,0);
                foreach (var renderer in root.GetComponentsInChildren<MeshRenderer>())
                {
                    renderer.sharedMaterial = material;
                    renderer.shadowCastingMode = ShadowCastingMode.Off;
                    renderer.receiveShadows = false;
                }
            }
            new GameObject("XR Interaction Manager").AddComponent<XRInteractionManager>();
            var rig = Instantiate(Samples + "Starter Assets/Prefabs/XR Origin (XR Rig).prefab");
            rig.transform.position = new Vector3(1.25f, 0, -2.25f);
            rig.transform.rotation = Quaternion.Euler(0, -22, 0);
            Instantiate(Samples + "XR Device Simulator/XR Device Simulator.prefab");
            // Collision proxies use metre dimensions, independent of detailed visual meshes.
            var colliders = new GameObject("Room collision and walkable floor").transform;
            Box(colliders, "Floor", new Vector3(0,-.05f,0), new Vector3(4.2f,.1f,5.6f), true);
            Box(colliders, "Left wall", new Vector3(-2.18f,1.75f,0), new Vector3(.16f,3.5f,5.76f));
            Box(colliders, "Right wall", new Vector3(2.18f,1.75f,0), new Vector3(.16f,3.5f,5.76f));
            Box(colliders, "Back wall and window", new Vector3(0,1.75f,2.88f), new Vector3(4.5f,3.5f,.16f));
            Box(colliders, "Entrance boundary", new Vector3(0,1.75f,-2.88f), new Vector3(4.5f,3.5f,.16f));
            Box(colliders, "Bed", new Vector3(-1.28f,.33f,-.1f), new Vector3(1.55f,.66f,2.4f));
            Box(colliders, "Sofa", new Vector3(.98f,.55f,2.12f), new Vector3(1.92f,1.1f,1.0f));
            Box(colliders, "Bookcase", new Vector3(1.66f,1.04f,1.24f), new Vector3(.92f,2.08f,.44f));
            Box(colliders, "Basket", new Vector3(1.78f,.17f,.57f), new Vector3(.46f,.34f,.46f));
            Box(colliders, "Desk", new Vector3(1.76f,.4f,-.69f), new Vector3(.68f,.80f,1.55f));
            Box(colliders, "Chair", new Vector3(1.15f,.48f,-.61f), new Vector3(.55f,.96f,.55f));
            RoundTable(colliders, "Coffee table", new Vector3(.65f,0,.78f), .39f,.49f);
            RoundTable(colliders, "Bedside table", new Vector3(-.53f,0,1.85f), .32f,.59f);
            var mug = Instantiate("Assets/_Project/Prefabs/Pickables/mug.prefab");
            mug.name = "Mug — only pickable"; mug.transform.position = Vector3.zero;
            mug.transform.rotation = Quaternion.identity;
            // Preserve the prefab/model, fit the scene instance to a real 10 cm mug.
            var bounds = BoundsOf(mug);
            mug.transform.localScale *= .10f / bounds.size.y;
            bounds = BoundsOf(mug);
            mug.transform.position += new Vector3(.80f-bounds.center.x, .495f-bounds.min.y, .68f-bounds.center.z);
            bounds = BoundsOf(mug);
            var box = mug.GetComponent<BoxCollider>();
            box.center = mug.transform.InverseTransformPoint(bounds.center);
            box.size = new Vector3(bounds.size.x / mug.transform.lossyScale.x, bounds.size.y / mug.transform.lossyScale.y, bounds.size.z / mug.transform.lossyScale.z);
            var body = mug.GetComponent<Rigidbody>(); body.interpolation = RigidbodyInterpolation.Interpolate;
            body.collisionDetectionMode = CollisionDetectionMode.ContinuousDynamic;
            mug.GetComponent<XRGrabInteractable>().useDynamicAttach = true;
            var ceramicPath = Models + "MugCeramic.mat";
            var ceramic = AssetDatabase.LoadAssetAtPath<Material>(ceramicPath);
            if (!ceramic) { ceramic = new Material(Shader.Find("Universal Render Pipeline/Lit")); AssetDatabase.CreateAsset(ceramic,ceramicPath); }
            ceramic.SetColor("_BaseColor",new Color(.76f,.73f,.63f)); ceramic.SetFloat("_Smoothness",.36f);
            foreach(var renderer in mug.GetComponentsInChildren<Renderer>()) renderer.sharedMaterials = Enumerable.Repeat(ceramic,renderer.sharedMaterials.Length).ToArray();
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(.65f,.70f,.76f);
            RenderSettings.ambientEquatorColor = new Color(.52f,.48f,.38f);
            RenderSettings.ambientGroundColor = new Color(.28f,.22f,.16f);
            var light = new GameObject("Window light for movable mug").AddComponent<Light>();
            light.type = LightType.Directional; light.color = new Color(1,.94f,.84f); light.intensity = .8f;
            light.transform.rotation = Quaternion.Euler(48,-155,0); light.shadows = LightShadows.Soft;
            // Static Blender shadows are in the atlas; the mug retains normal lit rendering.
            var camera = new GameObject("Reference preview camera (disabled in play)").AddComponent<Camera>();
            camera.enabled = false; camera.transform.position = new Vector3(.95f,1.85f,-2.62f);
            camera.transform.LookAt(new Vector3(-.12f,1.05f,.85f)); camera.fieldOfView=73;
            camera.nearClipPlane=.03f; camera.farClipPlane=30;
            camera.clearFlags=CameraClearFlags.SolidColor; camera.backgroundColor=new Color(.72f,.76f,.78f);
            foreach (var c in rig.GetComponentsInChildren<Camera>()) { c.nearClipPlane=.03f; c.farClipPlane=30; c.clearFlags=CameraClearFlags.SolidColor; c.backgroundColor=camera.backgroundColor; }
            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] {new EditorBuildSettingsScene(ScenePath,true)}.Concat(EditorBuildSettings.scenes.Where(s=>s.path!=ScenePath)).ToArray();
            AssetDatabase.SaveAssets(); Capture(camera);
            var meshes = scene.GetRootGameObjects().SelectMany(r=>r.GetComponentsInChildren<MeshFilter>()).Select(f=>f.sharedMesh).Where(m=>m);
            Debug.Log("ROOM_MESH_TRIANGLES=" + meshes.Sum(m=>m.triangles.Length/3));
            Debug.Log("RENDERED_ROOM_COMPLETE: exactly one mug; authored collision, XR rig and teleport floor.");
        }
        static Bounds BoundsOf(GameObject root)
        {
            var renderers=root.GetComponentsInChildren<Renderer>(); var b=renderers[0].bounds;
            foreach(var r in renderers.Skip(1)) b.Encapsulate(r.bounds); return b;
        }
        static void Box(Transform parent,string name,Vector3 position,Vector3 size,bool teleport=false)
        {
            var go=new GameObject(name); go.transform.SetParent(parent); go.transform.position=position;
            go.AddComponent<BoxCollider>().size=size;
            if(teleport) go.AddComponent<TeleportationArea>().interactionLayers = 1 << 31;
        }
        static void RoundTable(Transform parent,string name,Vector3 center,float radius,float height)
        {
            var go=GameObject.CreatePrimitive(PrimitiveType.Cylinder); go.name=name;
            go.transform.SetParent(parent); go.transform.position=center+Vector3.up*(height/2);
            go.transform.localScale=new Vector3(radius*2,height/2,radius*2);
            var mesh=go.GetComponent<MeshFilter>().sharedMesh;
            UnityEngine.Object.DestroyImmediate(go.GetComponent<Collider>());
            go.AddComponent<MeshCollider>().sharedMesh=mesh;
            UnityEngine.Object.DestroyImmediate(go.GetComponent<MeshRenderer>());
            UnityEngine.Object.DestroyImmediate(go.GetComponent<MeshFilter>());
        }

        static void Capture(Camera camera)
        {
            var rt=new RenderTexture(1000,1100,24) { antiAliasing = 4 }; camera.targetTexture=rt; camera.Render();
            RenderTexture.active=rt;var image=new Texture2D(1000,1100,TextureFormat.RGB24,false);
            image.ReadPixels(new Rect(0,0,1000,1100),0,0);image.Apply(); Directory.CreateDirectory("docs");
            File.WriteAllBytes("docs/room-unity.png",image.EncodeToPNG());
            camera.targetTexture=null;RenderTexture.active=null;UnityEngine.Object.DestroyImmediate(rt);UnityEngine.Object.DestroyImmediate(image);
        }
    }
}
