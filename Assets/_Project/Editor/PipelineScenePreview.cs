using System;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace RoomVR.EditorTools
{
    /// <summary>
    /// CHECK TOOL for the photo pipeline, not the runtime loader: opens the room named in a scene JSON
    /// (pipeline/scenes/*.json), removes the room's own pickables, places the JSON's pickables the way
    /// the loader should (fit to height_m * scale, rest on y, turn by rotationY), renders the room's
    /// reference camera to a PNG and closes the scene WITHOUT saving.
    ///
    /// Batch: Unity -batchmode -quit -projectPath . -executeMethod RoomVR.EditorTools.PipelineScenePreview.Run
    ///        -sceneJson pipeline/debug/x/scene_x.json -out pipeline/debug/x/unity_preview.png
    /// </summary>
    public static class PipelineScenePreview
    {
        [Serializable] class SceneObject { public string label; public string model; public float[] position; public float rotationY; public float scale = 1; }
        [Serializable] class SceneJson { public int version; public string room; public SceneObject[] objects; }

        const string Pickables = "Assets/_Project/Prefabs/Pickables/";
        const string Library = "pipeline/model_library.json";

        public static void Run()
        {
            var args = Environment.GetCommandLineArgs();
            string Arg(string name) { var i = Array.IndexOf(args, name); return i >= 0 && i + 1 < args.Length ? args[i + 1] : null; }
            var json = Arg("-sceneJson") ?? throw new ArgumentException("missing -sceneJson");
            var output = Arg("-out") ?? Path.ChangeExtension(json, ".png");
            Preview(json, output);
        }

        public static void Preview(string sceneJsonPath, string outputPng)
        {
            var data = JsonUtility.FromJson<SceneJson>(File.ReadAllText(sceneJsonPath));
            var scenePath = "Assets/_Project/Scenes/" + data.room + ".unity";
            if (!File.Exists(scenePath)) throw new InvalidOperationException("No scene for room " + data.room);
            var scene = EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Single);
            foreach (var g in scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<XRGrabInteractable>(true)).ToArray())
                UnityEngine.Object.DestroyImmediate(g.gameObject);
            var library = File.ReadAllText(Library);
            foreach (var o in data.objects)
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Pickables + o.model + ".prefab");
                if (!prefab) { Debug.LogWarning("PIPELINE_PREVIEW: no prefab for model " + o.model); continue; }
                var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
                go.name = o.label + " (from scene JSON)";
                go.transform.SetPositionAndRotation(Vector3.zero, Quaternion.Euler(0, o.rotationY, 0));
                var b = Bounds(go);
                var height = HeightOf(library, o.model);
                if (height > 0 && o.model != "book") { go.transform.localScale *= height * o.scale / b.size.y; b = Bounds(go); }
                else if (o.scale > 0) { go.transform.localScale *= o.scale; b = Bounds(go); }
                var p = new Vector3(o.position[0], o.position[1], o.position[2]);
                go.transform.position += new Vector3(p.x - b.center.x, p.y + .005f - b.min.y, p.z - b.center.z);
                Debug.Log($"PIPELINE_PREVIEW: {o.model} at {go.transform.position} height {Bounds(go).size.y:F3}");
            }
            var camera = scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<Camera>(true))
                              .First(c => c.name.StartsWith("Reference preview camera"));
            Capture(camera, outputPng);
            Debug.Log("PIPELINE_PREVIEW_COMPLETE: " + outputPng);
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);   // discard, never save
        }

        static float HeightOf(string library, string model)
        {
            var m = Regex.Match(library, "\"" + Regex.Escape(model) + "\"\\s*:\\s*\\{[^}]*?\"height_m\"\\s*:\\s*([0-9.]+)");
            return m.Success ? float.Parse(m.Groups[1].Value, System.Globalization.CultureInfo.InvariantCulture) : 0;
        }

        static Bounds Bounds(GameObject root)
        {
            var rs = root.GetComponentsInChildren<Renderer>(); var b = rs[0].bounds;
            foreach (var r in rs.Skip(1)) b.Encapsulate(r.bounds); return b;
        }

        static void Capture(Camera camera, string path)
        {
            int w = 1000, h = camera.fieldOfView > 80 ? 1200 : camera.fieldOfView > 75 ? 1500 : 1100;   // same sizes as the room builders
            var rt = new RenderTexture(w, h, 24) { antiAliasing = 4 }; camera.targetTexture = rt; camera.Render();
            RenderTexture.active = rt; var image = new Texture2D(w, h, TextureFormat.RGB24, false);
            image.ReadPixels(new Rect(0, 0, w, h), 0, 0); image.Apply();
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            File.WriteAllBytes(path, image.EncodeToPNG());
            camera.targetTexture = null; RenderTexture.active = null;
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(image);
        }
    }
}
