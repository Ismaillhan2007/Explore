using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace RoomVR
{
    [Serializable]
    public class PipelineSceneObject
    {
        public string label;
        public string model;
        public float[] position;
        public float rotationY;
        public float scale = 1f;
    }

    [Serializable]
    public class PipelineScene
    {
        public int version;
        public string room;
        public string wallColor;
        public PipelineSceneObject[] objects;
    }

    /// <summary>
    /// Places the pickables from a photo-pipeline scene JSON (pipeline/README.md section 4) into a room:
    /// removes the room's own pickables, spawns each listed prefab fitted to its real height x scale,
    /// rests it on its surface (y) and turns it by rotationY.
    ///
    /// In the Editor, the "Photo to VR" window sets a pending JSON before entering Play mode; it is applied
    /// automatically when the matching room scene loads. In a build, call LoadFromStreamingAssets.
    /// </summary>
    public static class PickableSceneLoader
    {
        /// <summary>SessionState key the Editor window uses to hand a JSON path to Play mode.</summary>
        public const string PendingKey = "RoomVR.PipelineSceneJson";
        const float DropHeight = .005f;   // spawn 5 mm above the surface and let physics settle it

        /// <summary>Path of a scene JSON to apply when its room loads (Play mode only). Set by the Editor window.</summary>
        public static string PendingJsonPath;

        public static event Action<Scene, List<GameObject>> Applied;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Init()
        {
#if UNITY_EDITOR
            if (string.IsNullOrEmpty(PendingJsonPath))
                PendingJsonPath = UnityEditor.SessionState.GetString(PendingKey, "");
#endif
            SceneManager.sceneLoaded -= OnSceneLoaded;
            SceneManager.sceneLoaded += OnSceneLoaded;
            TryApplyPending(SceneManager.GetActiveScene());
        }

        static void OnSceneLoaded(Scene scene, LoadSceneMode mode) => TryApplyPending(scene);

        static void TryApplyPending(Scene scene)
        {
            if (string.IsNullOrEmpty(PendingJsonPath) || !File.Exists(PendingJsonPath)) return;
            var data = Parse(File.ReadAllText(PendingJsonPath));
            if (data == null || data.room != scene.name) return;
            var placed = Apply(scene, data, PickableRegistry.Load());
            Debug.Log($"PickableSceneLoader: placed {placed.Count} pickables from {PendingJsonPath} into {scene.name}");
        }

        public static PipelineScene Parse(string json)
        {
            try { return JsonUtility.FromJson<PipelineScene>(json); }
            catch (Exception e) { Debug.LogError("PickableSceneLoader: bad scene JSON: " + e.Message); return null; }
        }

        /// <summary>Replace the scene's pickables with the JSON's. Returns the spawned objects.</summary>
        public static List<GameObject> Apply(Scene scene, PipelineScene data, PickableRegistry registry, bool removeExisting = true,
                                             Func<GameObject, GameObject> instantiate = null)
        {
            var placed = new List<GameObject>();
            if (registry == null) { Debug.LogError("PickableSceneLoader: no PickableRegistry (RoomVR → Update Pickable Registry)"); return placed; }
            if (removeExisting)
                foreach (var root in scene.GetRootGameObjects())
                    foreach (var g in root.GetComponentsInChildren<XRGrabInteractable>(true))
                        DestroyNow(g.gameObject);
            instantiate ??= UnityEngine.Object.Instantiate;
            foreach (var o in data.objects ?? Array.Empty<PipelineSceneObject>())
            {
                var entry = registry.Find(o.model);
                if (entry == null || entry.prefab == null) { Debug.LogWarning("PickableSceneLoader: no prefab for model " + o.model); continue; }
                if (o.position == null || o.position.Length != 3) { Debug.LogWarning("PickableSceneLoader: bad position for " + o.model); continue; }
                var go = instantiate(entry.prefab);
                SceneManager.MoveGameObjectToScene(go, scene);
                go.name = $"{o.label} (from photo pipeline)";
                Place(go, entry, o);
                placed.Add(go);
            }
            Applied?.Invoke(scene, placed);
            return placed;
        }

        /// <summary>Fit, turn and rest one instance on its surface, and set it up for smooth grabbing.</summary>
        public static void Place(GameObject go, PickableRegistry.Entry entry, PipelineSceneObject o)
        {
            go.transform.SetPositionAndRotation(Vector3.zero, Quaternion.Euler(0, o.rotationY, 0));
            var scale = o.scale > 0 ? o.scale : 1f;
            var b = BoundsOf(go);
            if (entry.fitToHeight && entry.heightM > 0 && b.size.y > 0) go.transform.localScale *= entry.heightM * scale / b.size.y;
            else go.transform.localScale *= scale;
            b = BoundsOf(go);
            var p = new Vector3(o.position[0], o.position[1], o.position[2]);
            go.transform.position += new Vector3(p.x - b.center.x, p.y + DropHeight - b.min.y, p.z - b.center.z);
            var body = go.GetComponent<Rigidbody>();
            if (body) { body.interpolation = RigidbodyInterpolation.Interpolate; body.collisionDetectionMode = CollisionDetectionMode.ContinuousDynamic; }
            var grab = go.GetComponent<XRGrabInteractable>();
            if (grab) grab.useDynamicAttach = true;
        }

        /// <summary>Headset builds: load Assets/StreamingAssets/pipeline/&lt;file&gt; and apply it to the active scene.</summary>
        public static IEnumerator LoadFromStreamingAssets(string fileName, Action<List<GameObject>> done = null)
        {
            var url = Path.Combine(Application.streamingAssetsPath, "pipeline", fileName);
            if (!url.Contains("://")) url = "file://" + url;
            using var req = UnityWebRequest.Get(url);
            yield return req.SendWebRequest();
            if (req.result != UnityWebRequest.Result.Success) { Debug.LogError("PickableSceneLoader: " + req.error + " " + url); yield break; }
            var data = Parse(req.downloadHandler.text);
            var scene = SceneManager.GetActiveScene();
            if (data == null || data.room != scene.name) { Debug.LogWarning($"PickableSceneLoader: {fileName} is for {data?.room}, not {scene.name}"); yield break; }
            done?.Invoke(Apply(scene, data, PickableRegistry.Load()));
        }

        static Bounds BoundsOf(GameObject root)
        {
            var rs = root.GetComponentsInChildren<Renderer>();
            if (rs.Length == 0) return new Bounds(root.transform.position, Vector3.zero);
            var b = rs[0].bounds;
            for (int i = 1; i < rs.Length; i++) b.Encapsulate(rs[i].bounds);
            return b;
        }

        static void DestroyNow(GameObject g)
        {
            if (Application.isPlaying) { g.SetActive(false); UnityEngine.Object.Destroy(g); }
            else UnityEngine.Object.DestroyImmediate(g);
        }
    }
}
