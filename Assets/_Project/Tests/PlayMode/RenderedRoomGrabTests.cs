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
            // The room has two pickables (mug and bedside lamp); pick the mug by name.
            var mug=System.Array.Find(Object.FindObjectsByType<XRGrabInteractable>(FindObjectsSortMode.None),g=>g.name.StartsWith("Mug"));
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

        // Stronger than the test above: the hand must *find* the object on its own (valid target),
        // the rig's real controller interactors must share an interaction layer with it,
        // and after release it must land back on its table, upright.
        [UnityTest] public IEnumerator MugIsGrabbableByAHand() { yield return GrabLiftRelease("Mug",.49f); }
        [UnityTest] public IEnumerator BedsideLampIsGrabbableByAHand() { yield return GrabLiftRelease("Bedside lamp",.59f); }

        static IEnumerator GrabLiftRelease(string namePrefix,float surfaceY)
        {
            yield return SceneManager.LoadSceneAsync("RenderedRoom");
            yield return null;
            var target=System.Array.Find(Object.FindObjectsByType<XRGrabInteractable>(FindObjectsSortMode.None),g=>g.name.StartsWith(namePrefix));
            Assert.IsNotNull(target,namePrefix+" not found in RenderedRoom");
            Assert.IsFalse(target.GetComponent<Rigidbody>().isKinematic,namePrefix+" must be a dynamic body");

            var rigInteractors=Object.FindObjectsByType<XRBaseInteractor>(FindObjectsSortMode.None);
            Assert.IsNotEmpty(rigInteractors,"XR rig has no interactors");
            Assert.IsTrue(System.Array.Exists(rigInteractors,i=>(i.interactionLayers.value&target.interactionLayers.value)!=0),
                "No rig controller interactor shares an interaction layer with "+namePrefix);

            var manager=Object.FindFirstObjectByType<XRInteractionManager>();
            var hand=new GameObject("Automated test hand");
            hand.transform.position=target.GetComponent<Collider>().bounds.center;
            var trigger=hand.AddComponent<SphereCollider>(); trigger.radius=.08f; trigger.isTrigger=true;
            var rb=hand.AddComponent<Rigidbody>(); rb.isKinematic=true; rb.useGravity=false;
            var interactor=hand.AddComponent<XRDirectInteractor>();
            for(int i=0;i<3;i++) yield return new WaitForFixedUpdate();
            yield return null;
            var targets=new List<IXRInteractable>(); interactor.GetValidTargets(targets);
            Assert.Contains((IXRInteractable)target,targets,"Hand touching "+namePrefix+" does not see it as grabbable");

            float startY=target.transform.position.y;
            manager.SelectEnter((IXRSelectInteractor)interactor,(IXRSelectInteractable)target);
            Assert.IsTrue(target.isSelected);
            hand.transform.position+=Vector3.up*.3f;
            for(int i=0;i<45;i++) yield return new WaitForFixedUpdate();
            Assert.Greater(target.transform.position.y,startY+.15f,namePrefix+" did not follow the hand up");

            manager.SelectExit((IXRSelectInteractor)interactor,(IXRSelectInteractable)target);
            Object.Destroy(hand);
            for(int i=0;i<240;i++) yield return new WaitForFixedUpdate();
            var body=target.GetComponent<Rigidbody>();
            Assert.That(target.GetComponent<Collider>().bounds.min.y,Is.EqualTo(surfaceY).Within(.03f),namePrefix+" did not land back on its table");
            Assert.Less(body.linearVelocity.magnitude,.08f,namePrefix+" is still moving");
            Assert.Greater(Vector3.Dot(target.transform.up,Vector3.up),.95f,namePrefix+" fell over");
        }
    }
}
