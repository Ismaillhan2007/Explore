using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.XR.Management;
using UnityEditor.XR.Management.Metadata;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.XR.Management;
using UnityEngine.XR.OpenXR;
using UnityEngine.XR.OpenXR.Features;

namespace RoomVR.EditorTools
{
    // Run via: Unity -batchmode -buildTarget Android -executeMethod RoomVR.EditorTools.ConfigureQuest.Run
    // Settings follow Meta's "Prepare your app for publishing" and OpenXR Meta Quest Support docs.
    public static class ConfigureQuest
    {
        static readonly string[] FeatureTypeNames =
        {
            "MetaQuestFeature",
            "OculusTouchControllerProfile",
            "MetaQuestTouchPlusControllerProfile",
        };

        public static void Run()
        {
            ConfigurePlayer();
            ConfigureXR();
            AssetDatabase.SaveAssets();
            Debug.Log("[ConfigureQuest] done");
        }

        static void ConfigurePlayer()
        {
            PlayerSettings.companyName = "Explore28";
            PlayerSettings.productName = "RoomVR";
            PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, "com.explore28.roomvr");
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.preferredInstallLocation = AndroidPreferredInstallLocation.Auto;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel29;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevelAuto;
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.Vulkan });
            PlayerSettings.colorSpace = ColorSpace.Linear;
        }

        static void ConfigureXR()
        {
            const BuildTargetGroup group = BuildTargetGroup.Android;

            EditorBuildSettings.TryGetConfigObject(XRGeneralSettings.k_SettingsKey, out XRGeneralSettingsPerBuildTarget perBuild);
            if (perBuild == null)
            {
                perBuild = ScriptableObject.CreateInstance<XRGeneralSettingsPerBuildTarget>();
                AssetDatabase.CreateAsset(perBuild, "Assets/XR/XRGeneralSettingsPerBuildTarget.asset");
                EditorBuildSettings.AddConfigObject(XRGeneralSettings.k_SettingsKey, perBuild, true);
            }
            if (!perBuild.HasSettingsForBuildTarget(group)) perBuild.CreateDefaultSettingsForBuildTarget(group);
            if (!perBuild.HasManagerSettingsForBuildTarget(group)) perBuild.CreateDefaultManagerSettingsForBuildTarget(group);

            var manager = perBuild.ManagerSettingsForBuildTarget(group);
            var ok = XRPackageMetadataStore.AssignLoader(manager, "UnityEngine.XR.OpenXR.OpenXRLoader", group);
            Debug.Log($"[ConfigureQuest] OpenXR loader assigned: {ok}");
            EditorUtility.SetDirty(manager);
            EditorUtility.SetDirty(perBuild);

            var openxr = OpenXRSettings.GetSettingsForBuildTargetGroup(group);
            if (openxr == null) { Debug.LogError("[ConfigureQuest] No OpenXR settings for Android"); return; }
            openxr.renderMode = OpenXRSettings.RenderMode.SinglePassInstanced; // Multiview on Quest

            foreach (var feature in openxr.GetFeatures<OpenXRFeature>())
            {
                var name = feature.GetType().Name;
                if (FeatureTypeNames.Contains(name)) feature.enabled = true;
                Debug.Log($"[ConfigureQuest] feature {name} enabled={feature.enabled}");
                EditorUtility.SetDirty(feature);
            }
            EditorUtility.SetDirty(openxr);
        }
    }
}
