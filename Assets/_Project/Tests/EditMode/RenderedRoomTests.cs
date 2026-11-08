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
        const string MugPrefab="Assets/_Project/Prefabs/Pickables/mug.prefab";
        const string LampPrefab="Assets/_Project/Prefabs/Pickables/lamp.prefab";
        const string BookPrefab="Assets/_Project/Prefabs/Pickables/book.prefab";
        static Bounds RendererBounds(Component c)
        {
            var renderers=c.GetComponentsInChildren<Renderer>(); var b=renderers[0].bounds;
            foreach(var r in renderers.Skip(1)) b.Encapsulate(r.bounds);
            return b;
        }
        XRGrabInteractable Pickable(string prefab)
        {
            var matches=All<XRGrabInteractable>().Where(g=>PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(g.gameObject)==prefab).ToArray();
            Assert.AreEqual(1,matches.Length,"Expected exactly one instance of "+prefab);
            return matches[0];
        }
        [Test] public void ExactlyThreePickables_TheMugTheBedsideLampAndTheBook()
        {
            var paths=All<XRGrabInteractable>().Select(g=>PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(g.gameObject)).OrderBy(p=>p).ToArray();
            CollectionAssert.AreEqual(new[]{BookPrefab,LampPrefab,MugPrefab},paths);
        }
        [Test] public void Mug_WithRealWorldSizeAndFittedCollider()
        {
            var mug=Pickable(MugPrefab);
            var b=RendererBounds(mug);
            Assert.That(b.size.y,Is.EqualTo(.10f).Within(.002f));
            Assert.That(b.min.y,Is.EqualTo(.495f).Within(.002f));
            Assert.That(mug.GetComponent<BoxCollider>().bounds.size.y,Is.EqualTo(b.size.y).Within(.002f));
            Assert.AreEqual(CollisionDetectionMode.ContinuousDynamic,mug.GetComponent<Rigidbody>().collisionDetectionMode);
        }
        [Test] public void BedsideLamp_StandsOnBedsideTable_WhereTheBakedLampWas()
        {
            var lamp=Pickable(LampPrefab);
            var b=RendererBounds(lamp);
            Assert.That(b.size.y,Is.EqualTo(.57f).Within(.005f));
            Assert.That(b.min.y,Is.EqualTo(.595f).Within(.003f),"Lamp should rest on the 0.59 m bedside table");
            Assert.That(b.center.x,Is.EqualTo(-.58f).Within(.01f));
            Assert.That(b.center.z,Is.EqualTo(1.89f).Within(.01f));
            var col=lamp.GetComponent<Collider>().bounds;
            Assert.That(col.size.y,Is.EqualTo(b.size.y).Within(.01f),"Lamp collider should match its mesh");
            Assert.That(col.min.y,Is.EqualTo(b.min.y).Within(.005f));
            Assert.AreEqual(CollisionDetectionMode.ContinuousDynamic,lamp.GetComponent<Rigidbody>().collisionDetectionMode);
            Physics.SyncTransforms();
            // Start just below the lamp's collider and above the table top, so the ray can only hit the table.
            Assert.IsTrue(Physics.Raycast(new Vector3(-.58f,b.min.y-.001f,1.89f),Vector3.down,.05f),"No bedside table collider under the lamp");
        }
        [Test] public void Book_RestsOnTheDesk_BesideTheLaptop()
        {
            // Placed by BuildRenderedRoom.cs (originally added by hand in PR #10), so a rebuild keeps it.
            var book=Pickable(BookPrefab);
            var b=RendererBounds(book);
            Assert.That(b.min.y,Is.EqualTo(.805f).Within(.003f),"Book should rest on the 0.80 m desk");
            Assert.That(b.center.x,Is.EqualTo(1.57f).Within(.01f));
            Assert.That(b.center.z,Is.EqualTo(-1.29f).Within(.01f));
            // Inside the desk top (x 1.42..2.10, z -1.465..0.085) and clear of the baked laptop (z -1.09..-0.83).
            Assert.That(b.min.x,Is.GreaterThanOrEqualTo(1.42f)); Assert.That(b.max.x,Is.LessThanOrEqualTo(2.10f));
            Assert.That(b.min.z,Is.GreaterThanOrEqualTo(-1.465f)); Assert.That(b.max.z,Is.LessThan(-1.09f),"Book overlaps the baked laptop");
            Assert.AreEqual(CollisionDetectionMode.ContinuousDynamic,book.GetComponent<Rigidbody>().collisionDetectionMode);
            Physics.SyncTransforms();
            Assert.IsTrue(Physics.Raycast(new Vector3(b.center.x,b.min.y-.001f,b.center.z),Vector3.down,.05f),"No desk collider under the book");
        }
        [Test] public void BakedFurnishings_NoLongerContainTheBedsideLamp()
        {
            // The old baked lamp shade was a 0.20 m radius cylinder from 0.875 to 1.165 m high.
            // No baked vertices may remain in that volume, or there would be two lamps.
            // (Starts at 0.86 m so the small baked plant next to it, which tops out lower, is not counted.)
            var root=scene.GetRootGameObjects().Single(r=>r.name.StartsWith("Furnishings"));
            var stray=root.GetComponentsInChildren<MeshFilter>().SelectMany(f=>f.sharedMesh.vertices.Select(v=>f.transform.TransformPoint(v)))
                .Count(v=>v.y>.86f&&v.y<1.20f&&new Vector2(v.x+.58f,v.z-1.89f).magnitude<.21f);
            Assert.AreEqual(0,stray,"Baked lamp geometry is still in Furnishings; re-run the Blender export");
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
