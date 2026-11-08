using System;
using UnityEngine;

namespace RoomVR
{
    /// <summary>
    /// Model name (as written in a pipeline scene JSON) -> pickable prefab and its real-world height.
    /// Lives at Assets/_Project/Resources/PickableRegistry.asset so it ships in a headset build.
    /// Generated from pipeline/model_library.json by RoomVR → Update Pickable Registry.
    /// </summary>
    [CreateAssetMenu(menuName = "RoomVR/Pickable Registry")]
    public class PickableRegistry : ScriptableObject
    {
        [Serializable]
        public class Entry
        {
            public string model;
            public GameObject prefab;
            [Tooltip("Real-world height in metres (height_m in model_library.json).")]
            public float heightM;
            [Tooltip("Fit the instance to heightM x scale. Off for objects measured by width (books): they keep the prefab size x scale.")]
            public bool fitToHeight = true;
        }

        public Entry[] entries = Array.Empty<Entry>();

        public const string ResourcePath = "PickableRegistry";

        public Entry Find(string model)
        {
            foreach (var e in entries)
                if (e != null && e.model == model) return e;
            return null;
        }

        public static PickableRegistry Load() => Resources.Load<PickableRegistry>(ResourcePath);
    }
}
