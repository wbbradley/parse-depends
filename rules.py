"""Docstring."""

from collections import namedtuple


"""
depend_expr ::= pkg_dep | and_expr | or_expr | pred_expr
pkg_dep     ::= ('!' | '!!')? ( catpkg | ( operator catpkg '-' version ))
operator    ::= '>' | '>=' | '<' | '<=' | '=' | '~'
catpkg      ::= category '/' package
grouping    ::= '(' whitespace (depend_expr whitespace)+ ')'
and_expr    ::= grouping
or_expr     ::= '||' whitespace+ grouping
pred_expr   ::= '!'? use_flag '?' whitespace+ depend_expr
"""

RULES = {
    "a": {
        "DEPEND": "ufoo? foo"
    }
}

PackageDependency = namedtuple('PackageDependency', ['category', 'package'])
PackageDependencyRelation = namedtuple('PackageDependencyRelation',
                                       ['operator', 'package_dependency',
                                        'version'])
BlockOperator = namedtuple('BlockOperator', ['strength', 'package_dependency'])
WEAK_BLOCK_STRENGTH = 'WEAK'
STRONG_BLOCK_STRENGTH = 'STRONG'
SlotDependency = namedtuple('SlotDependency', ['todo'])
SlottedPackageDependency = namedtuple('SlottedPackageDependency',
                                      ['package_dependency',
                                       'slot_dependency'])
SlottedPackageDependencyRelation = namedtuple(
    'SlottedPackageDependencyRelation', ['package_dependency_relation',
                                         'slot_dependency'])
Disjunction = namedtuple('Disjunction', ['dependencies'])
Conjunction = namedtuple('Conjunction', ['dependencies'])

class ParseState(namedtuple('ParseState', ['input', 'pos'])):
    """The immutable state of the parser as it progresses."""

    def char(self, ch):
        """Parse the next character."""
        if self.pos < len(self.input):
            if self.input[self.pos] == ch:
                return Parsing(ch, ParseState(self.input, self.pos+1))
        return None

    def string(self, s):
        """Parse a specific string."""
        pos = self.pos
        len_input = len(self.input)
        if pos + len(s) > len_input:
            return None
        i = 0
        len_s = len(s)
        while i < len_s and self.input[pos] == s[i]:
            pos += 1
            i += 1

        if pos - self.pos == len_s:
            return Parsing(self.input[self.pos:pos],
                           ParseState(self.input, pos))

    def token(self):
        """Parse the next token (anything that's not whitespace.)"""
        pos = self.pos
        last_input = len(self.input) - 1
        while pos <= last_input and not str.isspace(self.input[pos]):
            pos += 1

        if pos - self.pos > 0:
            return Parsing(self.input[self.pos:pos],
                           ParseState(self.input, pos))

def first(xs):
    """Grab the first item from a list-like thing."""
    return xs[0]

def end_of_input(ps):
    """Match the end of input, return a value of None."""
    if len(ps.input) == ps.pos:
        return Parsing(None, ps)
    return None

def option(parser):
    """Create a parser that succeeds even when the given parser does not."""
    def fn(ps):
        """Parse with parser, return value of None if parser fails."""
        parsing = parser(ps)
        if parsing:
            return parsing
        else:
            return Parsing(None, ps)
    return fn

def whitespace(ps):
    """Parse 1+ whitespaces, value is just a single space."""
    pos = ps.pos
    while pos < len(ps.input) and str.isspace(ps.input[pos]):
        pos += 1
    if pos != ps.pos:
        return Parsing(' ', ParseState(ps.input, pos))
    else:
        return None

def skip_space(parser, fail_without_whitespace=True):
    """Creates a new parser that skips the space before the given parse."""
    def fn(ps):
        """A function which will skip space before parsing."""
        parsing = whitespace(ps)
        if not parsing:
            if fail_without_whitespace:
                return None
        else:
            ps = parsing.ps
        return parser(ps)
    return fn

chomp_space = lambda parser: skip_space(parser, fail_without_whitespace=False)

def char(ch):
    """Return a parser for a specific char."""
    return lambda ps: ps.char(ch)

def string(s):
    """Return a parser for a specific string."""
    return lambda ps: ps.string(s)

class Parsing(namedtuple('Parsing', ['value', 'ps'])):
    """A value from a parser, and the next parse state."""

def lift(fn, parser):
    """Like fmap for a parser."""
    def lifted_parser(ps):
        """Lift this parser to pass its successfull output through."""
        parsing = parser(ps)
        if parsing:
            return Parsing(fn(parsing.value), parsing.ps)
        return None
    return lifted_parser

def many(parser):
    """Kleene star."""
    def fn(ps):
        """Parsers with parser 0+ times."""
        results = []
        while True:
            parsing = parser(ps)
            if parsing:
                results.append(parsing.value)
            else:
                break
        return Parsing(results, parsing.ps if parsing else ps)
    return fn

