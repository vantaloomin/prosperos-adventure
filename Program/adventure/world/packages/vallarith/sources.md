# Sources

Vanta's Vallarith material, from `Vallarith.zip` in the project files (2026-10-21). The originals
are not copied into this public repo. Every entry here is rewritten, and the D&D-derived Hell
material in the deity document (which reads close to wiki text) was summarized in fresh words
rather than carried over.

| File | What it is | Used for | SHA-256 |
| --- | --- | --- | --- |
| `existinglore.json` | 102-entry key/value lorebook | lore.json, settlements, factions, deities | `4e6a8bd71336dac6da257fa8c2897dab47357522e401aa4fbeee5aa8d4b54ed4` |
| `key_ley_information.md` | The Ley and the Source Font, an ontology of magic | canon/the-ley.md (the authority on magic) | `eec0f7a7b8a3b95579423d24c42d657869490c0539b8f331479aacf79f76297b` |
| `known-timeline.md` | History of Vallarith, Age of Dragons to the Reformation | canon/history.md | `af63fb6fdb95bdb9ce3afd744b76650cedc40cc443ba76b18aab084c8e960666` |
| `valla-diety-powers.md` | Fey, New Gods, Old Gods, Eternal Dragons, devils, Brotherhood | deities.json, factions.json | `26c15e3b50df070c3405f390aa28ce44129790ceecd21be07a469827a0f38cb1` |
| `new-gods-profile.docx` | Pre-ascension profiles of the six New Gods, with stories in their own words | personas.json, deities.json, beats.json | `63f9588b11b7f0cdb017bb496161a7e586ad4eb8512beb2832a85b06df69c947` |
| `Vallarith.png` | The Known World map, cropped | assets/maps/vallarith.jpg (reference for map positions) | `db80a79b45e3a43ea76c7adcecbec10616d4824e25d4de1f98d866d4ee5af450` |
| `LeyLine.png` | The Ley Line map, full sheet | assets/maps/ley-line.jpg (downscaled), Ley ratings | `8233424c852295309528642912d06669526e2876dd2c187f4715f2aa0b0e0e07` |
| `KnownWorld082022.png` | The Known World map, full sheet | Not copied (same map as Vallarith.png) | `ddbf51a4439324d4e0b0c07a83b8951a04b62da55e10b3ef56530386f5061a9b` |
| `unknown.png` | The Known World map, teal sea variant | Not copied | `6d59498c098dc8ffd7b335f1c348ebfa99c19aa7ba29ed553ea353f61c543ab1` |

Also used: the Kingswood town from the Milestone 1 slice
(`Program/dungeon/world/data/cities/kingswood.json`, by the "Companion code fork" thread), which is
the authority for Kingswood.

## Which source wins

When the files disagree, this draft prefers, in order: the ley document, the New Gods profiles,
the deity powers document, the timeline, then the lorebook (the oldest). Each call is listed in
[open-questions.md](open-questions.md).
