---
name: vfx
description: Визуальные эффекты игры — взрывы, огонь, дым, магия, удары, слэши, молнии, порталы, лечение, искры — как спрайтшиты из gameforge-fx (HDR, bloom, гладкий или пиксельный стиль) и как системы частиц в Unity, Godot, Unreal, по принципам тайминга и читаемости. Используй, когда нужны эффекты, «сок» ударов и попаданий, флипбуки, частицы, или эффекты выглядят плоско.
---

# VFX — эффекты, которые «продают» действие

## Перед началом: инструменты

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check-tools.py" --task vfx
```
Итог не «всё готово» → **сначала явно перечисли пользователю, что требуется установить или включить**, и пройди gameforge:doctor (установка только с его согласия). В сессии должны быть инструменты: `mcp__plugin_gameforge_gameforge-fx__*`; прописан, но инструментов нет — сервер не активен (doctor, шаг 5).

Инструмент: **`gameforge-fx`** (встроен в плагин, внешних программ не нужно).

## Принципы (проверяй каждый эффект)
1. **Тайминг: anticipation → impact → dissipation.** Быстрый вход (1–2 кадра), самый яркий кадр — импакт, долгий спад. Хит — 6–10 кадров, взрыв — 14–20, лупы — 16–24.
2. **Форма важнее частиц**: читаемый силуэт на первых кадрах (звезда удара, круг ударной волны, дуга слэша).
3. **Ценность и контраст**: ядро почти белое, по краю насыщенный цвет, затем тёмный дым. Эффект контрастен фону уровня.
4. **Цвет = смысл**: огонь/урон — тёплые, лечение — зелёные, магия — цвет школы/персонажа; цвета из палитры проекта (`fx_palette`).
5. **Масштаб и длительность под геймплей**: эффект не закрывает врагов и снаряды; частые эффекты короче и тише.
6. **Слои**: флипбук + частицы движка (искры, обломки) + свет + звук + тряска камеры/хит-стоп (gameforge:polish).

## Флипбуки через fx_effect
```
fx_effect kind=explosion out_dir=Assets/Art/VFX name=explosion_small size=128 seed=3
fx_effect kind=magic colors=["#8a4dff"] style=pixel pixel=4 outline=auto out_dir=art/vfx
fx_effect kind=fire loop=true background=black   # для additive-материала
```
- Виды: explosion, fire, smoke, magic, slash, hit, lightning, portal, heal, sparkle.
- `style=pixel` — одна ограниченная палитра на все кадры, жёсткая альфа, sel-out; размер кадра = size/pixel. Можно передать палитру игры: `palette="art/palette.gpl"`.
- **Обязательно посмотри превью** и итерируй: `seed` (другая форма), `colors`, `intensity`, `frames`, `bloom`. Сравни 3 варианта и выбери лучший, прежде чем показывать пользователю.
- Доводка: `post=[{"op":"grade","saturation":1.2}]`, `fx_post` (glow, outline), GIF для devlog — `fx_sheet action=gif`.

## В движке
| Движок | Флипбук | Частицы |
|--------|---------|---------|
| Unity | Sprite Mode Multiple → Slice Grid by Cell Size; Particle System → Texture Sheet Animation (Tiles X/Y из .json), материал URP Particles Unlit, Blend Additive (для `background=black`) или Alpha | Shuriken / VFX Graph; искры — Trails; свет — Light2D/URP point light с кривой интенсивности |
| Godot | `AnimatedSprite2D`/`Sprite2D` hframes/vframes; для частиц `CanvasItemMaterial` → Particles Animation (H/V Frames), Blend Mode Add | GPUParticles2D/3D, `ParticleProcessMaterial`; one_shot для взрывов |
| Unreal | Niagara: SubUV Animation (Sub Image Size), материал Translucent/Additive | Niagara emitters, Light Renderer |

Пул эффектов (object pooling), лимит одновременных, LOD для mobile; overdraw — главный враг производительности на mobile (крупные прозрачные кадры → меньше размер, меньше слоёв).

## Готово, когда
Эффект проверен в игре на реальном фоне, синхронизирован со звуком (gameforge:audio), не роняет FPS ниже бюджета (gameforge:polish), файлы и параметры (seed, colors) записаны в `.gameforge/art/vfx.md`, чтобы перегенерировать в том же стиле.
