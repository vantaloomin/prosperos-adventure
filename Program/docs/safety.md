# Safety: AI notices and crisis help

[Back to the README](../../README.md)

Prospero's Dungeon is a story game with an AI narrator and AI characters who stay in the story. This page says how the app makes clear
that they are AI and what it does when someone may be thinking about hurting themselves. It is published so anyone
can read the protocol the app follows. Everything here runs on your own computer, with rules rather than a model, and
nothing is sent anywhere.

## The characters are AI

- **On first start**, before anything else, the app shows a one-time notice that the characters are AI, that what
  they say is written by an AI model and can be wrong, and that the app is for adults. It can't be dismissed without
  ticking **I'm 18 or older**. Confirming is recorded once in your workspace.
- **Under every message box** a small line says *Characters are AI and can make mistakes.* It shows under the story's
  message box, on a computer and on a phone, the whole time you are playing.
- **The notices come from the app, never from a character.** The narrator never says it is an AI in the story; a
  message starting with `OOC:` or wrapped in ((double parentheses)) gets a plain, honest answer.

## Crisis help

- **What is checked.** Only your own messages in the story. Each one is checked
  against a list of phrases about suicide and self-harm (`Program/dungeon/safety.py`). The narrator's messages are not
  checked, and no model is asked.
- **What happens.** A message that matches gets a note from the app right under it, styled so it is clearly not the
  narrator. It names the 988 Suicide & Crisis Lifeline (call or text **988** in the US), the Crisis Text Line (text
  **HOME** to **741741**), [findahelpline.com](https://findahelpline.com) for other countries, and says to call the
  local emergency number in an emergency.
- **What doesn't happen.** The message is never blocked or changed, the narrator's reply carries on as usual, and
  nothing about it leaves your computer. There is no setting that turns the note off.
- **What the narrator is told.** The Story narrator has no rule about self-harm in the fiction:
  Dungeon's stories are dark fiction for adults with no hard lines beyond adults only, and a character in them may
  come to harm. The crisis note is about the real player's own words, so it is code and shows whatever any prompt
  says.
- **Limits.** A list of phrases misses some ways of saying things and catches some jokes ("this exam makes me want to
  die"). It leans toward showing the note: a false alarm costs one note, a missed one costs much more.

## What the app does not do

The app has no accounts and sends nothing home, so it cannot count how often the note is shown or report it anywhere.
It is not a crisis service and does not replace one.
