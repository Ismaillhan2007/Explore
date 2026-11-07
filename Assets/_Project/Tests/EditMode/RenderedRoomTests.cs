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
    public class RenderedRoomTests
    {
        const string Path="Assets/_Project/Scenes/RenderedRoom.unity";
        Scene scene;
        [SetUp] public void Open() { scene=EditorSceneManager.OpenScene(Path,OpenSceneMode.Single); }
        T[] All<T>() where T:Component => scene.GetRootGameObjects().SelectMany(r=>r.GetComponentsInChildren<T>(true)).ToArray();
        [Test] public void ExactlyOneExistingMug_WithRealWorldSizeAndFittedCollider()
        {
            var grabs=All<XRGrabInteractable>(); Assert.AreEqual(1,grabs.Length);
            var mug=grabs[0];
            Assert.AreEqual("Assets/_Project/Prefabs/Pickables/mug.prefab",PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(mug.gameObject));
            var renderers=mug.GetComponentsInChildren<Renderer>(); var b=renderers[0].bounds;
            foreach(var r in renderers.Skip(1)) b.Encapsulate(r.bounds);
            Assert.That(b.size.y,Is.EqualTo(.10f).Within(.002f));
            Assert.That(b.min.y,Is.EqualTo(.495f).Within(.002f));
            Assert.That(mug.GetComponent<BoxCollider>().bounds.size.y,Is.EqualTo(b.size.y).Within(.002f));
            Assert.AreEqual(CollisionDetectionMode.ContinuousDynamic,mug.GetComponent<Rigidbody>().collisionDetectionMode);
        }
        [Test] public void WalkableFloor_UsesRigTeleportLayer_AndFurnitureBlocksMovement()
        {
            var areas=All<TeleportationArea>(); Assert.AreEqual(1,areas.Length);
            Assert.AreEqual(1<<31,areas[0].interactionLayers.value);
            Assert.IsNotNull(All<CharacterController>().SingleOrDefault());
            Physics.SyncTransforms();
            foreach(var origin in new[]{new Vector3(0,2,-1.8f),new Vector3(.8f,2,.68f),new Vector3(-1.28f,2,0)})
                Assert.IsTrue(Physics.Raycast(origin,Vector3.down,3),"Missing floor/furniture collision at "+origin);
            Assert.IsTrue(Physics.Raycast(new Vector3(0,1,0),Vector3.left,3),"Left boundary missing");
        }
        [Test] public void BakedMeshesAndTexturesArePresent_AndArchitectureIsSeparate()
        {
            foreach(var name in new[]{"Architecture","Furnishings"})
            {
                var root=scene.GetRootGameObjects().Single(r=>r.name.StartsWith(name));
                var renderer=root.GetComponentInChildren<MeshRenderer>(); Assert.IsNotNull(renderer);
                Assert.IsTrue(renderer.sharedMaterial.shader.isSupported);
                Assert.IsNotNull(renderer.sharedMaterial.GetTexture("_BaseMap"));
                Assert.That(renderer.bounds.size.magnitude,Is.InRange(4,12));
            }
        }
        [Test] public void VisibleCoffeeTableMatchesPhysicsAndMugCoordinates()
        {
            var root=scene.GetRootGameObjects().Single(r=>r.name.StartsWith("Furnishings"));
            var vertices=root.GetComponentsInChildren<MeshFilter>().SelectMany(f=>f.sharedMesh.vertices.Select(v=>f.transform.TransformPoint(v))).ToArray();
            foreach(var offset in new[]{Vector3.left,Vector3.right,Vector3.forward,Vector3.back})
            {
                var expected=new Vector3(.65f,.49f,.78f)+offset*.38f;
                Assert.Less(vertices.Min(v=>Vector3.Distance(v,expected)),.025f,"Visual table does not match its collider at "+expected);
            }
        }
    }
}
