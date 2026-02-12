"""
A simple DSL that compiles to logical primitives.

Syntax:
  predicate <name> {<role>: <type>, ...}
  entity <name> : <type>
  <pred>(<role>: <arg>, ...)
  not <pred>(<role>: <arg>, ...)
  MODAL [<var>:<type>, ...]: <premise> & <premise> -> <conclusion>
  ? <predicate>

Modals: always, usually, likely, sometimes, rarely, never
"""

import re
from dataclasses import dataclass, field

from message.core.logic import (
    Type, RoleLabel, Entity, Constant, Variable, Predicate
)


MODALS = {
    "always": 99.0,
    "usually": 2.3,
    "likely": 1.4,
    "sometimes": 0.7,
    "rarely": -2.3,
    "never": -99.0,
}


@dataclass
class PredicateDecl:
    name: str
    roles: dict[str, str]


@dataclass
class Rule:
    premises: list[Predicate]
    conclusion: Predicate
    variables: list[Variable]
    weight: float = 99.0
    modal: str = "always"


@dataclass
class LogicalDocument:
    predicates: dict[str, PredicateDecl] = field(default_factory=dict)
    entities: dict[str, Constant] = field(default_factory=dict)
    types: dict[str, Type] = field(default_factory=dict)
    propositions: list[Predicate] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    queries: list[Predicate] = field(default_factory=list)


class ParseError(Exception):
    def __init__(self, message: str, line_num: int, line: str):
        self.line_num = line_num
        self.line = line
        super().__init__(f"Line {line_num}: {message}\n  {line}")


