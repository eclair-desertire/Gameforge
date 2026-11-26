# Экспорт из Blender в движок

## Перед экспортом (чеклист)

- [ ] Масштаб: Unit Scale 1.0, метры; размеры объекта реальные
- [ ] Apply Rotation & Scale (`bpy.ops.object.transform_apply(rotation=True, scale=True)`)
- [ ] Пивот там, где он нужен в игре (низ-центр для пропсов, угол сетки для модулей, между стоп для персонажей)
- [ ] Модификаторы применены (или экспорт с `use_mesh_modifiers=True`)
- [ ] Нормали наружу, нет n-gon’ов в деформируемых местах, нет дублей вершин
- [ ] Один материал = один слот; неиспользуемые слоты удалены
- [ ] UV без перекрытий там, где будет bake/lightmap (второй UV-канал под lightmap для статики в Unity/Unreal)
- [ ] LOD и коллизии названы по правилам движка (ниже)
- [ ] .blend сохранён версией до экспорта

## Нейминг

`SM_` статический меш, `SK_` скелетный, `T_<Asset>_<Map>` текстуры (`_BC` base color, `_N` normal, `_ORM` или `_MS`), `M_` материал, `A_` анимация.

## Unity

- Формат: **FBX** (`bpy.ops.export_scene.fbx`) — `apply_scale_options='FBX_SCALE_ALL'`, `axis_forward='-Z'`, `axis_up='Y'`, `apply_unit_scale=True`, `use_mesh_modifiers=True`, `bake_anim` только для анимаций. В импорте Unity — включить **Bake Axis Conversion**.
- LOD: дочерние меши `<Name>_LOD0`, `_LOD1`, `_LOD2` → Unity создаёт LOD Group автоматически.
- Коллизии: простые меши отдельно, в Unity — Box/Capsule/Mesh Collider (convex) на префабе.
- Материалы URP Lit: Metallic + Smoothness в альфе metallic-карты (Smoothness = 1 − Roughness).
- Персонажи: Rig → Humanoid, проверить Avatar mapping.
- Кладём в `Assets/Art/<Category>/<Asset>/`; после экспорта — `unity recompile`/refresh, проверка в сцене через gameforge:engine-unity.

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
