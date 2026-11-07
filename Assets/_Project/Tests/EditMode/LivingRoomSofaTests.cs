using System.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.XR.Interaction.Toolkit.Interactables;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Teleportation;

namespace RoomVR.Tests
{
    /// <summary>Checks the generated LivingRoomSofa scene (tools/room/build_living_room_sofa.py + BuildLivingRoomSofa.cs).</summary>
    public class LivingRoomSofaTests
    {
        const string Path = "Assets/_Project/Scenes/LivingRoomSofa.unity";
        const string Pickables = "Assets/_Project/Prefabs/Pickables/";
        // Must match BuildLivingRoomSofa: coffee table top .42 m, side table top .53 m.
        static readonly Vector3 CoffeeTable = new Vector3(-.15f, .42f, .95f);
        static readonly Vector3 SideTable = new Vector3(-1.0f, .53f, .95f);

        Scene scene;
        [SetUp] public void Open() { scene = EditorSceneManager.OpenScene(Path, OpenSceneMode.Single); }
        T[] All<T>() where T : Component => scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<T>(true)).ToArray();
        static Bounds RendererBounds(Component c)
        {
            var rs = c.GetComponentsInChildren<Renderer>(); var b = rs[0].bounds;
            foreach (var r in rs.Skip(1)) b.Encapsulate(r.bounds);
            return b;
        }
        XRGrabInteractable Pickable(string prefab)
        {
            var m = All<XRGrabInteractable>().Where(g => PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(g.gameObject) == Pickables + prefab).ToArray();
            Assert.AreEqual(1, m.Length, "Expected exactly one " + prefab);
            return m[0];
        }

        [Test] public void ThreePickables_MugBookAndLamp()
        {
            var paths = All<XRGrabInteractable>().Select(g => PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(g.gameObject)).OrderBy(p => p).ToArray();
            CollectionAssert.AreEqual(new[] { Pickables + "book.prefab", Pickables + "lamp.prefab", Pickables + "mug.prefab" }, paths);
        }

        [TestCase("mug.prefab", .10f, "coffee")]
        [TestCase("book.prefab", 0f, "coffee")]
        [TestCase("lamp.prefab", .57f, "side")]
        public void PickableRestsOnItsTable(string prefab, float height, string table)
        {
            var p = Pickable(prefab);
            var surface = table == "coffee" ? CoffeeTable : SideTable;
            float radius = table == "coffee" ? .45f : .25f;
            var b = RendererBounds(p);
            if (height > 0) Assert.That(b.size.y, Is.EqualTo(height).Within(.005f), prefab + " real-world height");
            Assert.That(b.min.y, Is.EqualTo(surface.y + .005f).Within(.003f), prefab + " should sit on the " + table + " table");
            var flat = new Vector2(b.center.x - surface.x, b.center.z - surface.z).magnitude;
            Assert.Less(flat + Mathf.Max(b.extents.x, b.extents.z), radius, prefab + " overhangs the " + table + " table");
            Assert.AreEqual(CollisionDetectionMode.ContinuousDynamic, p.GetComponent<Rigidbody>().collisionDetectionMode);
            Physics.SyncTransforms();
            Assert.IsTrue(Physics.Raycast(new Vector3(b.center.x, b.min.y - .001f, b.center.z), Vector3.down, .05f), "No table collider under " + prefab);
        }

        [Test] public void BakedMeshesAndTexturesArePresent_AndArchitectureIsSeparate()
        {
            foreach (var name in new[] { "Architecture", "Furnishings" })
            {
                var root = scene.GetRootGameObjects().Single(r => r.name.StartsWith(name));
                var renderer = root.GetComponentInChildren<MeshRenderer>(); Assert.IsNotNull(renderer);
                Assert.IsTrue(renderer.sharedMaterial.shader.isSupported);
                Assert.IsNotNull(renderer.sharedMaterial.GetTexture("_BaseMap"));
                Assert.That(renderer.bounds.size.magnitude, Is.InRange(4, 12));
            }
        }

        [Test] public void VisibleTablesMatchTheirColliders()
        {
            var root = scene.GetRootGameObjects().Single(r => r.name.StartsWith("Furnishings"));
            var v = root.GetComponentsInChildren<MeshFilter>().SelectMany(f => f.sharedMesh.vertices.Select(x => f.transform.TransformPoint(x))).ToArray();
            foreach (var (c, r) in new[] { (CoffeeTable, .45f), (SideTable, .25f) })
                foreach (var dir in new[] { Vector3.left, Vector3.right, Vector3.forward, Vector3.back })
                {
                    var expected = c + dir * (r - .01f);
                    Assert.Less(v.Min(x => Vector3.Distance(x, expected)), .03f, "Visual table rim does not match its collider at " + expected);
                }
        }

        [Test] public void WalkableFloor_RigInsideRoom_AndFurnitureBlocksMovement()
        {
            var areas = All<TeleportationArea>(); Assert.AreEqual(1, areas.Length);
            Assert.AreEqual(1 << 31, areas[0].interactionLayers.value);
            var player = All<CharacterController>().Single();
            var p = player.transform.position;
            Assert.That(Mathf.Abs(p.x), Is.LessThan(2.0f)); Assert.That(Mathf.Abs(p.z), Is.LessThan(2.3f));
            Physics.SyncTransforms();
            foreach (var origin in new[] { new Vector3(0, 2, -1.5f), new Vector3(.25f, 2, 1.98f), new Vector3(.95f, 2, .38f), CoffeeTable + Vector3.up })
                Assert.IsTrue(Physics.Raycast(origin, Vector3.down, 3), "Missing floor/furniture collision at " + origin);
            Assert.IsTrue(Physics.Raycast(new Vector3(0, 1, 0), Vector3.left, 3), "Left wall missing");
            Assert.IsTrue(Physics.Raycast(new Vector3(0, 1, 0), Vector3.forward, 3), "Back wall missing");
        }
    }
}
