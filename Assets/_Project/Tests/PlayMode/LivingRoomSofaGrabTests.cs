using System.Collections;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Interactables;
using UnityEngine.XR.Interaction.Toolkit.Interactors;

namespace RoomVR.Tests
{
    /// <summary>In LivingRoomSofa, a hand can find, lift and release each pickable, and it lands back on its table.</summary>
    public class LivingRoomSofaGrabTests
    {
        [UnityTest] public IEnumerator MugIsGrabbable() { yield return GrabLiftRelease("Mug", .42f); }
        [UnityTest] public IEnumerator BookIsGrabbable() { yield return GrabLiftRelease("Book", .42f); }
        [UnityTest] public IEnumerator TableLampIsGrabbable() { yield return GrabLiftRelease("Table lamp", .53f); }

        [UnityTest]
        public IEnumerator PlayerCanWalkTowardTheSofaButNotThroughWalls()
        {
            yield return SceneManager.LoadSceneAsync("LivingRoomSofa");
            yield return null;
            var player = Object.FindFirstObjectByType<CharacterController>();
            Assert.IsNotNull(player);
            for (int i = 0; i < 30; i++) { player.Move(Vector3.forward * .05f); yield return null; }
            Assert.Greater(player.transform.position.z, -.6f, "Path from the doorway into the room is blocked");
            for (int i = 0; i < 120; i++) { player.Move(Vector3.right * .05f); yield return null; }
            Assert.Less(player.transform.position.x, 2.1f, "Player crossed the right wall");
        }

        static IEnumerator GrabLiftRelease(string namePrefix, float surfaceY)
        {
            yield return SceneManager.LoadSceneAsync("LivingRoomSofa");
            yield return null;
            var target = System.Array.Find(Object.FindObjectsByType<XRGrabInteractable>(FindObjectsSortMode.None), g => g.name.StartsWith(namePrefix));
            Assert.IsNotNull(target, namePrefix + " not found in LivingRoomSofa");
            Assert.IsFalse(target.GetComponent<Rigidbody>().isKinematic);
            var rigInteractors = Object.FindObjectsByType<XRBaseInteractor>(FindObjectsSortMode.None);
            Assert.IsTrue(System.Array.Exists(rigInteractors, i => (i.interactionLayers.value & target.interactionLayers.value) != 0),
                "No rig controller interactor shares an interaction layer with " + namePrefix);

            var manager = Object.FindFirstObjectByType<XRInteractionManager>();
            var hand = new GameObject("Automated test hand");
            hand.transform.position = target.GetComponent<Collider>().bounds.center;
            var trigger = hand.AddComponent<SphereCollider>(); trigger.radius = .08f; trigger.isTrigger = true;
            var rb = hand.AddComponent<Rigidbody>(); rb.isKinematic = true; rb.useGravity = false;
            var interactor = hand.AddComponent<XRDirectInteractor>();
            for (int i = 0; i < 3; i++) yield return new WaitForFixedUpdate();
            yield return null;
            var targets = new List<IXRInteractable>(); interactor.GetValidTargets(targets);
            Assert.Contains((IXRInteractable)target, targets, "Hand touching " + namePrefix + " does not see it as grabbable");

            float startY = target.transform.position.y;
            manager.SelectEnter((IXRSelectInteractor)interactor, (IXRSelectInteractable)target);
            Assert.IsTrue(target.isSelected);
            hand.transform.position += Vector3.up * .3f;
            for (int i = 0; i < 45; i++) yield return new WaitForFixedUpdate();
            Assert.Greater(target.transform.position.y, startY + .15f, namePrefix + " did not follow the hand up");

            manager.SelectExit((IXRSelectInteractor)interactor, (IXRSelectInteractable)target);
            Object.Destroy(hand);
            for (int i = 0; i < 240; i++) yield return new WaitForFixedUpdate();
            Assert.That(target.GetComponent<Collider>().bounds.min.y, Is.EqualTo(surfaceY).Within(.03f), namePrefix + " did not land back on its table");
            Assert.Less(target.GetComponent<Rigidbody>().linearVelocity.magnitude, .08f, namePrefix + " is still moving");
            Assert.Greater(Vector3.Dot(target.transform.up, Vector3.up), .95f, namePrefix + " fell over");
        }
    }
}
