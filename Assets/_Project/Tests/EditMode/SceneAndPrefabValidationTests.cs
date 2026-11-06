using System.Collections.Generic;
using System.IO;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace RoomVR.Tests
{
    public class SceneAndPrefabValidationTests
    {
        const string PickablesFolder = "Assets/_Project/Prefabs/Pickables";
        const string ScenesFolder = "Assets/_Project/Scenes";
        const float MaxSceneExtent = 100f;

        static IEnumerable<string> PickablePrefabPaths()
        {
            if (!AssetDatabase.IsValidFolder(PickablesFolder)) yield break;
            foreach (var guid in AssetDatabase.FindAssets("t:Prefab", new[] { PickablesFolder }))
                yield return AssetDatabase.GUIDToAssetPath(guid);
        }

        static IEnumerable<string> ScenePaths()
        {
            if (!AssetDatabase.IsValidFolder(ScenesFolder)) yield break;
            foreach (var guid in AssetDatabase.FindAssets("t:Scene", new[] { ScenesFolder }))
                yield return AssetDatabase.GUIDToAssetPath(guid);
        }

        [Test]
        public void PickablePrefabs_HaveColliderRigidbodyAndGrabInteractable()
        {
            foreach (var path in PickablePrefabPaths())
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                Assert.IsNotNull(prefab, path);
                Assert.IsNotNull(prefab.GetComponentInChildren<Collider>(), $"{path}: missing Collider");
                Assert.IsNotNull(prefab.GetComponent<Rigidbody>(), $"{path}: missing Rigidbody");
                Assert.IsNotNull(prefab.GetComponent<XRGrabInteractable>(), $"{path}: missing XRGrabInteractable");
            }
        }

        [Test]
        public void PickablePrefabs_HaveNoMissingScripts()
        {
            foreach (var path in PickablePrefabPaths())
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                foreach (var t in prefab.GetComponentsInChildren<Transform>(true))
                    Assert.AreEqual(0, GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject),
                        $"{path}: missing script on {t.name}");
            }
        }

        [Test]
        public void Scenes_HaveNoMissingScripts_AndSaneTransforms()
        {
            foreach (var path in ScenePaths())
            {
                var scene = EditorSceneManager.OpenScene(path, OpenSceneMode.Additive);
                try
                {
                    foreach (var root in scene.GetRootGameObjects())
                        foreach (var t in root.GetComponentsInChildren<Transform>(true))
                        {
                            Assert.AreEqual(0, GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject),
                                $"{path}: missing script on {t.name}");
                            Assert.Less(Mathf.Abs(t.position.x), MaxSceneExtent, $"{path}: {t.name} x out of range");
                            Assert.Less(Mathf.Abs(t.position.y), MaxSceneExtent, $"{path}: {t.name} y out of range");
                            Assert.Less(Mathf.Abs(t.position.z), MaxSceneExtent, $"{path}: {t.name} z out of range");
                            // Negative scale is legal (mirrored models); zero scale on any axis is not.
                            Assert.Greater(Mathf.Abs(t.lossyScale.x), 0f, $"{path}: {t.name} has zero X scale");
                            Assert.Greater(Mathf.Abs(t.lossyScale.y), 0f, $"{path}: {t.name} has zero Y scale");
                            Assert.Greater(Mathf.Abs(t.lossyScale.z), 0f, $"{path}: {t.name} has zero Z scale");
                        }
                }
                finally
                {
                    EditorSceneManager.CloseScene(scene, true);
                }
            }
        }

        [Test]
        public void ScenesInFolder_AreInBuildSettings()
        {
            var inBuild = new HashSet<string>();
            foreach (var s in EditorBuildSettings.scenes) inBuild.Add(s.path);
            foreach (var path in ScenePaths())
                Assert.IsTrue(inBuild.Contains(path), $"{path} is not in Build Settings");
        }
    }
}
