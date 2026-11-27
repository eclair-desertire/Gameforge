var root = "Assets/GameForgeTest"; var log = new System.Text.StringBuilder();
var scn = UnityEditor.SceneManagement.EditorSceneManager.OpenScene(root + "/GF_ExportTest.unity", UnityEditor.SceneManagement.OpenSceneMode.Additive);
GameObject human = null, lamp = null, house = null;
foreach (var g in scn.GetRootGameObjects()) { if (g.name.StartsWith("PF_CafeOwner")) human = g; if (g.name.StartsWith("PF_StreetLamp")) lamp = g; if (g.name == "PF_Townhouse") house = g; if (g.name.StartsWith("LOD_Showcase_")) g.GetComponent<LODGroup>().ForceLOD(int.Parse(g.name.Substring(13))); }
human.transform.rotation = Quaternion.Euler(0, -25, 0);
UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(scn);
UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scn);
UnityEditor.ShaderUtil.allowAsyncCompilation = false;   // make sure variants are compiled before Render()
var shots = root + "/Screenshots";
var camGo = new GameObject("GF_ShotCamera"); UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(camGo, scn);
var cam = camGo.AddComponent<Camera>(); cam.scene = scn; cam.nearClipPlane = 0.05f; cam.farClipPlane = 500;
System.Action<string, Vector3, Vector3, float> Shot = (file, pos, target, fov) => {
  cam.transform.position = pos; cam.transform.LookAt(target); cam.fieldOfView = fov;
  var rt = new RenderTexture(1600, 900, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB); rt.antiAliasing = 4;
  cam.targetTexture = rt; cam.Render(); cam.Render();
  RenderTexture.active = rt; var tex = new Texture2D(1600, 900, TextureFormat.RGB24, false); tex.ReadPixels(new Rect(0, 0, 1600, 900), 0, 0); tex.Apply();
  System.IO.File.WriteAllBytes(shots + "/" + file, tex.EncodeToPNG());
  RenderTexture.active = null; cam.targetTexture = null; rt.Release(); UnityEngine.Object.DestroyImmediate(tex);
  log.AppendLine("shot " + file);
};
var hp = human.transform.position;
Shot("01_street_overview.png", new Vector3(12, 3.5f, 16), new Vector3(0, 6, -2), 50);
Shot("02_facade_front.png", new Vector3(0, 7, 26), new Vector3(0, 8.5f, 0), 45);
Shot("03_owner_scale_1m_cube.png", new Vector3(2.4f, 1.3f, 7.5f), new Vector3(2.4f, 1.0f, 2.2f), 35);
Shot("04_owner_closeup.png", hp + human.transform.forward * 1.2f + Vector3.up * 1.8f, hp + Vector3.up * 1.82f, 28);
Shot("05_lamp.png", new Vector3(8.5f, 2.8f, 7.5f), new Vector3(6.6f, 2.6f, 2.55f), 45);
Shot("06_lod0_lod1_lod2.png", new Vector3(-27, 9, 30), new Vector3(-27, 8, -4), 55);
// collider overlay: show UCX hulls / capsule as translucent green
var gm = new Material(Shader.Find("Universal Render Pipeline/Unlit")); gm.SetFloat("_Surface", 1); gm.SetColor("_BaseColor", new Color(0.1f, 1f, 0.2f, 0.45f));
var ut = System.Type.GetType("UnityEditor.Rendering.Universal.ShaderGUI.UnlitShader, Unity.RenderPipelines.Universal.Editor"); if (ut != null) ut.GetMethod("ValidateMaterial").Invoke(System.Activator.CreateInstance(ut, true), new object[]{ gm });
var tmp = new System.Collections.Generic.List<GameObject>();
foreach (var mc in house.GetComponentsInChildren<MeshCollider>()) { var o = new GameObject("viz"); UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(o, scn); o.transform.SetPositionAndRotation(mc.transform.position, mc.transform.rotation); o.AddComponent<MeshFilter>().sharedMesh = mc.sharedMesh; o.AddComponent<MeshRenderer>().sharedMaterial = gm; tmp.Add(o); }
foreach (var mc in lamp.GetComponentsInChildren<MeshCollider>()) { var o = new GameObject("viz"); UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(o, scn); o.transform.SetPositionAndRotation(mc.transform.position, mc.transform.rotation); o.AddComponent<MeshFilter>().sharedMesh = mc.sharedMesh; o.AddComponent<MeshRenderer>().sharedMaterial = gm; tmp.Add(o); }
var cap = GameObject.CreatePrimitive(PrimitiveType.Capsule); UnityEngine.Object.DestroyImmediate(cap.GetComponent<Collider>()); UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(cap, scn); cap.transform.position = hp + Vector3.up; cap.transform.localScale = new Vector3(0.6f, 1f, 0.6f); cap.GetComponent<Renderer>().sharedMaterial = gm; tmp.Add(cap);
Shot("07_colliders_ucx.png", new Vector3(14, 6, 18), new Vector3(0, 7, -3), 55);
foreach (var o in tmp) UnityEngine.Object.DestroyImmediate(o);
// floor-to-floor: repeated raycasts through a temporary non-convex collider on LOD0
var lod0 = house.transform.Find("SM_Townhouse_LOD0").gameObject; var tmc = lod0.AddComponent<MeshCollider>(); Physics.SyncTransforms();
var ys = new System.Collections.Generic.List<float>(); var o2 = new Vector3(0.3f, 16f, -5f); RaycastHit h;
for (int i = 0; i < 20 && tmc.Raycast(new Ray(o2, Vector3.down), out h, 30f); i++) { ys.Add(h.point.y); o2 = h.point + Vector3.down * 0.01f; }
log.AppendLine("LOD0 surfaces hit going down at (0.3,-5): " + string.Join(", ", ys.ConvertAll(y => y.ToString("F2"))));
UnityEngine.Object.DestroyImmediate(tmc);
UnityEngine.Object.DestroyImmediate(camGo);
UnityEditor.ShaderUtil.allowAsyncCompilation = true;
UnityEditor.SceneManagement.EditorSceneManager.CloseScene(scn, true);
UnityEditor.AssetDatabase.Refresh();
return log.ToString();
