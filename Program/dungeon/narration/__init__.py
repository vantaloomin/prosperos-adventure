"""The narrator: its layered prompt (prompt.py) and the checks run on what it writes (prose.py).

Code decides and the model narrates. The prompt tells the narrator how to write a turn from facts the
code already settled, and prose.py checks the result before the player sees it, so the rules that can be
checked mechanically (no em dashes, the blocklist, dialogue echoes) do not depend on the model obeying.
The sources are Vanta's three writing documents, kept verbatim in the project files under
dungeon/prompting/; docs/requirements.md ("Narrator prompting") says how they were adapted.
"""
