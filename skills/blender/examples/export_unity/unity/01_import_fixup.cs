// GameForge: import fix-up for Blender FBX -> URP (driven by gf_materials.json from export_unity.py)
var root = "Assets/GameForgeTest"; UnityEditor.AssetDatabase.DeleteAsset(root + "/_AxisTest"); UnityEditor.AssetDatabase.Refresh();
var log = new System.Text.StringBuilder();
var json = System.IO.File.ReadAllText(root + "/gf_materials.json");
// tiny parse via MiniJSON-like approach: use UnityEngine.JsonUtility with wrapper types is not available in eval; parse manually with System.Text.Json? -> try Unity's internal Json
var parsed = (System.Collections.Generic.Dictionary<string, object>)typeof(UnityEditor.EditorWindow).Assembly.GetType("UnityEditor.Json").GetMethod("Deserialize", new[]{typeof(string)}).Invoke(null, new object[]{json});
var list = (System.Collections.Generic.List<object>)parsed["materials"];
System.Func<object, float> F = o => System.Convert.ToSingle(o);
// 1) texture importers
foreach (var g in UnityEditor.AssetDatabase.FindAssets("t:Texture2D", new[]{root})) {
  var p = UnityEditor.AssetDatabase.GUIDToAssetPath(g);
  var ti = (UnityEditor.TextureImporter)UnityEditor.AssetImporter.GetAtPath(p);
  bool ch = false; var f = System.IO.Path.GetFileName(p);
  if ((f.Contains("_nor_gl") || f.Contains("_normal")) && ti.textureType != UnityEditor.TextureImporterType.NormalMap) { ti.textureType = UnityEditor.TextureImporterType.NormalMap; ch = true; }
  if (f.Contains("_MS") && ti.sRGBTexture) { ti.sRGBTexture = false; ch = true; }
  if ((f.StartsWith("short02") || f.StartsWith("eyebrow") || f.StartsWith("eyelashes")) && !ti.alphaIsTransparency) { ti.alphaIsTransparency = true; ch = true; }
  if (ch) { ti.SaveAndReimport(); log.AppendLine("tex " + f); }
}
// 2) URP Lit materials
var litShader = Shader.Find("Universal Render Pipeline/Lit");
var litGuiT = System.Type.GetType("UnityEditor.Rendering.Universal.ShaderGUI.LitShader, Unity.RenderPipelines.Universal.Editor");
object litGui = litGuiT != null ? System.Activator.CreateInstance(litGuiT, true) : null;
var remap = new System.Collections.Generic.Dictionary<string, System.Collections.Generic.Dictionary<string, Material>>();
foreach (System.Collections.Generic.Dictionary<string, object> e in list) {
  var name = (string)e["name"]; var asset = (string)e["asset"];
  var dir = root + "/" + asset + "/Materials";
  if (!UnityEditor.AssetDatabase.IsValidFolder(dir)) UnityEditor.AssetDatabase.CreateFolder(root + "/" + asset, "Materials");
  var mpath = dir + "/M_" + name.Replace("GF_Human_", "").Replace("GF_", "").Replace(".", "_") + ".mat";
  var m = UnityEditor.AssetDatabase.LoadAssetAtPath<Material>(mpath);
  if (!m) { m = new Material(litShader); UnityEditor.AssetDatabase.CreateAsset(m, mpath); }
  m.shader = litShader;
  var c = (System.Collections.Generic.List<object>)e["color"];
  m.SetColor("_BaseColor", new Color(F(c[0]), F(c[1]), F(c[2]), F(c[3])));
  System.Func<string, Texture2D> T = n => UnityEditor.AssetDatabase.LoadAssetAtPath<Texture2D>(root + "/" + asset + "/Textures/" + n);
  if (e.ContainsKey("baseMap")) m.SetTexture("_BaseMap", T((string)e["baseMap"]));
  if (e.ContainsKey("normalMap")) { m.SetTexture("_BumpMap", T((string)e["normalMap"])); m.SetFloat("_BumpScale", F(e["normalScale"])); }
  m.SetFloat("_Metallic", F(e["metallic"]));
  if (e.ContainsKey("metallicGlossMap")) { m.SetTexture("_MetallicGlossMap", T((string)e["metallicGlossMap"])); m.SetFloat("_Smoothness", 1f); }
  else m.SetFloat("_Smoothness", Mathf.Clamp01(F(e["smoothness"])));
  if (e.ContainsKey("transparent")) { m.SetFloat("_Surface", 1); m.SetFloat("_Blend", 0); }
  if (e.ContainsKey("alphaClip")) { m.SetFloat("_AlphaClip", 1); m.SetFloat("_Cutoff", F(e["alphaClip"])); }
  if (e.ContainsKey("doubleSided")) m.SetFloat("_Cull", 0);
  if (e.ContainsKey("emission")) { var em = (System.Collections.Generic.List<object>)e["emission"]; m.SetColor("_EmissionColor", new Color(F(em[0]), F(em[1]), F(em[2]))); m.EnableKeyword("_EMISSION"); m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.BakedEmissive; }
  if (litGui != null) litGuiT.GetMethod("ValidateMaterial").Invoke(litGui, new object[]{ m });
  if (e.ContainsKey("emission")) m.EnableKeyword("_EMISSION");
  UnityEditor.EditorUtility.SetDirty(m);
  if (!remap.ContainsKey(asset)) remap[asset] = new System.Collections.Generic.Dictionary<string, Material>();
  remap[asset][name] = m;
}
UnityEditor.AssetDatabase.SaveAssets();
log.AppendLine("materials " + list.Count + " litGui=" + (litGui != null));
// 3) model importers
var models = new System.Collections.Generic.Dictionary<string, string>{{"Townhouse","Townhouse/SM_Townhouse.fbx"},{"StreetLamp","StreetLamp/SM_StreetLamp.fbx"},{"CafeOwner","CafeOwner/SK_CafeOwner.fbx"}};
foreach (var kv in models) {
  var p = root + "/" + kv.Value;
  var mi = (UnityEditor.ModelImporter)UnityEditor.AssetImporter.GetAtPath(p);
  mi.bakeAxisConversion = false; // Blender FBX (-Z fwd, Y up): ON turns models 180° to face -Z
  if (kv.Key == "CafeOwner") { mi.animationType = UnityEditor.ModelImporterAnimationType.Human; mi.avatarSetup = UnityEditor.ModelImporterAvatarSetup.CreateFromThisModel; mi.importAnimation = false;
    mi.humanDescription = new HumanDescription(); mi.autoGenerateAvatarMappingIfUnspecified = true; } // drop stale skeleton (else "Avatar Rig Configuration mis-match" after axis changes)
  else { mi.generateSecondaryUV = true; mi.importAnimation = false; mi.animationType = UnityEditor.ModelImporterAnimationType.None; }
  foreach (var r in remap[kv.Key]) mi.AddRemap(new UnityEditor.AssetImporter.SourceAssetIdentifier(typeof(Material), r.Key), r.Value);
  mi.SaveAndReimport();
  log.AppendLine("model " + kv.Key + " reimported");
}
return log.ToString();
