"""
This contains all predicates for use within Bobcat. These are primarily used
in designing links, for example:
::
    Node_Name:
        type: nodetype
        Node_To_Link_To: SimTime > 10

This creates a link that will only forward messages after a sim time of 10 "units" (typically seconds).

"""
patterns = []

try:
    from .gt import fn as gt_fn, pattern as gt_pattern

    patterns.append((gt_pattern, gt_fn))
except Exception as e:
    pass

try:
    from .gte import fn as gte_fn, pattern as gte_pattern

    patterns.append((gte_pattern, gte_fn))
except Exception as e:
    pass

try:
    from .lt import fn as lt_fn, pattern as lt_pattern

    patterns.append((lt_pattern, lt_fn))
except Exception as e:
    pass

try:
    from .lte import fn as lte_fn, pattern as lte_pattern

    patterns.append((lte_pattern, lte_fn))
except Exception as e:
    pass

try:
    from .de import fn as de_fn, pattern as de_pattern

    patterns.append((de_pattern, de_fn))
except Exception as e:
    pass

try:
    from .dne import fn as dne_fn, pattern as dne_pattern

    patterns.append((dne_pattern, dne_fn))
except Exception as e:
    pass

try:
    from .key_exists import fn as key_exists_fn, pattern as key_exists_pattern

    patterns.append((key_exists_pattern, key_exists_fn))
except Exception as e:
    pass

try:
    from .key_missing import fn as key_missing_fn, pattern as key_missing_pattern

    patterns.append((key_missing_pattern, key_missing_fn))
except Exception as e:
    pass

try:
    from .regex import fn as regex_fn, pattern as regex_pattern

    patterns.append((regex_pattern, regex_fn))
except Exception as e:
    pass

try:
    from .regex_failed import fn as regex_failed_fn, pattern as regex_failed_pattern

    patterns.append((regex_failed_pattern, regex_failed_fn))
except Exception as e:
    pass

try:
    from .percentage import fn as percentage_fn, pattern as percentage_pattern

    patterns.append((percentage_pattern, percentage_fn))
except Exception as e:
    pass

try:
    from .starts_with import fn as starts_with_fn, pattern as starts_with_pattern

    patterns.append((starts_with_pattern, starts_with_fn))
except Exception as e:
    pass
