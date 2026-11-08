using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace RoomVR.EditorTools
{
    /// <summary>
    /// CHECK TOOL for the photo pipeline: opens the room named in a scene JSON (pipeline/scenes/*.json),
    /// places the JSON's pickables with the same code as Play mode (RoomVR.PickableSceneLoader), renders the
    /// room's reference camera to a PNG and closes the scene WITHOUT saving.
    ///
    /// Batch: Unity -batchmode -quit -projectPath . -executeMethod RoomVR.EditorTools.PipelineScenePreview.Run
    ///        -sceneJson pipeline/debug/x/scene_x.json -out pipeline/debug/x/unity_preview.png
    /// Optional camera override (e.g. a photo camera solved by pipeline/steps/align_camera.py):
    ///        -cameraPos x,y,z -lookAt x,y,z -vfov 66.4 -size 505,607
    /// </summary>
    public static class PipelineScenePreview
    {
        public static void Run()
        {
            var args = Environment.GetCommandLineArgs();
            string Arg(string name) { var i = Array.IndexOf(args, name); return i >= 0 && i + 1 < args.Length ? args[i + 1] : null; }
            var json = Arg("-sceneJson") ?? throw new ArgumentException("missing -sceneJson");
            var output = Arg("-out") ?? Path.ChangeExtension(json, ".png");
            Preview(json, output, Arg("-cameraPos"), Arg("-lookAt"), Arg("-vfov"), Arg("-size"));
        }

        static Vector3 V3(string csv)
        {
            var p = csv.Split(',').Select(v => float.Parse(v, System.Globalization.CultureInfo.InvariantCulture)).ToArray();
            return new Vector3(p[0], p[1], p[2]);
        }

        public static void Preview(string sceneJsonPath, string outputPng, string cameraPos = null, string lookAt = null,
                                   string vfov = null, string size = null)
        {
            var data = PickableSceneLoader.Parse(File.ReadAllText(sceneJsonPath));
            var scenePath = "Assets/_Project/Scenes/" + data.room + ".unity";
            if (!File.Exists(scenePath)) throw new InvalidOperationException("No scene for room " + data.room);
            var scene = EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Single);
            var registry = AssetDatabase.LoadAssetAtPath<PickableRegistry>(PickableRegistryBuilder.AssetPath);
            if (!registry) { PickableRegistryBuilder.Run(); registry = AssetDatabase.LoadAssetAtPath<PickableRegistry>(PickableRegistryBuilder.AssetPath); }
            foreach (var go in PickableSceneLoader.Apply(scene, data, registry, true, p => (GameObject)PrefabUtility.InstantiatePrefab(p)))
                Debug.Log($"PIPELINE_PREVIEW: {go.name} at {go.transform.position} height {Bounds(go).size.y:F3}");
            var camera = scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<Camera>(true))
                              .First(c => c.name.StartsWith("Reference preview camera"));
            int w = 0, h = 0;
            if (cameraPos != null && lookAt != null)
            {
                camera.transform.position = V3(cameraPos);
                camera.transform.LookAt(V3(lookAt));
                if (vfov != null) camera.fieldOfView = float.Parse(vfov, System.Globalization.CultureInfo.InvariantCulture);
            }
            if (size != null) { var wh = size.Split(','); w = int.Parse(wh[0]); h = int.Parse(wh[1]); }
            Capture(camera, outputPng, w, h);
            Debug.Log("PIPELINE_PREVIEW_COMPLETE: " + outputPng);
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);   // discard, never save
        }

        static Bounds Bounds(GameObject root)
        {
            var rs = root.GetComponentsInChildren<Renderer>(); var b = rs[0].bounds;
            foreach (var r in rs.Skip(1)) b.Encapsulate(r.bounds); return b;
        }

        static void Capture(Camera camera, string path, int w = 0, int h = 0)
        {
            if (w <= 0 || h <= 0) { w = 1000; h = camera.fieldOfView > 80 ? 1200 : camera.fieldOfView > 75 ? 1500 : 1100; }   // builder sizes
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
