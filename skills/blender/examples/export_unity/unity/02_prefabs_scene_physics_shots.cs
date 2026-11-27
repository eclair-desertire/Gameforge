// GameForge: prefabs (UCX_ -> convex MeshCollider), test scene, physics checks, camera screenshots
var root = "Assets/GameForgeTest";
var log = new System.Text.StringBuilder();
// ---------- prefabs
System.Func<string, string, GameObject> MakePrefab = (model, prefabPath) => {
  var src = UnityEditor.AssetDatabase.LoadAssetAtPath<GameObject>(model);
  var inst = (GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(src);
  int n = 0;
  foreach (var mf in inst.GetComponentsInChildren<MeshFilter>(true)) {
    if (!mf.name.StartsWith("UCX_")) continue;
    var mc = mf.gameObject.AddComponent<MeshCollider>(); mc.sharedMesh = mf.sharedMesh; mc.convex = true;
    UnityEngine.Object.DestroyImmediate(mf.GetComponent<MeshRenderer>()); UnityEngine.Object.DestroyImmediate(mf);
    n++;
  }
  if (inst.GetComponent<Animator>()) { var cc = inst.AddComponent<CapsuleCollider>(); cc.height = 2.0f; cc.radius = 0.3f; cc.center = new Vector3(0, 1.0f, 0); n++; }
  var pf = UnityEditor.PrefabUtility.SaveAsPrefabAsset(inst, prefabPath);
  UnityEngine.Object.DestroyImmediate(inst);
  log.AppendLine("prefab " + prefabPath + " colliders=" + n);
  return pf;
};
var pHouse = MakePrefab(root + "/Townhouse/SM_Townhouse.fbx", root + "/Townhouse/PF_Townhouse.prefab");
var pLamp = MakePrefab(root + "/StreetLamp/SM_StreetLamp.fbx", root + "/StreetLamp/PF_StreetLamp.prefab");
var pHuman = MakePrefab(root + "/CafeOwner/SK_CafeOwner.fbx", root + "/CafeOwner/PF_CafeOwner.prefab");
// ---------- test scene (additive, so the user's open scene is untouched)
var scenePath = root + "/GF_ExportTest.unity";
var scn = UnityEditor.SceneManagement.EditorSceneManager.NewScene(UnityEditor.SceneManagement.NewSceneSetup.EmptyScene, UnityEditor.SceneManagement.NewSceneMode.Additive);
var prevActive = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
UnityEngine.SceneManagement.SceneManager.SetActiveScene(scn);
var sun = new GameObject("Sun"); var l = sun.AddComponent<Light>(); l.type = LightType.Directional; l.intensity = 1.6f; l.color = new Color(1f, 0.96f, 0.9f); l.shadows = LightShadows.Soft; sun.transform.rotation = Quaternion.Euler(42, 150, 0);
var ground = GameObject.CreatePrimitive(PrimitiveType.Cube); ground.name = "Ground"; ground.transform.localScale = new Vector3(60, 0.1f, 60); ground.transform.position = new Vector3(0, -0.05f, 0);
var gmat = new Material(Shader.Find("Universal Render Pipeline/Lit")); gmat.SetColor("_BaseColor", new Color(0.35f, 0.34f, 0.33f)); gmat.SetFloat("_Smoothness", 0.2f);
UnityEditor.AssetDatabase.CreateAsset(gmat, root + "/M_TestGround.mat"); ground.GetComponent<Renderer>().sharedMaterial = gmat;
var cube = GameObject.CreatePrimitive(PrimitiveType.Cube); cube.name = "Ref_Cube_1m"; cube.transform.position = new Vector3(3.2f, 0.5f, 2.2f);
var cmat = new Material(Shader.Find("Universal Render Pipeline/Lit")); cmat.SetColor("_BaseColor", new Color(0.9f, 0.45f, 0.1f)); UnityEditor.AssetDatabase.CreateAsset(cmat, root + "/M_TestRefCube.mat"); cube.GetComponent<Renderer>().sharedMaterial = cmat;
// Blender (x,y,z) -> Unity (-x, z, -y): lamp (-6.6,-2.55) -> (6.6, 2.55); owner (-1.35,-1.25), rotZ -28 -> (1.35, 1.25)
var house = (GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(pHouse, scn);
var lamp = (GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(pLamp, scn); lamp.transform.position = new Vector3(6.6f, 0, 2.55f);
var human = (GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(pHuman, scn); human.transform.position = new Vector3(1.6f, 0.02f, 2.2f); human.transform.rotation = Quaternion.Euler(0, 200, 0);
// LOD showcase row (forced LODs), far to the side
for (int i = 0; i < 3; i++) { var h = (GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(pHouse, scn); h.name = "LOD_Showcase_" + i; h.transform.position = new Vector3(-40 + i * 13, 0, 0); h.GetComponent<LODGroup>().ForceLOD(i); }
UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scn, scenePath);
// ---------- physics checks
Physics.SyncTransforms();
RaycastHit hit;
System.Func<Vector3, Vector3, string> Ray = (o, d) => Physics.Raycast(o, d, out hit, 50f) ? (hit.collider.name + " @ " + hit.point.ToString("F2")) : "MISS";
log.AppendLine("ray wall  (0,1.5,8)->-Z : " + Ray(new Vector3(0, 1.5f, 8), Vector3.back));
log.AppendLine("ray steps (0,0.3,8)->-Z : " + Ray(new Vector3(0, 0.3f, 8), Vector3.back));
log.AppendLine("ray roof  (0,30,-5)->-Y : " + Ray(new Vector3(0, 30, -5), Vector3.down));
log.AppendLine("ray lamp  (6.6,1,8)->-Z : " + Ray(new Vector3(6.6f, 1, 8), Vector3.back));
log.AppendLine("ray lampH (6.6,4.4,8)->-Z: " + Ray(new Vector3(6.6f, 4.4f, 8), Vector3.back));
log.AppendLine("capsule sweep toward wall: " + (Physics.CapsuleCast(new Vector3(-2, 0.4f, 8), new Vector3(-2, 1.6f, 8), 0.3f, Vector3.back, out hit, 20f) ? hit.collider.name + " dist=" + hit.distance.ToString("F2") : "MISS"));
// floor-to-floor height: temporary non-convex collider on LOD0
var lod0 = house.transform.Find("SM_Townhouse_LOD0").gameObject; var tmc = lod0.AddComponent<MeshCollider>(); Physics.SyncTransforms();
var ys = new System.Collections.Generic.List<float>();
foreach (var h2 in Physics.RaycastAll(new Vector3(0.3f, 13.8f, -5f), Vector3.down, 20f)) if (h2.collider == tmc) ys.Add(h2.point.y);
ys.Sort(); log.AppendLine("LOD0 horizontal surfaces under (0.3,-5): " + string.Join(", ", ys.ConvertAll(y => y.ToString("F2"))));
UnityEngine.Object.DestroyImmediate(tmc);
// ---------- screenshots (camera render, only this scene)
var shots = root + "/Screenshots"; if (!UnityEditor.AssetDatabase.IsValidFolder(shots)) UnityEditor.AssetDatabase.CreateFolder(root, "Screenshots");
var camGo = new GameObject("GF_ShotCamera"); UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(camGo, scn);
var cam = camGo.AddComponent<Camera>(); cam.scene = scn; cam.clearFlags = CameraClearFlags.Skybox; cam.nearClipPlane = 0.05f; cam.farClipPlane = 500;
System.Action<string, Vector3, Vector3, float> Shot = (file, pos, target, fov) => {
  cam.transform.position = pos; cam.transform.LookAt(target); cam.fieldOfView = fov;
  var rt = new RenderTexture(1600, 900, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB); rt.antiAliasing = 4;
  cam.targetTexture = rt; cam.Render();
  RenderTexture.active = rt; var tex = new Texture2D(1600, 900, TextureFormat.RGB24, false); tex.ReadPixels(new Rect(0, 0, 1600, 900), 0, 0); tex.Apply();
  System.IO.File.WriteAllBytes(shots + "/" + file, tex.EncodeToPNG());
  RenderTexture.active = null; cam.targetTexture = null; rt.Release(); UnityEngine.Object.DestroyImmediate(tex);
  log.AppendLine("shot " + file);
};
Shot("01_street_overview.png", new Vector3(12, 3.5f, 16), new Vector3(0, 6, -2), 50);
Shot("02_facade_front.png", new Vector3(0, 7, 24), new Vector3(0, 8, 0), 45);
Shot("03_owner_scale_1m_cube.png", new Vector3(2.6f, 1.4f, 6.5f), new Vector3(2.3f, 1.0f, 2.2f), 35);
Shot("04_owner_closeup.png", human.transform.position + human.transform.forward * 1.3f + Vector3.up * 1.75f, human.transform.position + Vector3.up * 1.75f, 30);
Shot("05_lamp.png", new Vector3(8.5f, 2.8f, 7.5f), new Vector3(6.6f, 2.6f, 2.55f), 45);
Shot("06_lod0_lod1_lod2.png", new Vector3(-27, 9, 30), new Vector3(-27, 8, -4), 55);
UnityEngine.Object.DestroyImmediate(camGo);
UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scn, scenePath);
UnityEngine.SceneManagement.SceneManager.SetActiveScene(prevActive);
UnityEditor.SceneManagement.EditorSceneManager.CloseScene(scn, true);
UnityEditor.AssetDatabase.Refresh();
return log.ToString();
