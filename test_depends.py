"""Test DEPENDs parsing."""
import logging

from lifted import ParseState
from depends import (parse_depends, SlottedPackageDependency, Conjunction, Disjunction,
                     BlockOperator)


def test_parsing():
    """Test various parsing DEPENDs cases."""
    test_cases = [
        ('a/b:3', SlottedPackageDependency),
        (' a/b !c/d ', Conjunction),
        (' || ( a/b c/d )', Disjunction),
        (' || ( a/b:= c/d )', Disjunction),
        ('!!abc/def', BlockOperator),
        ('!sys-apps/grep-2', BlockOperator),
        ('!!sys-apps/grep-2', BlockOperator),
        ('=sys-devel/llvm-9-r3 ||  ( >=c/a =d/b-2 <d/c )', Conjunction),
        ('|| ( <c/a-1.0 d/b d/c )', Disjunction),
        ('cheddar/cheese || ( <c/a-1.0 d/b d/c )', Conjunction),
        ('!!=cheddar/cheese-3.5-r4:_gouda+', BlockOperator),
        ('=cheddar/cheese-3.5-r4:_gouda+', SlottedPackageDependency),
        ('chunky/monkey:*', SlottedPackageDependency),
        ('cheddar/cheese-3.5-r4:1/2*', None),
        ('sys-apps/dtc-r4:1=', SlottedPackageDependency),
        ('sys-apps/dtc-r4:1/funky=', None),
        ('<sys-apps/dtc-r4:1/not-so-funky', SlottedPackageDependency),
    ]

    for test_case in test_cases:
        parsing = parse_depends(ParseState(test_case[0], 0))
        if parsing:
            # print parsing.value
            if not isinstance(parsing.value, test_case[1]):
                logging.error('We could not parse "%s" as type "%s"!',
                              test_case[0], test_case[1].__name__)
                logging.error('...instead we got %s',
                              parsing.value)
                assert False
        elif test_case[1] is None:
            # Fine for now
            continue
        else:
            logging.error('We could not parse "%s" as type "%s"!',
                          test_case[0], test_case[1].__name__)
            logging.error('...instead we got nothing.')
            assert False
