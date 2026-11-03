# 5E SRD 5.2.1 content pack

The full content of the System Reference Document 5.2.1 as structured data, for the 5e ruleset module (Milestone 4).
It is 5E compatible.

## Attribution

This work includes material from the System Reference Document 5.2.1 ("SRD 5.2.1") by Wizards of the Coast LLC,
available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative Commons Attribution 4.0
International License, available at https://creativecommons.org/licenses/by/4.0/legalcode.

The app shows this attribution wherever the pack's content is credited. `pack.json` holds the same sentence under
`license.attribution`, and the test checks it word for word.

## Changes from the source

- Converted from the PDF to JSON. The rules text is kept as Markdown, unchanged apart from the items below.
- The publisher's game trademark is removed from one sentence in Playing the Game.
- Fields that are not in the source are added: ids, parsed numbers (prices in copper, weights, dice, attacks and
  saves), `shop_types`, `legality`, magic item `value_cp`, and the wage classes in `economy.json`.
- One printing error is corrected (Young White Dragon's Intelligence save). `pack.json` lists it under
  `corrections`, and lists the source's other errors, left as printed, under `source_notes`.

## Files

| File | Contents |
|---|---|
| `pack.json` | Manifest: source and hash, license, outcome mapping, pricing rules, corrections, file counts |
| `classes.json` | 12 classes: core traits, level table, features, spell lists, one subclass each |
| `species.json` | 9 species and their traits |
| `backgrounds.json` | 4 backgrounds: ability scores, feat, skills, tool, equipment |
| `feats.json` | 17 feats by category |
| `spells.json` | 339 spells with parsed casting time, range, components, duration, saves and damage |
| `equipment.json` | Weapons, armor, tools, gear, mounts and vehicles with prices in copper and shop types; equipment rules |
| `economy.json` | Coins, lifestyles, food, drink and lodging, hirelings, spellcasting services, scroll scribing, wage classes |
| `magic_items.json` | 258 magic items: rarity, attunement, charges, variants, value in copper |
| `monsters.json` | 330 stat blocks (monsters and animals) with parsed attacks, saves, spellcasting and legendary actions |
| `rules.json` | Playing the Game, Character Creation, Rules Glossary, Gameplay Toolbox, magic item and monster rules; conditions, skills, actions, damage types, XP tables, poisons, traps and the indexed rules tables |

## How a d20 lands on the outcome ladder

Pass/fail as written. A test that meets the DC is `success`, otherwise `failure`. A natural 20 or 1 is
`critical_success` or `critical_failure` only on attack rolls and death saving throws. The middle bands
(`failure_upside`, `success_cost`) are not used by this ruleset.

## Regenerating

The extractor lives in `scripts/srd52_extract/` and needs PyMuPDF. From `Program/`:

```
python scripts/srd52_extract/lin.py SRD_CC_v5.2.1.pdf lines.json
python scripts/srd52_extract/build.py lines.json dungeon/rules/packs/srd52
```

The PDF must match the SHA-256 in `pack.json`.
