##############################################################################
#
# Copyright (c) 2001, 2002 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################

import re

from .exc import LanguageError
from .utils import descriptorint
from .utils import descriptorstr
from .namespaces import XMLNS_NS

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

try:
    # optional library: `zope.interface`
    import interfaces
    import zope.interface
except ImportError:
    interfaces = None


NAME = r"[a-zA-Z_][-a-zA-Z0-9_]*"
DEFINE_RE = re.compile(r"(?s)\s*(?:(global|local)\s+)?" +
                       r"(%s|\(%s(?:,\s*%s)*\))\s+(.*)\Z" % (NAME, NAME, NAME))
SUBST_RE = re.compile(r"\s*(?:(text|structure)\s+)?(.*)\Z", re.S)
ATTR_RE = re.compile(r"\s*([^\s]+)\s+([^\s].*)\Z", re.S)

ENTITY_RE = re.compile(r'(&(#?)(x?)(\d{1,5}|\w{1,8});)')

WHITELIST = frozenset([
    "define",
    "condition",
    "content",
    "replace",
    "repeat",
    "attributes",
    "on-error",
    "omit-tag",
    "script",
    "switch",
    "case",
    ])


def split_parts(arg):
    # Break in pieces at undoubled semicolons and
    # change double semicolons to singles:
    arg = ENTITY_RE.sub(r'\1;', arg)
    arg = arg.replace(";;", "\0")
    parts = arg.split(';')
    parts = [p.replace("\0", ";") for p in parts]
    if len(parts) > 1 and not parts[-1].strip():
        del parts[-1]  # It ended in a semicolon
    return parts


def parse_attributes(clause):
    attrs = {}
    for part in split_parts(clause):
        m = ATTR_RE.match(part)
        if not m:
            raise LanguageError(
                "Bad syntax in attributes.", clause)
        name, expr = m.groups()
        if name in attrs:
            raise LanguageError(
                "Duplicate attribute name in attributes.", part)

        attrs[name] = expr

    return attrs


def parse_substitution(clause):
    m = SUBST_RE.match(clause)
    if m is None:
        raise LanguageError(
            "Invalid content substitution syntax.", clause)

    key, expression = m.groups()
    if not key:
        key = "text"

    return key, expression


def parse_defines(clause):
    defines = []
    for part in split_parts(clause):
        m = DEFINE_RE.match(part)
        if m is None:
            return
        context, name, expr = m.group(1, 2, 3)
        context = context or "local"

        if name.startswith('('):
            names = [n.strip() for n in name.strip('()').split(',')]
        else:
            names = (name,)

        defines.append((context, names, expr))

    return defines


def prepare_attributes(attrs, dyn_attributes, ns_attributes, drop_ns):
    drop = set([attribute['name'] for attribute, (ns, value)
                in zip(attrs, ns_attributes)
                if ns in drop_ns or (
                    ns == XMLNS_NS and
                    attribute['value'] in drop_ns
                    )
                ])

    attributes = OrderedDict()

    for attribute in attrs:
        name = attribute['name']

        if name in drop:
            continue

        attributes[name] = (
            attribute['value'],
            attribute['quote'],
            attribute['space'],
            attribute['eq'],
            None,
            )

    for name, expr in dyn_attributes.items():
        try:
            text, quote, space, eq, ignore = attributes[name]
        except KeyError:
            text = None
            quote = '"'
            space = " "
            eq = "="
        attributes[name] = text, quote, space, eq, expr

    return attributes


