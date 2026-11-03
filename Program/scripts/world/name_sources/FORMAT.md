# Name source files

One file per culture, read by `scripts/world/given_names.py`. Plain text, UTF-8.

```
# id: korea
# name: South Korea
# source: Statistics Korea and press round-ups of popular names, from general knowledge
# estimate: yes
surnames: Kim Lee Park Choi Jung ...
1950s F: Young-ja Jung-ja Soon-ja ...
1950s M: Young-soo Young-ho ...
2009-2013 F: ...
```

- Header lines start with `# key: value`. `estimate: yes` marks lists written from general knowledge rather
  than copied from an official table; `estimate-from: 2009` marks only cohorts from that year on as estimates.
- `surnames:` lists the most common family names, most common first (may be omitted for a culture whose
  people take family names from the city's name group, such as the United States).
- Each cohort line is `<period> F:` or `<period> M:` followed by given names, most popular first. A period is a
  decade (`1950s`), a range (`2009-2013`) or one year (`1994`).
- Names are separated by spaces; write a space inside a name as `_` (`Mary_Ann`). Hyphens stay as they are.
- Write names in their usual romanised spelling without diacritics (Jose, Zofia, Helene, Thi), as people
  would type them on an English keyboard.
- Never include a name from `invented.txt`; tests reject any overlap.
