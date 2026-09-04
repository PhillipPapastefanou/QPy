import re

# Matches a Fortran "NAMELIST /group_name/" declaration header (free-form source,
# case-insensitive - Fortran identifiers are case-insensitive).
_NML_HEADER_RE = re.compile(r'NAMELIST\s*/\s*([A-Za-z0-9_]+)\s*/', re.IGNORECASE)

# Matches a `CASE ('keyword')` arm of a Fortran SELECT CASE construct.
_CASE_KEY_RE = re.compile(r"CASE\s*\(\s*'([A-Za-z0-9_]+)'\s*\)", re.IGNORECASE)


def _strip_comment(line):
    # Fortran '!' starts an end-of-line comment. None of the blocks we scan contain
    # '!' inside string literals, so a plain find is sufficient here.
    idx = line.find('!')
    return line if idx == -1 else line[:idx]


def scan_namelist_groups(fortran_path):
    """Parse every `NAMELIST /group/ var1, var2, ...` declaration in a quincy Fortran
    source file, returning {lowercased_group_name: set_of_lowercased_variable_names}.

    Handles '&' line continuations, blank lines within a continued list (both are
    valid free-form Fortran and appear in quincy's source), and C-preprocessor
    conditionals (`#ifdef __QUINCY_STANDALONE__` / `#endif`) wrapped around some
    variables - these guard standalone-only fields that ARE present in the qs.bin
    build QPy targets, so they must not break the continuation scan.

    If a group name appears more than once in the file, the variable sets are merged.
    """
    with open(fortran_path, 'r', errors='replace') as f:
        lines = f.readlines()

    groups = {}
    i = 0
    n = len(lines)
    while i < n:
        m = _NML_HEADER_RE.search(lines[i])
        if not m:
            i += 1
            continue

        group_name = m.group(1).lower()
        text_parts = []

        first = _strip_comment(lines[i][m.end():])
        stripped = first.strip()
        if stripped and not stripped.startswith('#'):
            text_parts.append(first)
        continuing = (not stripped) or stripped.startswith('#') or stripped.endswith('&')

        while continuing and i + 1 < n:
            i += 1
            raw = _strip_comment(lines[i])
            stripped = raw.strip()
            if not stripped or stripped.startswith('#'):
                continuing = True
                continue
            text_parts.append(raw)
            continuing = stripped.endswith('&')

        text = ''.join(text_parts).replace('&', ' ')
        var_names = {tok.strip().lower() for tok in text.split(',') if tok.strip()}

        groups.setdefault(group_name, set()).update(var_names)
        i += 1

    return groups


def scan_lctlib_case_keys(fortran_path):
    """Return the set of lowercased keyword strings accepted by quincy's lctlib reader
    (mo_jsb_lctlib_class.f90), extracted from its `CASE ('keyword')` arms."""
    with open(fortran_path, 'r', errors='replace') as f:
        content = f.read()
    return {m.group(1).lower() for m in _CASE_KEY_RE.finditer(content)}
