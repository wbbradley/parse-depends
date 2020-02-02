"""Portage DEPEND syntax parser."""

from collections import namedtuple

from lifted import (Parsing, any_of, char, chomp_space, compose, end_of_input,
                    first, lift, many, many1, mconcat, option,
                    parse_until_colon_or_whitespace, second, sequence,
                    skip_space, string, strings, until, whitespace)

class Error(Exception):
    """Module error class."""

class ParserError(Error):
    """Likely an error exists in the parser."""

PackageDependency = namedtuple('PackageDependency', ['category', 'package'])
PackageDependencyRelation = namedtuple('PackageDependencyRelation',
                                       ['operator', 'package_dependency',
                                        'version'])
BlockOperator = namedtuple('BlockOperator', ['strength', 'package_dependency'])
WEAK_BLOCK_STRENGTH = 'WEAK'
STRONG_BLOCK_STRENGTH = 'STRONG'

# https://devmanual.gentoo.org/general-concepts/dependencies/index.html#slot-dependencies
AnySlot = namedtuple('AnySlot', [])
OnlySlot = namedtuple('OnlySlot', ['slot'])
OnlySlotSubslot = namedtuple('OnlySlotSubslot', ['slot', 'subslot'])
SlottedPackageDependency = namedtuple('SlottedPackageDependency',
                                      ['package_dependency', 'slotting'])

Disjunction = namedtuple('Disjunction', ['dependencies'])
Conjunction = namedtuple('Conjunction', ['dependencies'])

parse_relational_tokens = strings('>', '>=', '<', '<=', '=')

def parse_category_package(parse_state):
    """Parse a PackageDependency."""
    # See https://devmanual.gentoo.org/ebuild-writing/file-format/#file-naming-rules
    # for more correct parsing rules here...
    parsing = parse_until_colon_or_whitespace(parse_state)
    if parsing:
        components = parsing.value.split('/')
        if len(components) != 2:
            return None
        return Parsing(PackageDependency(*components), parsing.parse_state)

    return None

def construct_package_dependency_relation(opcatpkgver):
    """Munge parse_operator_category_package_version output to a PackageDependencyRelation."""
    components = opcatpkgver[1].split('/')
    if len(components) != 2:
        raise ParserError('found bogus package name? "%s" looks like it is '
                          'missing a category or package name' % opcatpkgver[1])

    return PackageDependencyRelation(opcatpkgver[0],
                                     PackageDependency(*components),
                                     'v0')

# Parse a PackageDependencyRelation.
parse_operator_category_package_version = (
    lift(construct_package_dependency_relation,
         sequence([parse_relational_tokens,
                   parse_until_colon_or_whitespace])))

def parse_depend_expr(parse_state):
    """Parse a dependency expression."""
    return _parse_depend_expr(parse_state)

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

def construct_top_level_depends(terms):
    """Simplify the AST for top-level DEPENDs."""
    assert len(terms) == 2
    # Strip the end_of_input
    deps = terms[0]

    if len(deps) == 1:
        return deps[0]
    elif not deps:
        return None
    else:
        return Conjunction(deps)

# Parse a whole depends text. (Guarantees that we parse the whole thing.)
parse_depends = lift(construct_top_level_depends,
                     sequence([
                         many(chomp_space(parse_depend_expr)),
                         chomp_space(end_of_input)]))

parse_slot_name = sequence([
    until(lambda x: not str.isalnum(x) and x != '_'),
    option(until(lambda x: not str.isalnum(x) and x not in ('_', '-', '.', '+')))])

# Build a proper slotting.
parse_slot_dependency = (
    lift(second,
         sequence([
             char(':'),
             any_of([
                 lift(lambda _: AnySlot(), string('=')),
                 lift(lambda _: AnySlot(), string('*')),
                 lift(lambda terms: OnlySlot(mconcat(first(terms))),
                      sequence([parse_slot_name, char('=')])),
                 lift(lambda terms: OnlySlotSubslot(mconcat(terms[0]), mconcat(terms[2])),
                      sequence([parse_slot_name, char('/'), parse_slot_name])),
                 lift(compose(OnlySlot, mconcat), parse_slot_name),
             ])
         ])))


def construct_pkg_dep(terms):
    """Construct a package dependency with the appropriate slotting.

    Based on terms from parse_pkg_dep.
    """
    return SlottedPackageDependency(terms[0], terms[1] if terms[1] else AnySlot())

# Parse a package dependency."""
parse_pkg_dep = lift(construct_pkg_dep,
                     sequence([any_of([parse_operator_category_package_version,
                                       parse_category_package]),
                               option(parse_slot_dependency)]))

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
                                                        parse_pkg_dep]))

# The implementation of top-level depends language forms parsing.
_parse_depend_expr = any_of([parse_block_expr, parse_and_expr, parse_or_expr])