class LogicalParser:
    def __init__(self):
        self.doc = LogicalDocument()
        self.phase = "predicates"

    def get_or_create_type(self, name: str) -> Type:
        if name not in self.doc.types:
            self.doc.types[name] = Type(name)
        return self.doc.types[name]

    def parse(self, text: str) -> LogicalDocument:
        self.doc = LogicalDocument()
        self.phase = "predicates"
        lines = text.strip().split("\n")
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                self.parse_line(line, i)
            except Exception as e:
                raise ParseError(str(e), i, line)
        return self.doc

    def parse_line(self, line: str, line_num: int):
        if line.startswith("predicate "):
            if self.phase != "predicates":
                raise ValueError("Predicate declarations must come before entities and sentences")
            self.parse_predicate_decl(line)
        elif line.startswith("entity "):
            if self.phase == "sentences":
                raise ValueError("Entity declarations must come before sentences")
            self.phase = "entities"
            self.parse_entity(line)
        elif self._is_rule(line):
            self.phase = "sentences"
            self.parse_rule(line)
        elif line.startswith("? "):
            self.phase = "sentences"
            self.parse_query(line)
        elif line.startswith("not ") and "(" in line:
            self.phase = "sentences"
            self.parse_proposition(line)
        elif "(" in line:
            self.phase = "sentences"
            self.parse_proposition(line)
        else:
            raise ValueError(f"Unknown syntax: {line}")

    def _is_rule(self, line: str) -> bool:
        for modal in MODALS:
            if line.startswith(modal + " ") or line.startswith(modal + ":"):
                return True
        if line.startswith("["):
            return True
        return False

    def parse_predicate_decl(self, line: str):
        match = re.match(r'predicate\s+(\w+)\s*\{([^}]*)\}', line)
        if not match:
            raise ValueError("Expected: predicate <name> {<role>: <type>, ...}")
        name = match.group(1)
        roles_str = match.group(2).strip()
        if name in self.doc.predicates:
            raise ValueError(f"Duplicate predicate: {name}")
        roles = {}
        if roles_str:
            for part in self._split_args(roles_str):
                part = part.strip()
                if ":" not in part:
                    raise ValueError(f"Expected role: type, got: {part}")
                role_name, type_name = part.split(":", 1)
                role_name = role_name.strip()
                type_name = type_name.strip()
                if role_name in roles:
                    raise ValueError(f"Duplicate role: {role_name}")
                roles[role_name] = type_name
                self.get_or_create_type(type_name)
        self.doc.predicates[name] = PredicateDecl(name=name, roles=roles)

    def parse_entity(self, line: str):
        match = re.match(r"entity\s+(\w+)\s*:\s*(\w+)", line)
        if not match:
            raise ValueError("Expected: entity <name> : <type>")
        name, type_name = match.groups()
        typ = self.get_or_create_type(type_name)
        entity = Entity(name)
        const = Constant(entity, typ)
        self.doc.entities[name] = const

    def parse_predicate(self, text: str, allow_variables: bool = False,
                        variables: dict = None, check_decl: bool = True) -> Predicate:
        variables = variables or {}
        text = text.strip()
        negated = False
        if text.startswith("not "):
            negated = True
            text = text[4:].strip()
        match = re.match(r'(\w+)\(\s*\)', text)
        if match:
            func_name = match.group(1)
            if check_decl and func_name not in self.doc.predicates:
                raise ValueError(f"Undeclared predicate: {func_name}")
            if check_decl and self.doc.predicates[func_name].roles:
                raise ValueError(f"Predicate {func_name} expects roles: {list(self.doc.predicates[func_name].roles.keys())}")
            return Predicate(func_name, (), negated)
        match = re.match(r'(\w+)\((.+)\)', text, re.DOTALL)
        if not match:
            raise ValueError(f"Expected predicate: pred(role: arg, ...), got: {text}")
        func_name = match.group(1)
        args_str = match.group(2).strip()
        if check_decl and func_name not in self.doc.predicates:
            raise ValueError(f"Undeclared predicate: {func_name}")
        decl = self.doc.predicates.get(func_name) if check_decl else None
        roles = []
        seen_roles = set()
        for arg_part in self._split_args(args_str):
            arg_part = arg_part.strip()
            if ":" not in arg_part:
                raise ValueError(f"Expected role: arg, got: {arg_part}")
            colon_idx = arg_part.index(":")
            role_name = arg_part[:colon_idx].strip()
            arg_value = arg_part[colon_idx + 1:].strip()
            if not role_name:
                raise ValueError("Empty role name")
            if decl and role_name not in decl.roles:
                raise ValueError(f"Unknown role '{role_name}' for predicate {func_name}")
            if role_name in seen_roles:
                raise ValueError(f"Duplicate role: {role_name}")
            seen_roles.add(role_name)
            role = RoleLabel(role_name)
            expected_type = decl.roles[role_name] if decl else None
            if "(" in arg_value:
                if expected_type and expected_type != "s" and not expected_type.startswith("["):
                    raise ValueError(f"Role '{role_name}' expects {expected_type}, got a predicate")
                arg = self.parse_predicate(arg_value, allow_variables=allow_variables,
                                          variables=variables, check_decl=check_decl)
            elif expected_type and expected_type.startswith("["):
                if arg_value not in self.doc.predicates:
                    raise ValueError(f"Unknown predicate: {arg_value}")
                arg = Constant(Entity(arg_value), Type("predicate"))
            elif arg_value in variables:
                arg = variables[arg_value]
            elif arg_value in self.doc.entities:
                arg = self.doc.entities[arg_value]
            elif allow_variables:
                raise ValueError(f"Unknown variable: {arg_value}")
            else:
                raise ValueError(f"Unknown entity: {arg_value}")
            roles.append((role, arg))
        if decl:
            missing = set(decl.roles.keys()) - seen_roles
            if missing:
                raise ValueError(f"Missing roles for {func_name}: {missing}")
        return Predicate(func_name, tuple(roles), negated)

    def parse_proposition(self, line: str):
        pred = self.parse_predicate(line, allow_variables=False)
        self.doc.propositions.append(pred)

    def parse_rule(self, line: str):
        rest = line
        modal = "always"
        for m in MODALS:
            if rest.startswith(m + " ") or rest.startswith(m + ":"):
                modal = m
                rest = rest[len(m):].strip()
                break
        weight = MODALS[modal]
        variables = {}
        var_list = []
        if rest.startswith("["):
            depth = 0
            end = 0
            for i, ch in enumerate(rest):
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end == 0:
                raise ValueError("Unmatched [ in rule bindings")
            var_decls = rest[1:end]
            rest = rest[end + 1:].strip()
            for var_decl in self._split_args(var_decls):
                var_decl = var_decl.strip()
                if not var_decl:
                    continue
                if ":" not in var_decl:
                    raise ValueError(f"Expected var:type, got: {var_decl}")
                var_name, type_name = var_decl.split(":", 1)
                var_name = var_name.strip()
                type_name = type_name.strip()
                typ = self.get_or_create_type(type_name)
                var = Variable(typ, var_name)
                variables[var_name] = var
                var_list.append(var)
        if rest.startswith(":"):
            rest = rest[1:].strip()
        if "->" not in rest:
            raise ValueError("Rule missing ->")
        premise_str, conclusion_str = rest.split("->", 1)
        premises = []
        for part in self._split_on_ampersand(premise_str):
            part = part.strip()
            if part:
                pred = self.parse_predicate(part, allow_variables=True, variables=variables)
                premises.append(pred)
        conclusion = self.parse_predicate(conclusion_str.strip(), allow_variables=True, variables=variables)
        rule = Rule(
            premises=premises,
            conclusion=conclusion,
            variables=var_list,
            weight=weight,
            modal=modal,
        )
        self.doc.rules.append(rule)

    def parse_query(self, line: str):
        pred_str = line[1:].strip()
        pred = self.parse_predicate(pred_str, allow_variables=False)
        self.doc.queries.append(pred)

    def _split_args(self, s: str) -> list[str]:
        parts = []
        depth = 0
        current = ""
        for ch in s:
            if ch in "([{":
                depth += 1
                current += ch
            elif ch in ")]}":
                depth -= 1
                current += ch
            elif ch == "," and depth == 0:
                parts.append(current)
                current = ""
            else:
                current += ch
        if current.strip():
            parts.append(current)
        return parts

    def _split_on_ampersand(self, s: str) -> list[str]:
        parts = []
        depth = 0
        current = ""
        for ch in s:
            if ch in "([{":
                depth += 1
                current += ch
            elif ch in ")]}":
                depth -= 1
                current += ch
            elif ch == "&" and depth == 0:
                parts.append(current)
                current = ""
            else:
                current += ch
        if current.strip():
            parts.append(current)
        return parts


