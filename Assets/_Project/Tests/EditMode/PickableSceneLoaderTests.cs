using System.Linq;
using NUnit.Framework;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace RoomVR.Tests
{
    /// <summary>The runtime loader that places a photo-pipeline scene JSON's pickables into a room.</summary>
    public class PickableSceneLoaderTests
    {
        // The sofa room with things moved: mug on the pouf, book at the front of the coffee table, lamp unchanged.
        const string Moved = @"{""version"":1,""room"":""LivingRoomSofa"",""wallColor"":""#ffffff"",""objects"":[
            {""label"":""mug"",""model"":""mug"",""position"":[0.95,0.38,0.38],""rotationY"":90,""scale"":1.0},
            {""label"":""book"",""model"":""book"",""position"":[0.05,0.42,0.70],""rotationY"":30,""scale"":1.1},
            {""label"":""lamp"",""model"":""lamp"",""position"":[-1.0,0.53,0.95],""rotationY"":0,""scale"":1.0}]}";

        static Bounds RendererBounds(GameObject g)
        {
            var rs = g.GetComponentsInChildren<Renderer>(); var b = rs[0].bounds;
            foreach (var r in rs.Skip(1)) b.Encapsulate(r.bounds);
            return b;
        }

        [Test] public void Registry_HasTheThreePickables_WithRealHeights()
        {
            var reg = PickableRegistry.Load();
            Assert.IsNotNull(reg, "Resources/PickableRegistry.asset missing (RoomVR → Update Pickable Registry)");
            foreach (var (model, h, fit) in new[] { ("mug", .10f, true), ("lamp", .57f, true), ("book", .03f, false) })
            {
                var e = reg.Find(model);
                Assert.IsNotNull(e, model); Assert.IsNotNull(e.prefab, model);
                Assert.That(e.heightM, Is.EqualTo(h).Within(.001f), model);
                Assert.AreEqual(fit, e.fitToHeight, model);
            }
        }

        [Test] public void Apply_ReplacesTheRoomsPickables_WithTheJsonOnes()
        {
            var scene = EditorSceneManager.OpenScene("Assets/_Project/Scenes/LivingRoomSofa.unity", OpenSceneMode.Single);
            var placed = PickableSceneLoader.Apply(scene, PickableSceneLoader.Parse(Moved), PickableRegistry.Load());
            Assert.AreEqual(3, placed.Count);
            var all = scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<XRGrabInteractable>()).ToArray();
            Assert.AreEqual(3, all.Length, "the room's own pickables should be gone");
            Assert.IsTrue(all.All(g => g.name.EndsWith("(from photo pipeline)")));

            var mug = placed.Single(g => g.name.StartsWith("mug")); var mb = RendererBounds(mug);
            Assert.That(mb.size.y, Is.EqualTo(.10f).Within(.003f), "mug fitted to its real height");
            Assert.That(mb.min.y, Is.EqualTo(.385f).Within(.003f), "mug rests on the pouf (0.38 m)");
            Assert.That(mb.center.x, Is.EqualTo(.95f).Within(.01f)); Assert.That(mb.center.z, Is.EqualTo(.38f).Within(.01f));
            Assert.That(mug.transform.eulerAngles.y, Is.EqualTo(90f).Within(.5f));

            var lamp = placed.Single(g => g.name.StartsWith("lamp"));
            Assert.That(RendererBounds(lamp).size.y, Is.EqualTo(.57f).Within(.005f));
            Assert.That(RendererBounds(lamp).min.y, Is.EqualTo(.535f).Within(.003f));

            var book = placed.Single(g => g.name.StartsWith("book"));
            Assert.That(RendererBounds(book).min.y, Is.EqualTo(.425f).Within(.003f));
            Assert.AreEqual(CollisionDetectionMode.ContinuousDynamic, book.GetComponent<Rigidbody>().collisionDetectionMode);
            Assert.IsTrue(book.GetComponent<XRGrabInteractable>().useDynamicAttach);
        }

        [Test] public void UnknownModels_AreSkipped_WithAWarning()
        {
            var scene = EditorSceneManager.OpenScene("Assets/_Project/Scenes/LivingRoomSofa.unity", OpenSceneMode.Single);
            var json = @"{""version"":1,""room"":""LivingRoomSofa"",""objects"":[{""label"":""vase"",""model"":""vase"",""position"":[0,0.42,1],""rotationY"":0,""scale"":1}]}";
            LogAssert.Expect(LogType.Warning, "PickableSceneLoader: no prefab for model vase");
            Assert.AreEqual(0, PickableSceneLoader.Apply(scene, PickableSceneLoader.Parse(json), PickableRegistry.Load()).Count);
        }

        [Test] public void PipelineOutput_ParsesWithTheSameFields()
        {
            // The answer keys share the pipeline's format, including extra fields the loader must ignore (source, decor).
            var data = PickableSceneLoader.Parse(System.IO.File.ReadAllText("pipeline/scenes/scene_living_room_tv.json"));
            Assert.AreEqual("LivingRoomTV", data.room);
            Assert.AreEqual(3, data.objects.Length);
            Assert.IsTrue(data.objects.All(o => o.position.Length == 3 && o.scale > 0));
        }
    }
}
