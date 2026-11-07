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
    /// <summary>Checks the generated LivingRoomTV scene (tools/room/build_living_room_tv.py + BuildLivingRoomTV.cs).</summary>
    public class LivingRoomTVTests
    {
        const string Path = "Assets/_Project/Scenes/LivingRoomTV.unity";
        const string Pickables = "Assets/_Project/Prefabs/Pickables/";
        // Must match BuildLivingRoomTV: (x, top height, z) and footprint half-size.
        static readonly Vector3 CoffeeTable = new Vector3(-.30f, .42f, .10f); static readonly Vector2 CoffeeHalf = new Vector2(.5f, .5f);
        static readonly Vector3 SideTable = new Vector3(.10f, .55f, 1.60f); const float SideRadius = .22f;
        static readonly Vector3 Cabinet = new Vector3(.65f, .55f, 2.24f); static readonly Vector2 CabinetHalf = new Vector2(1.1f, .225f);

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

        [Test] public void ThreePickables_BookMugAndLamp()
        {
            var paths = All<XRGrabInteractable>().Select(g => PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(g.gameObject)).OrderBy(p => p).ToArray();
            CollectionAssert.AreEqual(new[] { Pickables + "book.prefab", Pickables + "lamp.prefab", Pickables + "mug.prefab" }, paths);
        }

        [TestCase("book.prefab", 0f, "coffee")]
        [TestCase("mug.prefab", .10f, "side")]
        [TestCase("lamp.prefab", .57f, "cabinet")]
        public void PickableRestsOnItsSurface(string prefab, float height, string surface)
        {
            var p = Pickable(prefab);
            var b = RendererBounds(p);
            var s = surface == "coffee" ? CoffeeTable : surface == "side" ? SideTable : Cabinet;
            if (height > 0) Assert.That(b.size.y, Is.EqualTo(height).Within(.005f), prefab + " real-world height");
            Assert.That(b.min.y, Is.EqualTo(s.y + .005f).Within(.003f), prefab + " should sit on the " + surface);
            if (surface == "side")
                Assert.Less(new Vector2(b.center.x - s.x, b.center.z - s.z).magnitude + Mathf.Max(b.extents.x, b.extents.z), SideRadius, prefab + " overhangs");
            else
            {
                var half = surface == "coffee" ? CoffeeHalf : CabinetHalf;
                Assert.LessOrEqual(Mathf.Abs(b.center.x - s.x) + b.extents.x, half.x, prefab + " overhangs in x");
                Assert.LessOrEqual(Mathf.Abs(b.center.z - s.z) + b.extents.z, half.y, prefab + " overhangs in z");
            }
            Assert.AreEqual(CollisionDetectionMode.ContinuousDynamic, p.GetComponent<Rigidbody>().collisionDetectionMode);
            Physics.SyncTransforms();
            Assert.IsTrue(Physics.Raycast(new Vector3(b.center.x, b.min.y - .001f, b.center.z), Vector3.down, .05f), "No collider under " + prefab);
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

        [Test] public void VisibleSurfacesMatchTheirColliders()
        {
            var root = scene.GetRootGameObjects().Single(r => r.name.StartsWith("Furnishings"));
            var v = root.GetComponentsInChildren<MeshFilter>().SelectMany(f => f.sharedMesh.vertices.Select(x => f.transform.TransformPoint(x))).ToArray();
            var expected = new[] {
                CoffeeTable + new Vector3(-.49f, 0, -.49f), CoffeeTable + new Vector3(.49f, 0, .49f),
                SideTable + Vector3.left * .21f, SideTable + Vector3.right * .21f,
                Cabinet + new Vector3(-1.09f, 0, -.215f), Cabinet + new Vector3(1.09f, 0, .215f) };
            foreach (var e in expected)
                Assert.Less(v.Min(x => Vector3.Distance(x, e)), .03f, "Visual surface does not match its collider at " + e);
        }

        [Test] public void WalkableFloor_RigInsideRoom_AndFurnitureBlocksMovement()
        {
            var areas = All<TeleportationArea>(); Assert.AreEqual(1, areas.Length);
            Assert.AreEqual(1 << 31, areas[0].interactionLayers.value);
            var p = All<CharacterController>().Single().transform.position;
            Assert.That(Mathf.Abs(p.x), Is.LessThan(2.2f)); Assert.That(Mathf.Abs(p.z), Is.LessThan(2.4f));
            Physics.SyncTransforms();
            foreach (var origin in new[] { new Vector3(0, 2, -1.5f), new Vector3(1.40f, 2, .95f), Cabinet + Vector3.up, CoffeeTable + Vector3.up })
                Assert.IsTrue(Physics.Raycast(origin, Vector3.down, 3), "Missing floor/furniture collision at " + origin);
            Assert.IsTrue(Physics.Raycast(new Vector3(0, 1, 0), Vector3.left, 3), "Left wall missing");
            Assert.IsTrue(Physics.Raycast(new Vector3(-1.6f, 1.5f, 0), Vector3.forward, 3), "TV wall missing");
        }
    }
}