def parse_logical(text: str) -> LogicalDocument:
    parser = LogicalParser()
    return parser.parse(text)


def format_predicate(pred: Predicate) -> str:
    prefix = "not " if pred.negated else ""
    if not pred.roles:
        return f"{prefix}{pred.function_name}()"
    args = ", ".join(f"{r.name}: {format_arg(a)}" for r, a in pred.roles)
    return f"{prefix}{pred.function_name}({args})"


def format_arg(arg) -> str:
    if isinstance(arg, Constant):
        return arg.entity.id
    elif isinstance(arg, Variable):
        return arg.name
    elif isinstance(arg, Predicate):
        return format_predicate(arg)
    return str(arg)


def format_predicate_decl(decl: PredicateDecl) -> str:
    if not decl.roles:
        return f"predicate {decl.name} {{}}"
    roles = ", ".join(f"{r}: {t}" for r, t in decl.roles.items())
    return f"predicate {decl.name} {{{roles}}}"


def format_rule(rule: Rule) -> str:
    if rule.variables:
        vars_str = ", ".join(f"{v.name}:{v.type.name}" for v in rule.variables)
        var_part = f"[{vars_str}]"
    else:
        var_part = ""
    premises_str = " & ".join(format_predicate(p) for p in rule.premises)
    if var_part:
        return f"{rule.modal} {var_part}: {premises_str} -> {format_predicate(rule.conclusion)}"
    else:
        return f"{rule.modal}: {premises_str} -> {format_predicate(rule.conclusion)}"


def format_document(doc: LogicalDocument) -> str:
    lines = []
    if doc.predicates:
        lines.append("# Predicates")
        for decl in doc.predicates.values():
            lines.append(format_predicate_decl(decl))
        lines.append("")
    if doc.entities:
        lines.append("# Entities")
        for name, const in doc.entities.items():
            lines.append(f"entity {name} : {const.type.name}")
        lines.append("")
    if doc.propositions:
        lines.append("# Propositions")
        for pred in doc.propositions:
            lines.append(format_predicate(pred))
        lines.append("")
    if doc.rules:
        lines.append("# Rules")
        for rule in doc.rules:
            lines.append(format_rule(rule))
        lines.append("")
    if doc.queries:
        lines.append("# Queries")
        for pred in doc.queries:
            lines.append(f"? {format_predicate(pred)}")
    return "\n".join(lines)