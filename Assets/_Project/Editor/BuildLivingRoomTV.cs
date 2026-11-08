using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Interactables;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Teleportation;

namespace RoomVR.EditorTools
{
    /// <summary>
    /// Generates LivingRoomTV.unity from the Blender bake of tools/room/build_living_room_tv.py,
    /// the same way BuildRenderedRoom does for room 1. Room 4.6 x 5.0 x 3.0 m, centred on the origin.
    /// Pickables: book on the tiered coffee table, mug on the brass side table, lamp on the left end of the TV cabinet.
    /// </summary>
    public static class BuildLivingRoomTV
    {
        public const string ScenePath = "Assets/_Project/Scenes/LivingRoomTV.unity";
        const string Models = "Assets/_Project/Models/LivingRoomTV/";
        const string Samples = "Assets/Samples/XR Interaction Toolkit/3.7.0/";
        const string Pickables = "Assets/_Project/Prefabs/Pickables/";

        // Static surfaces (must match build_living_room_tv.py): x, top height, z.
        public static readonly Vector3 CoffeeTable = new Vector3(-.30f, .42f, .10f);  // square 1.0 x 1.0 m
        public static readonly Vector3 SideTable = new Vector3(.10f, .55f, 1.60f); public const float SideTableRadius = .22f;
        public static readonly Vector3 Cabinet = new Vector3(.65f, .55f, 2.24f);      // 2.2 x 0.45 m

        static GameObject Instantiate(string path)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (!prefab) throw new InvalidOperationException("Missing asset: " + path);
            return (GameObject)PrefabUtility.InstantiatePrefab(prefab);
        }

