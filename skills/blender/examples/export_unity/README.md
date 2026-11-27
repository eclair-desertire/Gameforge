# Пример: экспорт Blender → Unity (URP), проверенный в живом проекте

Экспортирует три ассета сцены `../street/` — дом (`SM_Townhouse`, LOD0–2, UCX-коллизии), фонарь (`SM_StreetLamp`) и персонажа MPFB (`SK_CafeOwner`, Humanoid) — и собирает их в Unity. Результат прогона: LOD Group на 3 уровня, коллизии работают, Humanoid-аватар валиден (52 кости сопоставились автоматически), материалы URP Lit с текстурами.

| Файл | Что делает |
|------|-----------|
| `export_unity.py` | Blender, пакетно: экспортные копии (`GF_EXPORT_*`) из вычисленных мешей, box-UV в метрах по размеру тайла (`gf_pbr.size`), LOD, UCX-оболочки, подготовка MPFB (запечь shape keys, убрать subsurf, применить Mask, T-поза), FBX, манифест материалов `gf_materials.json`, MS-карты из roughness |
| `axis_variants.py` | перебор комбинаций осей FBX ↔ Unity (так нашли правильную) |
| `unity/01_import_fixup.cs` | импортёр (оси, Humanoid, lightmap UV), URP Lit-материалы из манифеста, `AddRemap` |
| `unity/02_prefabs_scene_physics_shots.cs` | префабы (`UCX_` → convex MeshCollider), тестовая сцена, проверки физики |
| `unity/03_shots_sync_compile.cs` | скриншоты камерой с синхронной компиляцией шейдеров, `ForceLOD` |
| `unity/04_probe.cs` | диагностика: оси корня, размеры, LOD, аватар, материалы |

**Запуск**
```bash
/Applications/Blender.app/Contents/MacOS/Blender -b ~/Documents/GameForge-examples/export_test.blend \
  --python export_unity.py -- "<UnityProject>/Assets/GameForgeTest"
```
Скрипт работает только с копией `export_test.blend` (защита от порчи исходника). Unity-скрипты — через `unity command … script eval "$(cat unity/01_import_fixup.cs)"` (корень `Assets/GameForgeTest` задан в первой строке каждого файла).

Это пример под конкретную сцену; для своего проекта перенеси функции (`bake`, `box_uv`, `hull`, `export`, манифест) в `art/blender/scripts/` и Unity-часть — в `Assets/Editor/` как `AssetPostprocessor`.
