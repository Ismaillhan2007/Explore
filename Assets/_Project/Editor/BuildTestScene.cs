using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace RoomVR.EditorTools
{
    // Run via: Unity -batchmode -executeMethod RoomVR.EditorTools.BuildTestScene.Run
    public static class BuildTestScene
    {
        const string Samples = "Assets/Samples/XR Interaction Toolkit/3.7.0";
        const string RigPrefab = Samples + "/Starter Assets/Prefabs/XR Origin (XR Rig).prefab";
        const string SimulatorPrefab = Samples + "/XR Device Simulator/XR Device Simulator.prefab";
        const string TeleportAreaPrefab = Samples + "/Starter Assets/DemoAssets/Prefabs/Teleport/Teleport Area.prefab";
        const string SettingsDir = "Assets/_Project/Settings";
        const string PickablePath = "Assets/_Project/Prefabs/Pickables/PickableCube.prefab";
        const string ScenePath = "Assets/_Project/Scenes/TestRoom.unity";

        public static void Run()
        {
            SetupUrp();
            CreatePickableCube();
            CreateScene();
            AssetDatabase.SaveAssets();
            Debug.Log("[BuildTestScene] done");
        }

        static void SetupUrp()
        {
            Directory.CreateDirectory(SettingsDir);
            const string pipelinePath = SettingsDir + "/URP-Quest.asset";
            var pipeline = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(pipelinePath);
            if (pipeline == null)
            {
                var renderer = ScriptableObject.CreateInstance<UniversalRendererData>();
                AssetDatabase.CreateAsset(renderer, SettingsDir + "/URP-Quest-Renderer.asset");
                pipeline = UniversalRenderPipelineAsset.Create(renderer);
                pipeline.supportsHDR = false;
                pipeline.msaaSampleCount = 4;
                AssetDatabase.CreateAsset(pipeline, pipelinePath);
            }
            GraphicsSettings.defaultRenderPipeline = pipeline;
            var current = QualitySettings.GetQualityLevel();
            for (int i = 0; i < QualitySettings.names.Length; i++)
            {
                QualitySettings.SetQualityLevel(i, false);
                QualitySettings.renderPipeline = pipeline;
            }
            QualitySettings.SetQualityLevel(current, false);
        }

        static void CreatePickableCube()
        {
            if (AssetDatabase.LoadAssetAtPath<GameObject>(PickablePath) != null) return;
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = "PickableCube";
            go.transform.localScale = Vector3.one * 0.2f;
            var rb = go.AddComponent<Rigidbody>();
            rb.mass = 0.5f;
            go.AddComponent<XRGrabInteractable>();
            PrefabUtility.SaveAsPrefabAsset(go, PickablePath);
            Object.DestroyImmediate(go);
        }

        static void CreateScene()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            var light = new GameObject("Directional Light").AddComponent<Light>();
            light.type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(50, -30, 0);

            var floorPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(TeleportAreaPrefab);
            var floor = (GameObject)PrefabUtility.InstantiatePrefab(floorPrefab);
            floor.name = "Floor (Teleport Area)";
            // Sample prefab is authored at y=-2; put its 0.25 m slab's top surface at y=0.
            floor.transform.position = new Vector3(0, -0.125f, 0);

            var rig = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(RigPrefab));
            rig.transform.position = new Vector3(0, 0, -1.5f);

            var sim = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(SimulatorPrefab));
            sim.name = "XR Device Simulator";

            var table = GameObject.CreatePrimitive(PrimitiveType.Cube);
            table.name = "Table";
            table.transform.position = new Vector3(0, 0.375f, 0.5f);
            table.transform.localScale = new Vector3(1.2f, 0.75f, 0.6f);

            var cubePrefab = AssetDatabase.LoadAssetAtPath<GameObject>(PickablePath);
            for (int i = 0; i < 3; i++)
            {
                var cube = (GameObject)PrefabUtility.InstantiatePrefab(cubePrefab);
                cube.transform.position = new Vector3(-0.35f + 0.35f * i, 0.9f, 0.5f);
            }

            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        }
    }
}