        [MenuItem("RoomVR/Build Living Room (TV)")]
        public static void Run()
        {
            AssetDatabase.Refresh();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            foreach (var name in new[] { "Architecture", "Furnishings" })
            {
                var texturePath = Models + name + ".png";
                var importer = (TextureImporter)AssetImporter.GetAtPath(texturePath);
                if (importer == null) throw new InvalidOperationException("Run the Blender export first: tools/room/build_living_room_tv.py");
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
                material.SetColor("_BaseColor", Color.white);   // wall tint: multiplies the baked texture
                var root = Instantiate(Models + name + ".fbx");
                root.name = name + " — Blender baked radiance";
                root.transform.rotation = Quaternion.Euler(0, 180, 0);   // same FBX axis fix as room 1
                foreach (var renderer in root.GetComponentsInChildren<MeshRenderer>())
                {
                    renderer.sharedMaterial = material;
                    renderer.shadowCastingMode = ShadowCastingMode.Off;
                    renderer.receiveShadows = false;
                }
            }

            new GameObject("XR Interaction Manager").AddComponent<XRInteractionManager>();
            var rig = Instantiate(Samples + "Starter Assets/Prefabs/XR Origin (XR Rig).prefab");
            rig.transform.position = new Vector3(.55f, 0, -1.9f);       // front of the room, facing the TV wall
            rig.transform.rotation = Quaternion.Euler(0, -8, 0);
            Instantiate(Samples + "XR Device Simulator/XR Device Simulator.prefab");

            // Collision proxies (metres, Unity axes), independent of the visual meshes.
            var colliders = new GameObject("Room collision and walkable floor").transform;
            Box(colliders, "Floor", new Vector3(0, -.05f, 0), new Vector3(4.6f, .1f, 5.0f), true);
            Box(colliders, "Left wall", new Vector3(-2.38f, 1.5f, 0), new Vector3(.16f, 3.0f, 5.16f));
            Box(colliders, "Right wall", new Vector3(2.38f, 1.5f, 0), new Vector3(.16f, 3.0f, 5.16f));
            Box(colliders, "TV wall, window and niche", new Vector3(0, 1.5f, 2.58f), new Vector3(4.92f, 3.0f, .16f));
            Box(colliders, "Front wall", new Vector3(0, 1.5f, -2.58f), new Vector3(4.92f, 3.0f, .16f));
            Box(colliders, "TV cabinet", new Vector3(Cabinet.x, Cabinet.y / 2, Cabinet.z), new Vector3(2.2f, Cabinet.y, .45f));
            Box(colliders, "Tiered coffee table", new Vector3(CoffeeTable.x, CoffeeTable.y / 2, CoffeeTable.z), new Vector3(1.0f, CoffeeTable.y, 1.0f));
            Box(colliders, "Swivel armchair", new Vector3(1.40f, .45f, .95f), new Vector3(.9f, .9f, .9f));
            Box(colliders, "Accent chair", new Vector3(-.55f, .45f, 1.55f), new Vector3(.6f, .9f, .56f));
            Box(colliders, "Low table with branches", new Vector3(-1.75f, .19f, .55f), new Vector3(.9f, .38f, .8f));
            RoundTable(colliders, "Brass side table", new Vector3(SideTable.x, 0, SideTable.z), SideTableRadius, SideTable.y);

            // Pickables. Each instance is fitted to its real height and dropped 5 mm above its surface.
            var mug = Pickable("mug.prefab", "Mug (pickable)", .10f, new Vector3(.15f, SideTable.y, 1.55f), 0, fitCollider: true);
            var ceramic = AssetDatabase.LoadAssetAtPath<Material>("Assets/_Project/Models/RenderedRoom/MugCeramic.mat");
            if (ceramic) foreach (var r in mug.GetComponentsInChildren<Renderer>()) r.sharedMaterials = Enumerable.Repeat(ceramic, r.sharedMaterials.Length).ToArray();
            Pickable("book.prefab", "Book (pickable)", 0, new Vector3(-.05f, CoffeeTable.y, -.12f), -15, fitCollider: false);
            // Left end of the cabinet: visible from the start view (on the right end it hid behind the armchair).
            // At x -0.25 the 0.40 m shade stays 7 cm in front of the TV panel's plane and within the cabinet top.
            Pickable("lamp.prefab", "Table lamp (pickable)", .57f, new Vector3(-.25f, Cabinet.y, Cabinet.z), 0, fitCollider: false);

            // Real-time light only for the movable pickables; the room's light is baked.
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(.74f, .74f, .74f);
            RenderSettings.ambientEquatorColor = new Color(.62f, .60f, .56f);
            RenderSettings.ambientGroundColor = new Color(.36f, .34f, .31f);
            var light = new GameObject("Window light for movable pickables").AddComponent<Light>();
            light.type = LightType.Directional; light.color = new Color(.96f, .97f, 1f); light.intensity = .8f;
            light.transform.rotation = Quaternion.Euler(40, 160, 0); light.shadows = LightShadows.Soft;  // from the window on the TV wall

            var camera = new GameObject("Reference preview camera (disabled in play)").AddComponent<Camera>();
            camera.enabled = false; camera.transform.position = new Vector3(.55f, 1.10f, -1.75f);
            camera.transform.LookAt(new Vector3(-.10f, 1.05f, 2.5f)); camera.fieldOfView = 84f;
            camera.nearClipPlane = .03f; camera.farClipPlane = 30;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(.88f, .88f, .87f);
            foreach (var c in rig.GetComponentsInChildren<Camera>()) { c.nearClipPlane = .03f; c.farClipPlane = 30; c.clearFlags = CameraClearFlags.SolidColor; c.backgroundColor = camera.backgroundColor; }

            EditorSceneManager.SaveScene(scene, ScenePath);
            if (EditorBuildSettings.scenes.All(s => s.path != ScenePath))   // append; room 1 stays first
                EditorBuildSettings.scenes = EditorBuildSettings.scenes.Concat(new[] { new EditorBuildSettingsScene(ScenePath, true) }).ToArray();
            AssetDatabase.SaveAssets(); Capture(camera, "docs/living-room-tv-unity.png");
            var meshes = scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<MeshFilter>()).Select(f => f.sharedMesh).Where(m => m);
            Debug.Log("ROOM_MESH_TRIANGLES=" + meshes.Sum(m => m.triangles.Length / 3));
            Debug.Log("LIVING_ROOM_TV_COMPLETE: book, mug and lamp pickables; authored collision, XR rig and teleport floor.");
        }

        /// <summary>Instantiate a pickable, fit it to `height` (0 = keep prefab size), rotate, and rest it on `surface` (x, top y, z).</summary>
        static GameObject Pickable(string prefab, string name, float height, Vector3 surface, float yaw, bool fitCollider)
        {
            var go = Instantiate(Pickables + prefab);
            go.name = name; go.transform.position = Vector3.zero; go.transform.rotation = Quaternion.Euler(0, yaw, 0);
            var b = BoundsOf(go);
            if (height > 0) { go.transform.localScale *= height / b.size.y; b = BoundsOf(go); }
            go.transform.position += new Vector3(surface.x - b.center.x, surface.y + .005f - b.min.y, surface.z - b.center.z);
            if (fitCollider)
            {
                b = BoundsOf(go);
                var box = go.GetComponent<BoxCollider>();
                box.center = go.transform.InverseTransformPoint(b.center);
                var s = go.transform.lossyScale;
                box.size = new Vector3(b.size.x / s.x, b.size.y / s.y, b.size.z / s.z);
            }
            var body = go.GetComponent<Rigidbody>();
            body.interpolation = RigidbodyInterpolation.Interpolate;
            body.collisionDetectionMode = CollisionDetectionMode.ContinuousDynamic;
            go.GetComponent<XRGrabInteractable>().useDynamicAttach = true;
            return go;
        }

        static Bounds BoundsOf(GameObject root)
        {
            var renderers = root.GetComponentsInChildren<Renderer>(); var b = renderers[0].bounds;
            foreach (var r in renderers.Skip(1)) b.Encapsulate(r.bounds); return b;
        }

        static void Box(Transform parent, string name, Vector3 position, Vector3 size, bool teleport = false)
        {
            var go = new GameObject(name); go.transform.SetParent(parent); go.transform.position = position;
            go.AddComponent<BoxCollider>().size = size;
            if (teleport) go.AddComponent<TeleportationArea>().interactionLayers = 1 << 31;
        }

        static void RoundTable(Transform parent, string name, Vector3 center, float radius, float height)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cylinder); go.name = name;
            go.transform.SetParent(parent); go.transform.position = center + Vector3.up * (height / 2);
            go.transform.localScale = new Vector3(radius * 2, height / 2, radius * 2);
            var mesh = go.GetComponent<MeshFilter>().sharedMesh;
            UnityEngine.Object.DestroyImmediate(go.GetComponent<Collider>());
            go.AddComponent<MeshCollider>().sharedMesh = mesh;
            UnityEngine.Object.DestroyImmediate(go.GetComponent<MeshRenderer>());
            UnityEngine.Object.DestroyImmediate(go.GetComponent<MeshFilter>());
        }

        static void Capture(Camera camera, string path)
        {
            const int w = 1000, h = 1200;
            var rt = new RenderTexture(w, h, 24) { antiAliasing = 4 }; camera.targetTexture = rt; camera.Render();
            RenderTexture.active = rt; var image = new Texture2D(w, h, TextureFormat.RGB24, false);
            image.ReadPixels(new Rect(0, 0, w, h), 0, 0); image.Apply(); Directory.CreateDirectory("docs");
            File.WriteAllBytes(path, image.EncodeToPNG());
            camera.targetTexture = null; RenderTexture.active = null; UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(image);
        }
    }
}
