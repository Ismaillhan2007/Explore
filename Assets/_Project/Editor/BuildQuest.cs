using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace RoomVR.EditorTools
{
    public static class BuildQuest
    {
        const string OutputPath = "Builds/RoomVR.apk";

        // CLI: Unity -batchmode -buildTarget Android -executeMethod RoomVR.EditorTools.BuildQuest.Build
        // Menu: RoomVR > Build Quest APK
        [MenuItem("RoomVR/Build Quest APK")]
        public static void Build()
        {
            Directory.CreateDirectory("Builds");
            var options = new BuildPlayerOptions
            {
                scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray(),
                locationPathName = OutputPath,
                target = BuildTarget.Android,
                options = BuildOptions.Development,
            };
            var report = BuildPipeline.BuildPlayer(options);
            Debug.Log($"[BuildQuest] {report.summary.result} size={report.summary.totalSize / (1024 * 1024)} MB errors={report.summary.totalErrors}");
            if (Application.isBatchMode)
                EditorApplication.Exit(report.summary.result == BuildResult.Succeeded ? 0 : 1);
        }
    }
}
