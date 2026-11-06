using UnityEditor;
using UnityEditor.PackageManager.UI;
using UnityEngine;

namespace RoomVR.EditorTools
{
    public static class ImportXRSamples
    {
        const string Package = "com.unity.xr.interaction.toolkit";

        // Run via: Unity -batchmode -executeMethod RoomVR.EditorTools.ImportXRSamples.Run
        public static void Run()
        {
            foreach (var sample in Sample.FindByPackage(Package, null))
            {
                if (sample.displayName != "Starter Assets" && sample.displayName != "XR Device Simulator")
                    continue;
                if (!sample.isImported)
                    sample.Import(Sample.ImportOptions.OverridePreviousImports);
                Debug.Log($"[ImportXRSamples] {sample.displayName} imported={sample.isImported}");
            }
            AssetDatabase.Refresh();
            foreach (var guid in AssetDatabase.FindAssets("t:Prefab", new[] { "Assets/Samples" }))
                Debug.Log("[ImportXRSamples] prefab: " + AssetDatabase.GUIDToAssetPath(guid));
        }
    }
}
