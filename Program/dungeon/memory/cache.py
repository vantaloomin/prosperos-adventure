"""Byte-bounded process memoization.

Adapted from prosperos-study server/memory/cache.py at bbcbde4. The Study's optional
persistent index backing is omitted; the Dungeon keeps memoization in process only.
"""
import hashlib
import json
import sys
from collections import OrderedDict
from dataclasses import fields, is_dataclass
from functools import wraps
from threading import RLock


def children(value):
    if isinstance(value, dict):
        return (*value.keys(), *value.values())
    if isinstance(value, (tuple, list, set, frozenset)):
        return value
    if is_dataclass(value):
        return tuple(getattr(value, field.name) for field in fields(value))
    return ()


# Values with nothing inside them to visit; sizing them directly keeps a cache miss cheap.
LEAVES = frozenset({str, bytes, int, float, bool, type(None)})


def retained_bytes(value, seen=None):
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    if type(value) in LEAVES:
        return sys.getsizeof(value)
    overhead = sys.getsizeof(vars(value)) if is_dataclass(value) and hasattr(value, '__dict__') else 0
    return sys.getsizeof(value) + overhead + sum(retained_bytes(item, seen) for item in children(value))


class ByteCache:
    def __init__(self, limit):
        self.limit = limit
        self.values = OrderedDict()
        self.bytes = self.hits = self.misses = 0
        self.lock = RLock()

    def get(self, key):
        with self.lock:
            entry = self.values.get(key)
            if entry is None:
                self.misses += 1
                return None
            self.hits += 1
            self.values.move_to_end(key)
            return entry[0]

    def put(self, key, value):
        size = retained_bytes((key, value)) + 192  # OrderedDict entry and bookkeeping allowance.
        with self.lock:
            previous = self.values.pop(key, None)
            self.bytes -= previous[1] if previous else 0
            if size > self.limit:
                return
            while self.values and self.bytes + size > self.limit:
                _, removed = self.values.popitem(last=False)
                self.bytes -= removed[1]
            self.values[key] = (value, size)
            self.bytes += size

    def clear(self):
        with self.lock:
            self.values.clear()
            self.bytes = self.hits = self.misses = 0

    def info(self):
        with self.lock:
            return {'entries': len(self.values), 'bytes': self.bytes, 'limit': self.limit,
                    'hits': self.hits, 'misses': self.misses}


def disk_key(namespace, args, kwargs):
    identity = json.dumps([namespace, args, kwargs], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(identity.encode('utf-8')).hexdigest()


def immutable_text(value):
    # Only the exact immutable argument shapes used by text/chunk compilation.
    # Other JSON-compatible inputs retain the previous canonical identity.
    return type(value) is str or (type(value) is tuple and all(type(item) is str for item in value))


def process_key(namespace, args, kwargs):
    if all(immutable_text(value) for value in (*args, *kwargs.values())):
        return args, tuple(kwargs.items())
    return disk_key(namespace, args, kwargs)


def memoized(namespace, limit):
    cache = ByteCache(limit)

    def decorate(function):
        @wraps(function)
        def call(*args, **kwargs):
            key = process_key(namespace, args, kwargs)
            value = cache.get(key)
            if value is not None:
                return value
            value = function(*args, **kwargs)
            cache.put(key, value)
            return value

        call.cache_clear = cache.clear
        call.cache_info = cache.info
        return call
    return decorate
