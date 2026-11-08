using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace RoomVR.EditorTools
{
    /// <summary>
    /// RoomVR → Photo to VR: pick a photo (or one of the rooms' renders), run the photo pipeline
    /// (pipeline/run_pipeline.py in pipeline/.venv), see what it found, then open the room and press
    /// Play to walk around the generated result. Play mode places the pickables with PickableSceneLoader.
    /// </summary>
    public class PhotoToVRWindow : EditorWindow
    {
        static readonly (string room, string title, string render, string photo)[] Rooms =
        {
            ("LivingRoomSofa", "Living room (sofa)", "docs/living-room-sofa-unity.png", "pipeline/photos/living_room_sofa.jpg"),
            ("LivingRoomTV", "Living room (TV)", "docs/living-room-tv-unity.png", "pipeline/photos/living_room_tv.jpg"),
            ("RenderedRoom", "Room 1 (bedroom)", "docs/room-unity.png", null),
        };
        static readonly string[] Steps = { "[1 camera]", "[2 depth", "[3 room", "[4 detect", "[5 place", "[6 match", "[7 export" };
        static readonly string[] StepNames = { "Camera", "Depth", "Room shape", "Find pickables", "Place on tables", "Prefab + scale", "Write scene JSON" };

        string repo, photo = "";
        int roomIndex;
        bool isRender = true, offline = true;
        Process process;
        readonly ConcurrentQueue<string> incoming = new ConcurrentQueue<string>();
        string log = "", resultJson, status = "Pick an image, then Run.";
        int step = -1;
        Texture2D detections;
        PipelineScene result;
        Vector2 logScroll;

        [MenuItem("RoomVR/Photo to VR")]
        public static void Open() => GetWindow<PhotoToVRWindow>("Photo to VR").Show();

        // Forget the generated result when Play ends, so the normal Play button shows the room as built.
        [InitializeOnLoadMethod]
        static void ClearAfterPlay() => EditorApplication.playModeStateChanged += s =>
        {
            if (s == PlayModeStateChange.EnteredEditMode) { SessionState.EraseString(PickableSceneLoader.PendingKey); PickableSceneLoader.PendingJsonPath = null; }
        };

        void OnEnable()
        {
            repo = Directory.GetParent(Application.dataPath)!.FullName;
            EditorApplication.update += Pump;
        }

        void OnDisable() => EditorApplication.update -= Pump;

        string Python => Path.Combine(repo, "pipeline", ".venv", "bin", "python");
        string RoomName => Rooms[roomIndex].room;
        string RunName => "ui_" + RoomName;

        void OnGUI()
        {
            EditorGUILayout.LabelField("1. Image", EditorStyles.boldLabel);
            using (new EditorGUILayout.HorizontalScope())
            {
                photo = EditorGUILayout.TextField(photo);
                if (GUILayout.Button("Browse…", GUILayout.Width(80)))
                {
                    var p = EditorUtility.OpenFilePanel("Photo or render of one of our rooms", Path.Combine(repo, "pipeline", "photos"), "jpg,jpeg,png");
                    if (!string.IsNullOrEmpty(p)) { photo = p; isRender = p.Replace('\\', '/').Contains("/docs/"); }
                }
            }
            roomIndex = EditorGUILayout.Popup("Room", roomIndex, Rooms.Select(r => r.title).ToArray());
            isRender = EditorGUILayout.ToggleLeft(new GUIContent("Image is a Unity render of this room (exact placement)",
                "On: taken from the room's reference camera, e.g. a render with objects moved. Off: a real photo of the room (placed relative to each table)."), isRender);
            using (new EditorGUILayout.HorizontalScope())
            {
                GUILayout.Label("Quick picks:", GUILayout.Width(80));
                foreach (var (room, title, render, ph) in Rooms)
                {
                    if (GUILayout.Button(title.Replace("Living room ", "") + " render")) Pick(room, render, true);
                    if (ph != null && File.Exists(Path.Combine(repo, ph)) && GUILayout.Button(title.Replace("Living room ", "") + " photo")) Pick(room, ph, false);
                }
            }

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("2. Run the algorithm", EditorStyles.boldLabel);
            offline = EditorGUILayout.ToggleLeft("Offline (models already downloaded; recommended at the event)", offline);
            var running = process != null && !process.HasExited;
            using (new EditorGUILayout.HorizontalScope())
            {
                GUI.enabled = !running && File.Exists(AbsPhoto());
                if (GUILayout.Button(running ? "Running…" : "Run algorithm", GUILayout.Height(28))) Run();
                GUI.enabled = running;
                if (GUILayout.Button("Stop", GUILayout.Width(60), GUILayout.Height(28))) { try { process.Kill(); } catch { } status = "Stopped."; }
                GUI.enabled = true;
            }
            if (!File.Exists(Python))
                EditorGUILayout.HelpBox("Python environment missing: cd pipeline && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt", MessageType.Warning);
            var r = EditorGUILayout.GetControlRect(false, 18);
            EditorGUI.ProgressBar(r, step < 0 ? 0 : (step + 1f) / Steps.Length, step < 0 ? status : $"{StepNames[step]} ({step + 1}/{Steps.Length}) — {status}");

            if (detections != null)
            {
                var h = Mathf.Min(260, position.width * detections.height / detections.width * .5f);
                var w = h * detections.width / detections.height;
                using (new EditorGUILayout.HorizontalScope())
                {
                    GUILayout.Label(detections, GUILayout.Width(w), GUILayout.Height(h));
                    using (new EditorGUILayout.VerticalScope())
                    {
                        EditorGUILayout.LabelField("Found and placed:", EditorStyles.boldLabel);
                        if (result?.objects == null || result.objects.Length == 0) EditorGUILayout.LabelField("nothing (none of our pickables in this image)");
                        else foreach (var o in result.objects)
                                EditorGUILayout.LabelField($"• {o.label} → ({o.position[0]:F2}, {o.position[1]:F2}, {o.position[2]:F2}) m, scale {o.scale:F2}");
                    }
                }
            }

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("3. Walk around it", EditorStyles.boldLabel);
            using (new EditorGUILayout.HorizontalScope())
            {
                GUI.enabled = !running && resultJson != null && !EditorApplication.isPlayingOrWillChangePlaymode;
                if (GUILayout.Button("Open room & Play (generated result)", GUILayout.Height(28))) Play(resultJson);
                GUI.enabled = !running && !EditorApplication.isPlayingOrWillChangePlaymode;
                if (GUILayout.Button("Play room as built", GUILayout.Height(28))) Play(null);
                GUI.enabled = resultJson != null;
                if (GUILayout.Button("Copy to StreamingAssets (headset build)", GUILayout.Height(28))) CopyToStreamingAssets();
                GUI.enabled = true;
            }
            EditorGUILayout.HelpBox("Play uses the XR rig: walk with the XR Device Simulator (keyboard/mouse) or a Quest over Link. Grab the placed objects as usual.", MessageType.None);

            EditorGUILayout.LabelField("Log", EditorStyles.boldLabel);
            logScroll = EditorGUILayout.BeginScrollView(logScroll, GUILayout.MinHeight(120));
            EditorGUILayout.TextArea(log, EditorStyles.wordWrappedMiniLabel);
            EditorGUILayout.EndScrollView();
        }

        void Pick(string room, string relPath, bool render)
        {
            roomIndex = Array.FindIndex(Rooms, x => x.room == room);
            photo = Path.Combine(repo, relPath); isRender = render;
        }

        string AbsPhoto() => string.IsNullOrEmpty(photo) ? "" : Path.IsPathRooted(photo) ? photo : Path.Combine(repo, photo);

        void Run()
        {
            log = ""; step = -1; resultJson = null; result = null; detections = null; status = "starting (first run loads ~1.6 GB of models)…";
            var psi = PipelineProcess(repo, AbsPhoto(), RoomName, isRender, offline);
            var args = psi.Arguments;
            try
            {
                process = new Process { StartInfo = psi, EnableRaisingEvents = true };
                process.OutputDataReceived += (_, e) => { if (e.Data != null) incoming.Enqueue(e.Data); };
                process.ErrorDataReceived += (_, e) => { if (e.Data != null && !e.Data.Contains("Loading weights") && !e.Data.Contains("Redirects")) incoming.Enqueue(e.Data); };
                process.Start(); process.BeginOutputReadLine(); process.BeginErrorReadLine();
                incoming.Enqueue("$ " + Path.GetFileName(Python) + " " + args);
            }
            catch (Exception e) { status = "could not start Python: " + e.Message; process = null; }
        }

        /// <summary>The exact command the window runs: pipeline/.venv python run_pipeline.py photo --name ui_room --room room [--render].</summary>
        public static ProcessStartInfo PipelineProcess(string repo, string photo, string room, bool render, bool offline)
        {
            var python = Path.Combine(repo, "pipeline", ".venv", "bin", "python");
            var args = $"run_pipeline.py \"{photo}\" --name ui_{room} --room {room}" + (render ? " --render" : "");
            var psi = new ProcessStartInfo(python, args)
            {
                WorkingDirectory = Path.Combine(repo, "pipeline"), UseShellExecute = false,
                RedirectStandardOutput = true, RedirectStandardError = true, CreateNoWindow = true,
            };
            psi.Environment["PYTHONUNBUFFERED"] = "1";
            if (offline) { psi.Environment["HF_HUB_OFFLINE"] = "1"; psi.Environment["TRANSFORMERS_OFFLINE"] = "1"; }
            return psi;
        }

        /// <summary>
        /// Batch smoke test of the window's flow without the GUI: run the pipeline exactly like "Run algorithm",
        /// then render the result with the shared loader. Play mode is covered by PickableSceneLoaderPlayTests.
        /// Unity -batchmode -quit -projectPath . -executeMethod RoomVR.EditorTools.PhotoToVRWindow.Smoke
        ///       -photo docs/living-room-sofa-unity.png -room LivingRoomSofa -render -out pipeline/debug/smoke.png
        /// </summary>
        public static void Smoke()
        {
            var a = Environment.GetCommandLineArgs();
            string Arg(string n) { var i = Array.IndexOf(a, n); return i >= 0 && i + 1 < a.Length ? a[i + 1] : null; }
            var repo = Directory.GetParent(Application.dataPath)!.FullName;
            var photo = Path.GetFullPath(Path.Combine(repo, Arg("-photo")));
            var room = Arg("-room"); var render = Array.IndexOf(a, "-render") >= 0;
            using var p = Process.Start(PipelineProcess(repo, photo, room, render, Array.IndexOf(a, "-online") < 0));
            var stderr = p.StandardError.ReadToEndAsync();          // read both pipes at once, or a full one blocks Python
            var stdout = p.StandardOutput.ReadToEnd(); p.WaitForExit();
            var line = stdout.Split('\n').FirstOrDefault(l => l.StartsWith("[7 export] "));
            if (p.ExitCode != 0 || line == null) throw new Exception($"PHOTO_TO_VR_SMOKE: pipeline failed (exit {p.ExitCode})\n{stdout}\n{stderr.Result}");
            var json = line.Substring("[7 export] ".Length).Trim();
            Debug.Log("PHOTO_TO_VR_SMOKE: pipeline ok -> " + json + "\n" + string.Join("\n", stdout.Split('\n').Where(l => l.StartsWith("[") || l.StartsWith("  "))));
            PipelineScenePreview.Preview(json, Arg("-out") ?? Path.Combine(repo, "pipeline", "debug", "smoke.png"));
            Debug.Log("PHOTO_TO_VR_SMOKE_COMPLETE");
        }

        void Pump()
        {
            var changed = false;
            while (incoming.TryDequeue(out var line))
            {
                changed = true; log += line + "\n";
                for (int i = 0; i < Steps.Length; i++) if (line.StartsWith(Steps[i])) { step = i; status = "running"; }
                if (line.StartsWith("[7 export] ")) resultJson = line.Substring("[7 export] ".Length).Trim();
            }
            if (process != null && process.HasExited && incoming.IsEmpty)
            {
                var ok = process.ExitCode == 0 && resultJson != null && File.Exists(resultJson);
                status = ok ? "done" : $"failed (exit {process.ExitCode}), see log";
                if (ok) LoadResult(); else resultJson = null;
                process = null; changed = true;
            }
            if (changed) { logScroll.y = float.MaxValue; Repaint(); }
        }

        void LoadResult()
        {
            result = PickableSceneLoader.Parse(File.ReadAllText(resultJson));
            var img = Path.Combine(repo, "pipeline", "debug", RunName, "detections.png");
            if (File.Exists(img)) { detections = new Texture2D(2, 2); detections.LoadImage(File.ReadAllBytes(img)); }
            Debug.Log($"PHOTO_TO_VR: {result?.objects?.Length ?? 0} pickables -> {resultJson}");
        }

        void Play(string json)
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            if (json != null) SessionState.SetString(PickableSceneLoader.PendingKey, json);
            else SessionState.EraseString(PickableSceneLoader.PendingKey);
            PickableSceneLoader.PendingJsonPath = json;
            EditorSceneManager.OpenScene($"Assets/_Project/Scenes/{RoomName}.unity", OpenSceneMode.Single);
            EditorApplication.EnterPlaymode();
        }

        void CopyToStreamingAssets()
        {
            var dir = Path.Combine(Application.dataPath, "StreamingAssets", "pipeline");
            Directory.CreateDirectory(dir);
            var dest = Path.Combine(dir, RoomName + ".json");
            File.Copy(resultJson, dest, true);
            AssetDatabase.Refresh();
            status = "copied to Assets/StreamingAssets/pipeline/" + RoomName + ".json";
            Debug.Log("PHOTO_TO_VR: " + status + " (load it in a build with PickableSceneLoader.LoadFromStreamingAssets)");
        }
    }
}
