using System.Collections;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace RoomVR.Tests
{
    /// <summary>What the "Photo to VR" window relies on: a pending scene JSON is applied when its room loads in Play mode.</summary>
    public class PickableSceneLoaderPlayTests
    {
        string jsonPath;

        [SetUp] public void WriteJson()
        {
            jsonPath = Path.Combine(Application.temporaryCachePath, "pipeline_play_test.json");
            File.WriteAllText(jsonPath, @"{""version"":1,""room"":""LivingRoomTV"",""wallColor"":""#ffffff"",""objects"":[
                {""label"":""mug"",""model"":""mug"",""position"":[-0.55,0.42,0.30],""rotationY"":0,""scale"":1.0},
                {""label"":""book"",""model"":""book"",""position"":[0.10,0.55,1.60],""rotationY"":0,""scale"":1.0}]}");
        }

        [TearDown] public void Clear() { PickableSceneLoader.PendingJsonPath = null; if (File.Exists(jsonPath)) File.Delete(jsonPath); }

        [UnityTest]
        public IEnumerator PendingJson_IsPlacedWhenItsRoomLoads_AndSettlesOnTheTables()
        {
            PickableSceneLoader.PendingJsonPath = jsonPath;
            yield return SceneManager.LoadSceneAsync("LivingRoomTV");
            yield return null;
            var grabbables = Object.FindObjectsByType<XRGrabInteractable>(FindObjectsSortMode.None);
            CollectionAssert.AreEquivalent(new[] { "book (from photo pipeline)", "mug (from photo pipeline)" }, grabbables.Select(g => g.name).ToArray(),
                "the room's own pickables are replaced by the JSON's");
            for (int i = 0; i < 150; i++) yield return new WaitForFixedUpdate();
            var mug = grabbables.Single(g => g.name.StartsWith("mug")).GetComponent<Collider>();
            var book = grabbables.Single(g => g.name.StartsWith("book")).GetComponent<Collider>();
            Assert.That(mug.bounds.min.y, Is.EqualTo(.42f).Within(.03f), "mug stays on the coffee table");
            Assert.That(book.bounds.min.y, Is.EqualTo(.55f).Within(.03f), "book stays on the side table");
            Assert.That(mug.bounds.center.x, Is.EqualTo(-.55f).Within(.05f));
        }

        [UnityTest]
        public IEnumerator JsonForAnotherRoom_IsIgnored()
        {
            PickableSceneLoader.PendingJsonPath = jsonPath;              // it is for LivingRoomTV
            yield return SceneManager.LoadSceneAsync("LivingRoomSofa");
            yield return null;
            var names = Object.FindObjectsByType<XRGrabInteractable>(FindObjectsSortMode.None).Select(g => g.name).ToArray();
            Assert.AreEqual(3, names.Length);
            Assert.IsFalse(names.Any(n => n.EndsWith("(from photo pipeline)")), "the sofa room keeps its own pickables");
        }
    }
}
