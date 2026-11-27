# Экспорт из Blender в движок

## Перед экспортом (чеклист)

- [ ] Масштаб: Unit Scale 1.0, метры; размеры объекта реальные
- [ ] Apply Rotation & Scale (`bpy.ops.object.transform_apply(rotation=True, scale=True)`)
- [ ] Пивот там, где он нужен в игре (низ-центр для пропсов, угол сетки для модулей, между стоп для персонажей)
- [ ] Экспорт из **отдельной коллекции экспортных копий** (`GF_EXPORT_<Asset>`: `bpy.data.meshes.new_from_object(ob.evaluated_get(depsgraph))`), а не применением модификаторов на рабочих объектах — исходник остаётся неразрушенным, текст (FONT) превращается в меш, отрицательный scale учитывается
- [ ] Нормали наружу, нет n-gon’ов в деформируемых местах, нет дублей вершин
- [ ] Один материал = один слот; неиспользуемые слоты удалены
- [ ] UV есть у всех мешей. Для **тайловых** материалов (стены, кровля, мостовая) — box-UV в метрах: `UV = координата / размер тайла материала`, тайлинг в движке = 1 (Smart UV сожмёт стену в 0–1 и растянет текстуру). Smart UV / ручная развёртка — только для уникальных текстур и бейка
- [ ] Lightmap UV: для Unity проще и надёжнее `generateSecondaryUV = true` на импортёре, чем второй UV-канал из Blender; для Unreal — второй канал или Generate Lightmap UVs
- [ ] LOD и коллизии названы по правилам движка (ниже)
- [ ] .blend сохранён версией до экспорта

## Нейминг

`SM_` статический меш, `SK_` скелетный, `T_<Asset>_<Map>` текстуры (`_BC` base color, `_N` normal, `_ORM` или `_MS`), `M_` материал, `A_` анимация.

## Unity (проверено: Unity 6000.6, URP, FBX)

**Экспорт FBX** (`bpy.ops.export_scene.fbx`):
```python
dict(use_selection=True, object_types={"MESH", "ARMATURE", "EMPTY"},
     apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y", apply_unit_scale=True,
     use_mesh_modifiers=True, mesh_smooth_type="OFF", add_leaf_bones=False,
     primary_bone_axis="Y", secondary_bone_axis="X", bake_anim=False,
     path_mode="STRIP", embed_textures=False,          # текстуры кладём рядом: <Asset>/Textures/
     bake_space_transform=not is_rig)                  # статика: True; риг: False
```
**Оси (проверено перебором 4 комбинаций):** в импортёре Unity **Bake Axis Conversion = OFF** (с ним модели разворачиваются на 180° и смотрят в −Z). Статика с `bake_space_transform=True` → корень (0,0,0), фасад в +Z. Риг с `bake_space_transform=False` → на узле арматуры 270° по X (норма для Blender-ригов), лицо в +Z, Humanoid валиден. Модель Blender «смотрит» в −Y.

**Материалы — FBX переносит мало.** Доходят только текстура, подключённая **напрямую** Image → Base Color, и Normal Map. Теряются: тонировка через Mix/MixRGB, node groups (кожа MPFB, все составные шейдеры), Metallic, Emission, процедурные текстуры. Рабочий рецепт: Blender пишет манифест материалов (`gf_materials.json`: base map + tint, normal, metallic/roughness, alpha, emission), Unity-скрипт создаёт **URP Lit** и делает `ModelImporter.AddRemap` на них. MS-карта: R = metallic, A = 1 − roughness, PNG non-color, при назначенной карте `_Smoothness = 1`. После установки свойств URP-материала вызвать `LitShader.ValidateMaterial` (через reflection), иначе не выставятся ключевые слова (alpha clip, emission). Глаза/волосы/брови/ресницы MPFB: вход Alpha связан → alpha clip 0.5, двусторонние.

**Импортёр** — настраивать **до первого импорта** в `AssetPostprocessor.OnPreprocessModel` по префиксам: `SM_` — `bakeAxisConversion=false`, `generateSecondaryUV=true`; `SK_` — плюс `animationType = Human`. Если у Humanoid-модели меняли оси/масштаб — сбросить `humanDescription = new HumanDescription()` + `autoGenerateAvatarMappingIfUnspecified = true`, иначе Unity держит старый скелет и сыплет «Avatar Rig Configuration mis-match».

