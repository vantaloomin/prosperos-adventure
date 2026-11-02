"""Conservative token estimate copied from prosperos-study server/memory/budget.py at bbcbde4."""
import math


def token_estimate(text: str) -> int:
    return math.ceil(len(text.encode('utf-8')) / 3)
