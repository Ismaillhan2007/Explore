using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEngine;

namespace RoomVR.EditorTools
{
    /// <summary>
    /// Builds Assets/_Project/Resources/PickableRegistry.asset from pipeline/model_library.json:
    /// every available pickable model whose prefab exists in Prefabs/Pickables.
    /// Batch: Unity -batchmode -quit -projectPath . -executeMethod RoomVR.EditorTools.PickableRegistryBuilder.Run
    /// </summary>
    public static class PickableRegistryBuilder
    {
        public const string AssetPath = "Assets/_Project/Resources/PickableRegistry.asset";
        const string Library = "pipeline/model_library.json";
        const string Pickables = "Assets/_Project/Prefabs/Pickables/";

        [MenuItem("RoomVR/Update Pickable Registry")]
        public static void Run()
        {
            var entries = Read(File.ReadAllText(Library));
            var registry = AssetDatabase.LoadAssetAtPath<PickableRegistry>(AssetPath);
            if (!registry)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(AssetPath));
                registry = ScriptableObject.CreateInstance<PickableRegistry>();
                AssetDatabase.CreateAsset(registry, AssetPath);
            }
            registry.entries = entries.ToArray();
            EditorUtility.SetDirty(registry);
            AssetDatabase.SaveAssets();
            Debug.Log($"PICKABLE_REGISTRY: {entries.Count} models -> {AssetPath}: " + string.Join(", ", entries.ConvertAll(e => $"{e.model} ({e.heightM} m)")));
        }

        /// <summary>Available pickable models from model_library.json that have a prefab.</summary>
        public static List<PickableRegistry.Entry> Read(string libraryJson)
        {
            var result = new List<PickableRegistry.Entry>();
            var models = Block(libraryJson, "\"models\"");
            if (models == null) return result;
            foreach (Match m in Regex.Matches(models, "\"([A-Za-z0-9_]+)\"\\s*:\\s*\\{"))
            {
                var name = m.Groups[1].Value;
                var body = Block(models.Substring(m.Index), "\"" + name + "\"");
                if (body == null || !body.Contains("\"kind\": \"pickable\"") || !body.Contains("\"status\": \"available\"")) continue;
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Pickables + name + ".prefab");
                if (!prefab) continue;
                var h = Regex.Match(body, "\"height_m\"\\s*:\\s*([0-9.]+)");
                result.Add(new PickableRegistry.Entry
                {
                    model = name, prefab = prefab,
                    heightM = h.Success ? float.Parse(h.Groups[1].Value, CultureInfo.InvariantCulture) : 0f,
                    fitToHeight = !body.Contains("\"scale_from\": \"width\""),
                });
            }
            return result;
        }

        /// <summary>The {...} object that follows `key` (balanced braces), or null.</summary>
        static string Block(string text, string key)
        {
            var i = text.IndexOf(key, System.StringComparison.Ordinal);
            if (i < 0) return null;
            var start = text.IndexOf('{', i);
            if (start < 0) return null;
            int depth = 0;
            for (int j = start; j < text.Length; j++)
            {
                if (text[j] == '{') depth++;
                else if (text[j] == '}' && --depth == 0) return text.Substring(start, j - start + 1);
            }
            return null;
        }
    }
}
