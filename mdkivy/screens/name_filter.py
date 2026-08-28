"""Player-name screening for the public exhibit.

Names are normalized (lowercased, common leetspeak substitutions
collapsed, separators stripped) and checked against a blocklist of
profanity and slurs. The check is substring-based so embedded and
disguised spellings are caught too.
"""
import re

_SUBS = str.maketrans({
    '0': 'o', '1': 'i', '!': 'i', '3': 'e', '4': 'a', '@': 'a',
    '5': 's', '$': 's', '7': 't', '8': 'b', '9': 'g', '6': 'g',
    '+': 't', '|': 'i',
})

_BLOCKED = (
    'fuck', 'fuk', 'fck', 'fack', 'phuck', 'shit', 'sht', 'bitch', 'btch', 'cunt',
    'cock', 'dick', 'dik', 'penis', 'pussy', 'vagina', 'boob', 'tit',
    'ass', 'arse', 'anus', 'anal', 'sex', 'rape', 'porn', 'cum',
    'semen', 'whore', 'hoe', 'slut', 'fag', 'dyke', 'tranny',
    'nigg', 'niga', 'chink', 'spic', 'kike', 'wetback', 'gook',
    'retard', 'rtard', 'nazi', 'hitler', 'kkk', 'isis',
    'kill', 'murder', 'suicide', 'terror',
    'damn', 'bastard', 'piss', 'wank', 'jerk off', 'blowjob', 'bj',
    'milf', 'thot', 'simp',
)

# avoids blocking names like Cassidy
_WHOLE_WORD_ONLY = {'ass', 'hoe', 'tit', 'cum', 'bj', 'sex', 'kill'}


def _normalize(name):
    n = name.lower().translate(_SUBS)
    n = re.sub(r'[^a-z ]+', '', n)
    return n


def is_clean(name):
    """Return True if the name is acceptable for the public leaderboard."""
    n = _normalize(name)
    collapsed = n.replace(' ', '')
    words = set(n.split())
    for bad in _BLOCKED:
        if bad in _WHOLE_WORD_ONLY:
            if bad in words or collapsed == bad:
                return False
        elif bad in collapsed:
            return False
    return True
