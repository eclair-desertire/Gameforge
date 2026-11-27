var sb = new System.Text.StringBuilder();
foreach (var p in new[]{"Assets/GameForgeTest/Townhouse/SM_Townhouse.fbx","Assets/GameForgeTest/StreetLamp/SM_StreetLamp.fbx","Assets/GameForgeTest/CafeOwner/SK_CafeOwner.fbx"}) {
  var imp = (UnityEditor.ModelImporter)UnityEditor.AssetImporter.GetAtPath(p);
  sb.AppendLine("== " + p + " bakeAxis=" + imp.bakeAxisConversion + " anim=" + imp.animationType + " lmUV=" + imp.generateSecondaryUV);
  var go = UnityEditor.AssetDatabase.LoadAssetAtPath<GameObject>(p);
  var inst = (GameObject)UnityEngine.Object.Instantiate(go);
  foreach (Transform t in inst.GetComponentsInChildren<Transform>()) {
    if (t.parent != null && t.parent.parent != null) continue;
    var r = t.GetComponent<Renderer>();
    sb.AppendLine("  " + t.name + " rot=" + t.localEulerAngles.ToString("F1") + (r ? " size=" + r.bounds.size.ToString("F2") + " min=" + r.bounds.min.ToString("F2") + " mats=" + string.Join(",", System.Array.ConvertAll(r.sharedMaterials, m => m ? m.name : "null")) : ""));
  }
  var lg = inst.GetComponent<LODGroup>();
  if (lg) foreach (var l in lg.GetLODs()) sb.AppendLine("  LOD h=" + l.screenRelativeTransitionHeight.ToString("F3") + " r=" + string.Join(",", System.Array.ConvertAll(l.renderers, x => x ? x.name : "null")));
  var anim = inst.GetComponent<Animator>();
  if (anim) {
    var av = anim.avatar;
    sb.AppendLine("  avatar=" + (av ? av.name : "none") + " valid=" + (av && av.isValid) + " human=" + (av && av.isHuman));
    if (av && av.isHuman) {
      var hd = imp.humanDescription; sb.AppendLine("  mapped bones=" + hd.human.Length);
      foreach (var hb in hd.human) sb.Append(hb.humanName + "->" + hb.boneName + "; ");
      sb.AppendLine();
      var ft = anim.GetBoneTransform(HumanBodyBones.LeftFoot); var hd2 = anim.GetBoneTransform(HumanBodyBones.Head);
      sb.AppendLine("  hips y=" + anim.GetBoneTransform(HumanBodyBones.Hips).position.y.ToString("F3") + " head y=" + hd2.position.y.ToString("F3") + " foot y=" + ft.position.y.ToString("F3") + " forward(hips)=" + anim.GetBoneTransform(HumanBodyBones.Hips).forward.ToString("F2") + " leftHand x=" + anim.GetBoneTransform(HumanBodyBones.LeftHand).position.x.ToString("F2"));
    }
    float ymin = 1e9f, ymax = -1e9f; float zmin=1e9f, zmax=-1e9f;
    foreach (var smr in inst.GetComponentsInChildren<SkinnedMeshRenderer>()) {
      var m = new Mesh(); smr.BakeMesh(m, true);
      foreach (var v in m.vertices) { var w = smr.transform.TransformPoint(v); ymin = Mathf.Min(ymin, w.y); ymax = Mathf.Max(ymax, w.y); }
      if (smr.name.EndsWith("Eyes")) { foreach (var v in m.vertices) { var w = smr.transform.TransformPoint(v); zmin=Mathf.Min(zmin,w.z); zmax=Mathf.Max(zmax,w.z);} }
    }
    sb.AppendLine("  baked height: ymin=" + ymin.ToString("F3") + " ymax=" + ymax.ToString("F3") + " H=" + (ymax - ymin).ToString("F3") + " eyes z=" + zmin.ToString("F2") + ".." + zmax.ToString("F2"));
  }
  UnityEngine.Object.DestroyImmediate(inst);
}
var mats = UnityEditor.AssetDatabase.FindAssets("t:Material", new[]{"Assets/GameForgeTest"});
int pink = 0; foreach (var g in mats) { var m = UnityEditor.AssetDatabase.LoadAssetAtPath<Material>(UnityEditor.AssetDatabase.GUIDToAssetPath(g)); if (!m.shader.isSupported || m.shader.name.Contains("Error")) pink++; }
sb.AppendLine("materials=" + mats.Length + " unsupported=" + pink);
return sb.ToString();