def many1(parser):
    """Kleene plus."""
    def fn(ps):
        """Parsers with parser 1+ times."""
        results = []
        while True:
            parsing = parser(ps)
            if parsing:
                ps = parsing.ps
                results.append(parsing.value)
            else:
                break
        if results:
            return Parsing(results, ps)
        return None
    return fn

def any_of(parsers):
    """Return a parser that will succeed for any of the given parsers.

    Note that parsing attempts are still ordered. So, if multiple parsers could
    succeed, the first to succeed still wins.
    """
    def fn(ps):
        """Parse one of a set of given parsers."""
        for parser in parsers:
            parsing = parser(ps)
            if parsing:
                assert parsing.ps.pos > ps.pos
                return parsing
        return None
    return fn

def sequence(parsers):
    """Return a parser for the given sequence."""
    def fn(ps):
        """Parse a sequence of parsers. Must succeed with all."""
        results = []
        starting_pos = ps.pos
        for parser in parsers:
            parsing = parser(ps)
            if not parsing:
                return None
            results.append(parsing.value)
            ps = parsing.ps
        return Parsing(results, parsing.ps)
    return fn

def tokens(*args):
    """Return a parser that passes for the given token options."""
    def fn(ps):
        """Parse the closed-over |args| as tokens."""
        parsing = ps.token()
        if parsing:
            if parsing.value in args:
                return parsing
        return None
    return fn

def strings(*args):
    """Return a parser that passes for the given token options."""
    def fn(ps):
        """Parse the closed-over |args| as tokens."""
        for arg in args:
            parsing = ps.string(arg)
            if parsing:
                return parsing
        return None
    return fn

parse_relational_tokens = strings('>', '>=', '<', '<=', '=')

def parse_category_package(ps):
    """Parse a PackageDependency."""
    parsing = ps.token()
    if parsing:
        components = parsing.value.split('/')
        if len(components) != 2:
            return None
        return Parsing(PackageDependency(*components), parsing.ps)

    return None

def construct_package_dependency_relation(opcatpkgver):
    """Munge parse_operator_category_package_version output to a PackageDependencyRelation."""
    return PackageDependencyRelation(opcatpkgver[0],
                                     PackageDependency(*opcatpkgver[1].split('/')),
                                     'v0')

# Parse a PackageDependencyRelation.
parse_operator_category_package_version = (
    lift(construct_package_dependency_relation,
         sequence([parse_relational_tokens,
                   lambda parse_state:
                   parse_state.token()])))

def parse_depend_expr(ps):
    """Parse a dependency expression."""
    return _parse_depend_expr(ps)

# Parse the ( a b c ) form.
parse_and_expr = (
    lift(lambda xs: Conjunction(xs[1]),
         sequence([string('('),
                   many1(skip_space(parse_depend_expr)),
                   skip_space(char(')'))])))

# Parse the || ( a b c ) form.
parse_or_expr = (
    lift(lambda xs: Disjunction(xs[3]),
         sequence([string('||'),
                   whitespace,
                   char('('),
                   many1(skip_space(parse_depend_expr)),
                   skip_space(char(')'))])))

# Parse a whole depends input. (Guarantees that we parse the whole thing.)
parse_depends = lift(first,
                     sequence([parse_depend_expr, chomp_space(end_of_input)]))

# Parse a package dependency."""
parse_pkg_dep = any_of([parse_operator_category_package_version,
                        parse_category_package])

def construct_block_expr(terms):
    """Map the value sequence of parse_block_expr to AST form."""
    strength = None
    if terms[0] == '!':
        strength = STRONG_BLOCK_STRENGTH if terms[1] == '!' else WEAK_BLOCK_STRENGTH
        return BlockOperator(strength, terms[2])
    else:
        return terms[2]

# Parse block "!!sys-apps/whatever" expressions.
parse_block_expr = lift(construct_block_expr, sequence([option(char('!')),
                                                        option(char('!')),
                                                        chomp_space(parse_pkg_dep)]))

# The implementation of top-level depends language forms parsing.
_parse_depend_expr = any_of([parse_block_expr, parse_and_expr, parse_or_expr])


print parse_block_expr(ParseState('!!abc/def', 0)).value
print parse_depend_expr(ParseState('!sys-apps/grep-2', 0)).value
assert isinstance(parse_depend_expr(ParseState('!!sys-apps/grep-2', 0)).value, BlockOperator)
print skip_space(char('a'))(ParseState('   a  ', 0)).value
print parse_depend_expr(ParseState('|| ( c/a d/b d/c )', 0)).value
assert sequence([skip_space(char('a')), end_of_input])(ParseState('   a  ', 0)) is None