class RepeatItem(object):
    if interfaces is not None:
        zope.interface.implements(interfaces.ITALESIterator)

    __slots__ = "length", "_iterator"

    def __init__(self, iterator, length):
        self.length = length
        self._iterator = iterator

    def __iter__(self):
        return self._iterator

    try:
        iter(()).__len__
    except AttributeError:
        @property
        def index(self):
            remaining = self._iterator.__length_hint__()
            return self.length - remaining - 1
    else:
        @property
        def index(self):
            remaining = self._iterator.__len__()
            return self.length - remaining - 1

    @property
    def start(self):
        return self.index == 0

    @property
    def end(self):
        return self.index == self.length - 1

    @descriptorint
    def number(self):
        return self.index + 1

    @descriptorstr
    def odd(self):
        """Returns a true value if the item index is odd.

        >>> it = RepeatItem(iter(("apple", "pear")), 2)

        >>> next(it._iterator)
        'apple'
        >>> it.odd()
        ''

        >>> next(it._iterator)
        'pear'
        >>> it.odd()
        'odd'
        """

        return self.index % 2 == 1 and 'odd' or ''

    @descriptorstr
    def even(self):
        """Returns a true value if the item index is even.

        >>> it = RepeatItem(iter(("apple", "pear")), 2)

        >>> next(it._iterator)
        'apple'
        >>> it.even()
        'even'

        >>> next(it._iterator)
        'pear'
        >>> it.even()
        ''
        """

        return self.index % 2 == 0 and 'even' or ''

    def next(self):
        raise NotImplementedError(
            "Method not implemented (can't update local variable).")

    def _letter(self, base=ord('a'), radix=26):
        """Get the iterator position as a lower-case letter

        >>> it = RepeatItem(iter(("apple", "pear", "orange")), 3)
        >>> next(it._iterator)
        'apple'
        >>> it.letter()
        'a'
        >>> next(it._iterator)
        'pear'
        >>> it.letter()
        'b'
        >>> next(it._iterator)
        'orange'
        >>> it.letter()
        'c'
        """

        index = self.index
        if index < 0:
            raise TypeError("No iteration position")
        s = ""
        while 1:
            index, off = divmod(index, radix)
            s = chr(base + off) + s
            if not index:
                return s

    letter = descriptorstr(_letter)

    @descriptorstr
    def Letter(self):
        """Get the iterator position as an upper-case letter

        >>> it = RepeatItem(iter(("apple", "pear", "orange")), 3)
        >>> next(it._iterator)
        'apple'
        >>> it.Letter()
        'A'
        >>> next(it._iterator)
        'pear'
        >>> it.Letter()
        'B'
        >>> next(it._iterator)
        'orange'
        >>> it.Letter()
        'C'
        """

        return self._letter(base=ord('A'))

    @descriptorstr
    def Roman(self, rnvalues=(
                    (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
                    (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
                    (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I'))):
        """Get the iterator position as an upper-case roman numeral

        >>> it = RepeatItem(iter(("apple", "pear", "orange")), 3)
        >>> next(it._iterator)
        'apple'
        >>> it.Roman()
        'I'
        >>> next(it._iterator)
        'pear'
        >>> it.Roman()
        'II'
        >>> next(it._iterator)
        'orange'
        >>> it.Roman()
        'III'
        """

        n = self.index + 1
        s = ""
        for v, r in rnvalues:
            rct, n = divmod(n, v)
            s = s + r * rct
        return s

    @descriptorstr
    def roman(self):
        """Get the iterator position as a lower-case roman numeral

        >>> it = RepeatItem(iter(("apple", "pear", "orange")), 3)
        >>> next(it._iterator)
        'apple'
        >>> it.roman()
        'i'
        >>> next(it._iterator)
        'pear'
        >>> it.roman()
        'ii'
        >>> next(it._iterator)
        'orange'
        >>> it.roman()
        'iii'
        """

        return self.Roman().lower()


class RepeatDict(dict):
    __slots__ = ()

    def __call__(self, key, iterable):
        """We coerce the iterable to a tuple and return an iterator
        after registering it in the repeat dictionary."""

        try:
            iterable = tuple(iterable)
        except TypeError:
            if iterable is None:
                iterable = ()
            else:
                # The message below to the TypeError is the Python
                # 2.5-style exception message. Python 2.4.X also
                # raises a TypeError, but with a different message.
                # ("TypeError: iteration over non-sequence").  The
                # Python 2.5 error message is more helpful.  We
                # construct the 2.5-style message explicitly here so
                # that both Python 2.4.X and Python 2.5+ will raise
                # the same error.  This makes writing the tests eaiser
                # and makes the output easier to understand.
                raise TypeError("%r object is not iterable" %
                                type(iterable).__name__)

        length = len(iterable)
        iterator = iter(iterable)

        # insert item into repeat-dictionary
        self[key] = iterator, length, None

        return iterator, length

    def __getitem__(self, key):
        iterator, length, repeat = dict.__getitem__(self, key)
        if repeat is None:
            repeat = RepeatItem(iterator, length)
            self[key] = iterator, length, repeat
        return repeat

    __getattr__ = __getitem__

    def get(self, key, default):
        if key not in self:
            return default
        return self[key]