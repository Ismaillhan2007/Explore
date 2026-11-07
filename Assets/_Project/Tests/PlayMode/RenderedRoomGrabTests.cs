using System.Collections;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Interactables;
using UnityEngine.XR.Interaction.Toolkit.Interactors;

namespace RoomVR.Tests
{
    public class RenderedRoomGrabTests
    {
        [UnityTest]
        public IEnumerator PlayerCanWalkFromEntranceTowardTableAndCannotCrossRoomBoundary()
        {
            yield return SceneManager.LoadSceneAsync("RenderedRoom");
            yield return null;
            var player=Object.FindFirstObjectByType<CharacterController>();
            Assert.IsNotNull(player);
            for(int i=0;i<25;i++) { player.Move(Vector3.left*.05f); yield return null; }
            Assert.That(player.transform.position.x,Is.InRange(-.2f,.25f));
            for(int i=0;i<40;i++) { player.Move(Vector3.forward*.05f); yield return null; }
            Assert.Greater(player.transform.position.z,-.6f,"Entrance-to-table aisle is obstructed");
            for(int i=0;i<130;i++) { player.Move(Vector3.left*.05f); yield return null; }
            Assert.Greater(player.transform.position.x,-2.1f,"Player crossed the room boundary");
        }
        [UnityTest]
        public IEnumerator MugCanBeSelectedLiftedReleasedAndSettlesOnTable()
        {
            yield return SceneManager.LoadSceneAsync("RenderedRoom");
            yield return null;
            var mug=Object.FindFirstObjectByType<XRGrabInteractable>();
            Assert.IsNotNull(mug);
            var manager=Object.FindFirstObjectByType<XRInteractionManager>();
            var hand=new GameObject("Automated test hand");
            hand.transform.position=mug.transform.position;
            var trigger=hand.AddComponent<SphereCollider>(); trigger.radius=.08f; trigger.isTrigger=true;
            var rb=hand.AddComponent<Rigidbody>();rb.isKinematic=true;rb.useGravity=false;
            var interactor=hand.AddComponent<XRDirectInteractor>();
            yield return null;
            float originalY=mug.transform.position.y;
            manager.SelectEnter((IXRSelectInteractor)interactor,(IXRSelectInteractable)mug);
            Assert.IsTrue(mug.isSelected);
            hand.transform.position+=Vector3.up*.3f;
            for(int i=0;i<45;i++) yield return new WaitForFixedUpdate();
            Assert.Greater(mug.transform.position.y,originalY+.15f);
            manager.SelectExit((IXRSelectInteractor)interactor,(IXRSelectInteractable)mug);
            Assert.IsFalse(mug.isSelected);
            Object.Destroy(hand);
            for(int i=0;i<180;i++) yield return new WaitForFixedUpdate();
            Assert.That(mug.GetComponent<Collider>().bounds.min.y,Is.EqualTo(.49f).Within(.03f));
            Assert.Less(mug.GetComponent<Rigidbody>().linearVelocity.magnitude,.08f);
        }
    }
}