**LOD:** дочерние меши `<Name>_LOD0/_LOD1/_LOD2` → LOD Group создаётся сам. Для LOD2 — непрозрачный тёмный «оконный» материал вместо стекла с интерьером.

**Коллизии:** `UCX_<Mesh>_NN` (выпуклая оболочка, `bmesh.ops.convex_hull`) в том же FBX. **Unity этот префикс не понимает** — нужен `AssetPostprocessor.OnPostprocessModel` или шаг сборки префаба: MeshCollider (convex) + удалить MeshRenderer/MeshFilter. LODGroup такие меши игнорирует. Персонажу — CapsuleCollider/CharacterController на префабе.

**Проверка без Unity MCP** (через `unity command`/editor-скрипт): тестовая сцена открывается аддитивно (сцены пользователя не трогаем); скриншот — `Camera.Render()` в RenderTexture с `camera.scene = <тестовая сцена>` и `ShaderUtil.allowAsyncCompilation = false` (иначе розовые материалы на снимке); LOD — `LODGroup.ForceLOD(i)` по уровню на снимок; коллизии — `Physics.SyncTransforms()` + Raycast/CapsuleCast; рост скелетного меша — `SkinnedMeshRenderer.BakeMesh`, не `bounds`; `avatar.isValid && avatar.isHuman`, число сопоставленных костей, консоль без «Rig Error».

**Готовые скрипты:** `../examples/export_unity/` — экспорт (экспортные копии, box-UV, LOD, UCX, подготовка MPFB, манифест материалов) и Unity-скрипты (импорт и материалы, префабы с коллайдерами, тестовая сцена, скриншоты, проверки).

Кладём в `Assets/Art/<Category>/<Asset>/` (текстуры в `Textures/`); проверка в сцене — gameforge:engine-unity.

## Godot

- Формат: **glTF 2.0 binary (.glb)** (`bpy.ops.export_scene.gltf(export_format='GLB')`) — родной формат Godot. Можно класть и `.blend` прямо в проект (Godot импортирует через Blender, нужен путь к Blender в настройках редактора).
- Суффиксы имён при импорте: `-col` (меш + коллизия), `-convcol`, `-colonly` (только коллизия), `-noimp` (не импортировать), `-navmesh`, `-rigid`.
- LOD Godot генерирует сам при импорте (mesh LOD), ручные LOD — не обязательны.
- Материалы: ORM упаковка поддерживается в StandardMaterial3D.

## Unreal

- Формат: **FBX** (или glTF / USD в UE 5.x); сцена в метрах — UE при импорте переводит в сантиметры корректно. Forward X, Up Z по умолчанию FBX из Blender подходит; проверь, что персонаж смотрит в +X.
- Коллизии: `UCX_<MeshName>_00` (выпуклые), `UBX_` (бокс), `USP_` (сфера), `UCP_` (капсула) — в одном FBX с мешем.
- LOD: `<Name>_LOD0…` в группе LOD или импорт LOD отдельно; Nanite для высокополигональной статики (pc) — тогда LOD не нужны, но нужна оптимизация под Lumen.
- Текстуры: ORM (R=AO, G=Roughness, B=Metallic), normal — DirectX (в Blender OpenGL → инвертировать G при запекании или флажок Flip Green в UE).
- Персонажи: проверить совместимость скелета с UE Mannequin для ретаргета (IK Retargeter).

## Пакетный экспорт (без GUI)

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b art/blender/building_kit.blend \
  --python art/blender/scripts/export_kit.py -- --engine unity --out "<проект>/Assets/Art/Buildings"
```

Скрипт экспорта храни в проекте — повторный экспорт после правок должен быть одной командой.

## Проверка в движке (обязательно)

Скриншот из движка рядом с рендером Blender: масштаб (рядом стандартный персонаж/куб 1 м), материалы и нормали, LOD переключаются на дистанции, коллизии (персонаж не проходит сквозь, не застревает), для скелетных — анимация без разрывов.
