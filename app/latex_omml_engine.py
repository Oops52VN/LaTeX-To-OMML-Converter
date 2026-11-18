# -*- coding: utf-8 -*-
r"""
latex_omml_engine.py
Direct LaTeX AST to OMML (Office Math Markup Language) Compiler.

Dedicated engine for the 'LaTeX' Studio tab in QUAST.
Completely independent from latex2mathml and MML2OMML.XSL.
Complies with Microsoft Word OMML schema and ISO 80000-2 mathematical layout standards.
"""

from __future__ import annotations
import re
import io
import time
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any, Union
from lxml import etree

WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MATH_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/math"
MATH_NS_URI = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
WORD_NS_URI = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

NSMAP = {
    'm': MATH_NAMESPACE,
    'w': WORD_NAMESPACE
}

# ---------------------------------------------------------------------------
# SYMBOL MAPPINGS
# ---------------------------------------------------------------------------

GREEK_SYMBOLS: Dict[str, str] = {
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\epsilon": "ϵ", r"\varepsilon": "ε", r"\zeta": "ζ", r"\eta": "η",
    r"\theta": "θ", r"\vartheta": "ϑ", r"\iota": "ι", r"\kappa": "κ",
    r"\lambda": "λ", r"\mu": "μ", r"\nu": "ν", r"\xi": "ξ",
    r"\pi": "π", r"\varpi": "ϖ", r"\rho": "ρ", r"\varrho": "ϱ",
    r"\sigma": "σ", r"\varsigma": "ς", r"\tau": "τ", r"\upsilon": "υ",
    r"\phi": "ϕ", r"\varphi": "φ", r"\chi": "χ", r"\psi": "ψ",
    r"\omega": "ω",
    r"\Gamma": "Γ", r"\Delta": "Δ", r"\Theta": "Θ", r"\Lambda": "Λ",
    r"\Xi": "Ξ", r"\Pi": "Π", r"\Sigma": "Σ", r"\Upsilon": "Υ",
    r"\Phi": "Φ", r"\Psi": "Ψ", r"\Omega": "Ω",
}

BINARY_OPERATORS: Dict[str, str] = {
    r"\pm": "±", r"\mp": "∓", r"\times": "×", r"\cdot": "·",
    r"\div": "÷", r"\ast": "∗", r"\star": "⋆", r"\circ": "∘",
    r"\bullet": "•", r"\cap": "∩", r"\cup": "∪", r"\uplus": "⊎",
    r"\sqcap": "⊓", r"\sqcup": "⊔", r"\vee": "∨", r"\wedge": "∧",
    r"\setminus": "∖", r"\wr": "≀", r"\diamond": "⋄", r"\bigtriangleup": "△",
    r"\bigtriangledown": "▽", r"\triangleleft": "◃", r"\triangleright": "▹",
    r"\oplus": "⊕", r"\ominus": "⊖", r"\otimes": "⊗", r"\oslash": "⊘",
    r"\odot": "⊙", r"\bigcirc": "○", r"\dagger": "†", r"\ddagger": "‡",
    r"\amalg": "⨿",
}

RELATIONS: Dict[str, str] = {
    r"\le": "≤", r"\leq": "≤", r"\ge": "≥", r"\geq": "≥",
    r"\ne": "≠", r"\neq": "≠", r"\ll": "≪", r"\gg": "≫",
    r"\approx": "≈", r"\sim": "∼", r"\simeq": "≃", r"\cong": "≅",
    r"\equiv": "≡", r"\propto": "∝", r"\perp": "⊥", r"\parallel": "∥",
    r"\subset": "⊂", r"\supset": "⊃", r"\subseteq": "⊆", r"\supseteq": "⊇",
    r"\in": "∈", r"\notin": "∉", r"\ni": "∋", r"\owns": "∋",
    r"\prec": "≺", r"\succ": "≻", r"\preceq": "⪯", r"\succeq": "⪰",
    r"\vdash": "⊢", r"\dashv": "⊣", r"\models": "⊨",
}

ARROWS: Dict[str, str] = {
    r"\to": "→", r"\rightarrow": "→", r"\leftarrow": "←",
    r"\gets": "←", r"\leftrightarrow": "↔",
    r"\Rightarrow": "⇒", r"\implies": "⇒", r"\Leftarrow": "⇐",
    r"\Leftrightarrow": "⇔", r"\iff": "⇔",
    r"\uparrow": "↑", r"\downarrow": "↓", r"\updownarrow": "↕",
    r"\Uparrow": "⇑", r"\Downarrow": "⇓", r"\Updownarrow": "⇕",
    r"\mapsto": "↦", r"\hookleftarrow": "↩", r"\hookrightarrow": "↪",
    r"\leftharpoonup": "↼", r"\leftharpoondown": "↽",
    r"\rightharpoonup": "⇀", r"\rightharpoondown": "⇁",
    r"\rightleftharpoons": "⇌",
}

MATH_MISC_SYMBOLS: Dict[str, str] = {
    r"\infty": "∞", r"\partial": "∂", r"\nabla": "∇", r"\forall": "∀",
    r"\exists": "∃", r"\nexists": "∄", r"\emptyset": "∅", r"\varnothing": "∅",
    r"\angle": "∠", r"\triangle": "△", r"\bot": "⊥", r"\top": "⊤",
    r"\hbar": "ℏ", r"\ell": "ℓ", r"\Re": "ℜ", r"\Im": "ℑ",
    r"\wp": "℘", r"\aleph": "ℵ", r"\prime": "′",
    r"\therefore": "∴", r"\because": "∵",
    r"\ldots": "…", r"\cdots": "⋯", r"\vdots": "⋮", r"\ddots": "⋱",
    r"\dots": "…",
}

NARY_OPERATORS: Dict[str, str] = {
    r"\sum": "∑",
    r"\prod": "∏",
    r"\coprod": "∐",
    r"\int": "∫",
    r"\iint": "∬",
    r"\iiint": "∭",
    r"\oint": "∮",
    r"\bigcup": "⋃",
    r"\bigcap": "⋂",
    r"\bigvee": "⋁",
    r"\bigwedge": "⋀",
    r"\bigoplus": "⨁",
    r"\bigotimes": "⨂",
    r"\bigsqcup": "⨆",
}

LIMIT_FUNCS = {
    r"\lim", r"\liminf", r"\limsup", r"\max", r"\min",
    r"\sup", r"\inf", r"\det", r"\gcd", r"\Pr", r"\deg"
}

STANDARD_MATH_FUNCS = {
    r"\sin", r"\cos", r"\tan", r"\cot", r"\sec", r"\csc",
    r"\tg", r"\ctg",  # Common aliases in VN/FR curriculum
    r"\arcsin", r"\arccos", r"\arctan", r"\arccot",
    r"\sinh", r"\cosh", r"\tanh", r"\coth",
    r"\sh", r"\ch", r"\th", r"\cth",
    r"\ln", r"\log", r"\lg", r"\exp", r"\dim", r"\hom",
    r"\ker", r"\arg", r"\mod"
}

ACCENTS_MAP = {
    r"\hat": "^", r"\widehat": "^",
    r"\vec": "→", r"\overrightarrow": "→",
    r"\bar": "¯", r"\overline": "¯",
    r"\underline": "_",
    r"\tilde": "~", r"\widetilde": "~",
    r"\dot": "˙", r"\ddot": "¨", r"\dddot": "⋯",
    r"\acute": "´", r"\grave": "`", r"\breve": "˘", r"\check": "ˇ",
}

SPACES_MAP = {
    r"\,": "thin", r"\thinspace": "thin",
    r"\:": "med", r"\medspace": "med",
    r"\;": "thick", r"\thickspace": "thick",
    r"\quad": "quad", r"\qquad": "qquad",
    r"\!": "neg", r"\enspace": "en",
}

# ---------------------------------------------------------------------------
# LEXER / TOKENIZER
# ---------------------------------------------------------------------------

@dataclass
class Token:
    kind: str  # COMMAND, IDENT, NUMBER, SYMBOL, OPERATOR, LBRACE, RBRACE, LBRACKET, RBRACKET, SUB, SUP, AMP, DBLBACKSLASH, SPACE, TEXT, NEWLINE
    value: str
    pos: int

class LaTeXLexer:
    """Fast lexical scanner for raw LaTeX mathematics and mixed text."""
    def __init__(self, text: str):
        self.text = text
        self.len = len(text)
        self.pos = 0

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        while self.pos < self.len:
            ch = self.text[self.pos]

            # LaTeX comments
            if ch == '%':
                while self.pos < self.len and self.text[self.pos] not in '\r\n':
                    self.pos += 1
                continue

            # Whitespace handling: Newline may indicate equation breaks
            if ch in '\r\n':
                # Skip consecutive newlines and emit a single NEWLINE
                start = self.pos
                while self.pos < self.len and self.text[self.pos] in '\r\n':
                    self.pos += 1
                tokens.append(Token('NEWLINE', '\n', start))
                continue

            if ch.isspace():
                self.pos += 1
                continue

            # LaTeX command: \something
            if ch == '\\':
                start = self.pos
                self.pos += 1
                if self.pos < self.len:
                    next_ch = self.text[self.pos]
                    if next_ch == '\\':
                        self.pos += 1
                        tokens.append(Token('DBLBACKSLASH', r'\\', start))
                        continue
                    if next_ch in [',', ':', ';', '!', ' ', '%', '$', '&', '#', '_', '{', '}', '|']:
                        self.pos += 1
                        val = '\\' + next_ch
                        if val in [r'\{', r'\}']:
                            tokens.append(Token('SYMBOL', val, start))
                        elif val in [r'\|']:
                            tokens.append(Token('SYMBOL', '‖', start))
                        elif val in [r'\$', r'\%', r'\&', r'\#', r'\_']:
                            tokens.append(Token('SYMBOL', next_ch, start))
                        else:
                            tokens.append(Token('SPACE', val, start))
                        continue
                    if next_ch.isalpha():
                        cmd_start = self.pos
                        while self.pos < self.len and self.text[self.pos].isalpha():
                            self.pos += 1
                        cmd_name = '\\' + self.text[cmd_start:self.pos]
                        tokens.append(Token('COMMAND', cmd_name, start))
                        continue
                tokens.append(Token('SYMBOL', '\\', start))
                continue

            if ch == '{':
                tokens.append(Token('LBRACE', '{', self.pos))
                self.pos += 1
            elif ch == '}':
                tokens.append(Token('RBRACE', '}', self.pos))
                self.pos += 1
            elif ch == '[':
                tokens.append(Token('LBRACKET', '[', self.pos))
                self.pos += 1
            elif ch == ']':
                tokens.append(Token('RBRACKET', ']', self.pos))
                self.pos += 1
            elif ch == '(':
                tokens.append(Token('LPAREN', '(', self.pos))
                self.pos += 1
            elif ch == ')':
                tokens.append(Token('RPAREN', ')', self.pos))
                self.pos += 1
            elif ch == '^':
                tokens.append(Token('SUP', '^', self.pos))
                self.pos += 1
            elif ch == '_':
                tokens.append(Token('SUB', '_', self.pos))
                self.pos += 1
            elif ch == '&':
                tokens.append(Token('AMP', '&', self.pos))
                self.pos += 1
            elif ch == "'":
                start = self.pos
                while self.pos < self.len and self.text[self.pos] == "'":
                    self.pos += 1
                tokens.append(Token('PRIME', self.text[start:self.pos], start))
            elif ch.isdigit() or (ch == '.' and self.pos + 1 < self.len and self.text[self.pos + 1].isdigit()):
                start = self.pos
                has_dot = False
                while self.pos < self.len and (self.text[self.pos].isdigit() or (self.text[self.pos] == '.' and not has_dot)):
                    if self.text[self.pos] == '.':
                        has_dot = True
                    self.pos += 1
                tokens.append(Token('NUMBER', self.text[start:self.pos], start))
            elif ch.isalpha():
                tokens.append(Token('IDENT', ch, self.pos))
                self.pos += 1
            elif ch in "+-*/=<>!|,;:@?~":
                tokens.append(Token('OPERATOR', ch, self.pos))
                self.pos += 1
            else:
                tokens.append(Token('SYMBOL', ch, self.pos))
                self.pos += 1

        return tokens


# ---------------------------------------------------------------------------
# AST NODES
# ---------------------------------------------------------------------------

@dataclass
class ASTNode:
    pass

@dataclass
class NodeList(ASTNode):
    nodes: List[ASTNode] = field(default_factory=list)

@dataclass
class TextNode(ASTNode):
    text: str
    is_normal: bool = False

@dataclass
class NumberNode(ASTNode):
    value: str

@dataclass
class SymbolNode(ASTNode):
    char: str

@dataclass
class OperatorNode(ASTNode):
    op: str

@dataclass
class SpaceNode(ASTNode):
    kind: str  # thin, med, thick, quad, etc.

@dataclass
class FracNode(ASTNode):
    num: ASTNode
    den: ASTNode
    has_bar: bool = True  # False for \binom

@dataclass
class SqrtNode(ASTNode):
    radicand: ASTNode
    degree: Optional[ASTNode] = None

@dataclass
class ScriptNode(ASTNode):
    base: ASTNode
    sub: Optional[ASTNode] = None
    sup: Optional[ASTNode] = None

@dataclass
class NaryNode(ASTNode):
    operator: str
    sub: Optional[ASTNode] = None
    sup: Optional[ASTNode] = None
    arg: Optional[ASTNode] = None

@dataclass
class LimNode(ASTNode):
    name: str
    target: Optional[ASTNode] = None
    arg: Optional[ASTNode] = None

@dataclass
class FuncNode(ASTNode):
    name: str
    sup: Optional[ASTNode] = None
    arg: Optional[ASTNode] = None

@dataclass
class DelimNode(ASTNode):
    beg_chr: str
    end_chr: str
    content: ASTNode
    grow: bool = True

@dataclass
class AccentNode(ASTNode):
    char: str
    base: ASTNode

@dataclass
class MatrixCell(ASTNode):
    content: ASTNode

@dataclass
class MatrixRow(ASTNode):
    cells: List[MatrixCell] = field(default_factory=list)

@dataclass
class MatrixNode(ASTNode):
    rows: List[MatrixRow] = field(default_factory=list)
    delim_open: str = ""
    delim_close: str = ""

@dataclass
class CasesNode(ASTNode):
    rows: List[MatrixRow] = field(default_factory=list)

@dataclass
class EqArrayNode(ASTNode):
    rows: List[ASTNode] = field(default_factory=list)


# ---------------------------------------------------------------------------
# PARSER (Recursive Descent)
# ---------------------------------------------------------------------------

class LaTeXParser:
    """Parses token streams into high-level mathematical AST nodes."""
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.len = len(tokens)

    def current(self) -> Optional[Token]:
        if self.pos < self.len:
            return self.tokens[self.pos]
        return None

    def advance(self) -> Optional[Token]:
        token = self.current()
        self.pos += 1
        return token

    def match(self, kind: str, value: Optional[str] = None) -> bool:
        t = self.current()
        if not t:
            return False
        if t.kind != kind:
            return False
        if value is not None and t.value != value:
            return False
        self.advance()
        return True

    def parse(self) -> ASTNode:
        """
        Parses full stream. If multiple lines are separated by \\ or \n at top-level,
        combines them into an EqArrayNode for Word OMML.
        """
        lines: List[List[ASTNode]] = [[]]

        while self.pos < self.len:
            cur = self.current()
            if not cur:
                break

            # Line break at top-level: \\ or NEWLINE
            if cur.kind == 'DBLBACKSLASH':
                self.advance()
                self.parse_optional_arg()  # e.g., \\[6pt]
                lines.append([])
                continue
            elif cur.kind == 'NEWLINE':
                self.advance()
                if lines[-1]:  # only create new line if current line has content
                    lines.append([])
                continue

            item = self.parse_item()
            if item:
                lines[-1].append(item)
            else:
                self.pos += 1

        # Clean empty lines
        lines = [line for line in lines if line]

        if not lines:
            return NodeList([])

        if len(lines) == 1:
            nodes = self._group_fences(lines[0])
            return nodes[0] if len(nodes) == 1 else NodeList(nodes)
        else:
            # Multi-line equations -> EqArrayNode
            eq_rows = []
            for line in lines:
                grouped = self._group_fences(line)
                row_ast = grouped[0] if len(grouped) == 1 else NodeList(grouped)
                eq_rows.append(row_ast)
            return EqArrayNode(rows=eq_rows)

    def parse_group_or_item(self) -> ASTNode:
        """Parses { ... } or a single atomic token."""
        if self.match('LBRACE'):
            nodes: List[ASTNode] = []
            while self.pos < self.len and not (self.current() and self.current().kind == 'RBRACE'):
                item = self.parse_item()
                if item:
                    nodes.append(item)
                else:
                    self.pos += 1
            self.match('RBRACE')
            nodes = self._group_fences(nodes)
            if len(nodes) == 1:
                return nodes[0]
            return NodeList(nodes)
        else:
            item = self.parse_atom()
            return item if item else NodeList([])

    def parse_optional_arg(self) -> Optional[ASTNode]:
        """Parses [ ... ] if present."""
        if self.match('LBRACKET'):
            nodes: List[ASTNode] = []
            while self.pos < self.len and not (self.current() and self.current().kind == 'RBRACKET'):
                item = self.parse_item()
                if item:
                    nodes.append(item)
                else:
                    self.pos += 1
            self.match('RBRACKET')
            if len(nodes) == 1:
                return nodes[0]
            return NodeList(nodes)
        return None

    def parse_item(self) -> Optional[ASTNode]:
        base = self.parse_atom()
        if base is None:
            return None

        # Check for Prime notation immediately following base
        while self.current() and self.current().kind == 'PRIME':
            prime_val = self.advance().value
            prime_symbol = "′" * len(prime_val)
            base = ScriptNode(base=base, sup=SymbolNode(prime_symbol))

        # Check for Sub/Superscripts
        has_sub = False
        has_sup = False
        sub_node: Optional[ASTNode] = None
        sup_node: Optional[ASTNode] = None

        while True:
            cur = self.current()
            if not cur:
                break
            if cur.kind == 'SUB' and not has_sub:
                self.advance()
                sub_node = self.parse_group_or_item()
                has_sub = True
            elif cur.kind == 'SUP' and not has_sup:
                self.advance()
                sup_node = self.parse_group_or_item()
                has_sup = True
            elif cur.kind == 'PRIME' and not has_sup:
                prime_val = self.advance().value
                sup_node = SymbolNode("′" * len(prime_val))
                has_sup = True
            else:
                break

        if has_sub or has_sup:
            if isinstance(base, NaryNode):
                base.sub = sub_node
                base.sup = sup_node
                return base
            elif isinstance(base, LimNode):
                base.target = sub_node
                return base
            elif isinstance(base, FuncNode):
                base.sup = sup_node
                return base
            else:
                return ScriptNode(base=base, sub=sub_node, sup=sup_node)

        return base

    def parse_atom(self) -> Optional[ASTNode]:
        cur = self.current()
        if not cur:
            return None

        # 1. GROUP { ... }
        if cur.kind == 'LBRACE':
            return self.parse_group_or_item()

        # 2. DELIMITERS: (, ), [, ]
        if cur.kind in ['LPAREN', 'RPAREN', 'LBRACKET', 'RBRACKET']:
            val = self.advance().value
            return SymbolNode(val)

        # 3. NUMBERS
        if cur.kind == 'NUMBER':
            return NumberNode(self.advance().value)

        # 4. IDENTIFIERS (a, b, x, y...)
        if cur.kind == 'IDENT':
            return TextNode(self.advance().value)

        # 5. BASIC OPERATORS
        if cur.kind == 'OPERATOR':
            val = self.advance().value
            return OperatorNode(val)

        # 6. SPACES
        if cur.kind == 'SPACE':
            val = self.advance().value
            kind = SPACES_MAP.get(val, 'thin')
            return SpaceNode(kind)

        # 7. COMMANDS (\frac, \sqrt, \sin, \sum, etc.)
        if cur.kind == 'COMMAND':
            cmd = cur.value
            self.advance()

            # Environments: \begin{...} ... \end{...}
            if cmd == r"\begin":
                return self.parse_environment()

            # Fractions
            if cmd in [r"\frac", r"\dfrac", r"\tfrac", r"\cfrac"]:
                num = self.parse_group_or_item()
                den = self.parse_group_or_item()
                return FracNode(num=num, den=den, has_bar=True)

            # Binomial coefficient
            if cmd in [r"\binom", r"\dbinom", r"\tbinom"]:
                n = self.parse_group_or_item()
                k = self.parse_group_or_item()
                inner_frac = FracNode(num=n, den=k, has_bar=False)
                return DelimNode(beg_chr="(", end_chr=")", content=inner_frac, grow=True)

            # Radicals / Square roots
            if cmd == r"\sqrt":
                deg = self.parse_optional_arg()
                rad = self.parse_group_or_item()
                return SqrtNode(radicand=rad, degree=deg)

            # N-ary Operators (\sum, \int, \prod, etc.)
            if cmd in NARY_OPERATORS:
                op_chr = NARY_OPERATORS[cmd]
                return NaryNode(operator=op_chr)

            # Limit-like functions (\lim, \max, \min, \det...)
            if cmd in LIMIT_FUNCS:
                clean_name = cmd.lstrip('\\')
                return LimNode(name=clean_name)

            # Standard mathematical functions (\sin, \cos, \ln, \tg, \ctg...)
            if cmd in STANDARD_MATH_FUNCS:
                clean_name = cmd.lstrip('\\')
                return FuncNode(name=clean_name)

            # Delimiters with \left and \right
            if cmd == r"\left":
                return self.parse_left_right()

            # Accents: \hat, \vec, \bar, \dot, etc.
            if cmd in ACCENTS_MAP:
                acc_chr = ACCENTS_MAP[cmd]
                target = self.parse_group_or_item()
                return AccentNode(char=acc_chr, base=target)

            # Text / Fonts: \text, \mathrm, \operatorname, \textbf...
            if cmd in [r"\text", r"\mathrm", r"\operatorname", r"\mbox"]:
                text_content = self.parse_raw_text_group()
                return TextNode(text=text_content, is_normal=True)
            if cmd in [r"\mathbf", r"\boldsymbol"]:
                node = self.parse_group_or_item()
                return node
            if cmd in [r"\mathit", r"\displaystyle", r"\textstyle", r"\scriptstyle"]:
                return self.parse_group_or_item()

            # Greek Symbols
            if cmd in GREEK_SYMBOLS:
                return SymbolNode(GREEK_SYMBOLS[cmd])

            # Binary Operators
            if cmd in BINARY_OPERATORS:
                return OperatorNode(BINARY_OPERATORS[cmd])

            # Relations
            if cmd in RELATIONS:
                return OperatorNode(RELATIONS[cmd])

            # Arrows
            if cmd in ARROWS:
                return SymbolNode(ARROWS[cmd])

            # Misc Math Symbols
            if cmd in MATH_MISC_SYMBOLS:
                return SymbolNode(MATH_MISC_SYMBOLS[cmd])

            # Delimiter characters escaped
            if cmd in [r"\{", r"\}"]:
                return SymbolNode("{" if cmd == r"\{" else "}")

            # Spaces
            if cmd in SPACES_MAP:
                return SpaceNode(SPACES_MAP[cmd])

            # Fallback for unknown commands: render as identifier text
            clean_cmd = cmd.lstrip('\\')
            return TextNode(clean_cmd, is_normal=True)

        # 8. SYMBOLS / OTHER
        if cur.kind == 'SYMBOL':
            val = self.advance().value
            return SymbolNode(val)

        return None

    def parse_raw_text_group(self) -> str:
        """Collects raw text within a { ... } group."""
        if not self.match('LBRACE'):
            if self.current():
                return self.advance().value
            return ""
        parts = []
        depth = 1
        while self.pos < self.len and depth > 0:
            cur = self.current()
            if cur.kind == 'LBRACE':
                depth += 1
                parts.append('{')
            elif cur.kind == 'RBRACE':
                depth -= 1
                if depth > 0:
                    parts.append('}')
            elif cur.kind == 'SPACE':
                parts.append(' ')
            else:
                parts.append(cur.value)
            self.advance()
        return "".join(parts)

    def parse_environment(self) -> ASTNode:
        """Parses LaTeX environments like matrix, cases, aligned, etc."""
        env_name = self.parse_raw_text_group().strip()

        rows: List[MatrixRow] = []
        cur_cells: List[MatrixCell] = []
        cur_nodes: List[ASTNode] = []

        while self.pos < self.len:
            cur = self.current()
            if not cur:
                break

            # Check for \end{env_name}
            if cur.kind == 'COMMAND' and cur.value == r"\end":
                self.advance()
                end_name = self.parse_raw_text_group().strip()
                if end_name == env_name:
                    break
                continue

            # Cell separator '&'
            if cur.kind == 'AMP':
                self.advance()
                cell_ast = NodeList(self._group_fences(cur_nodes)) if len(cur_nodes) > 1 else (cur_nodes[0] if cur_nodes else NodeList([]))
                cur_cells.append(MatrixCell(cell_ast))
                cur_nodes = []
                continue

            # Row separator '\\'
            if cur.kind == 'DBLBACKSLASH':
                self.advance()
                self.parse_optional_arg()
                cell_ast = NodeList(self._group_fences(cur_nodes)) if len(cur_nodes) > 1 else (cur_nodes[0] if cur_nodes else NodeList([]))
                cur_cells.append(MatrixCell(cell_ast))
                rows.append(MatrixRow(cur_cells))
                cur_cells = []
                cur_nodes = []
                continue

            item = self.parse_item()
            if item:
                cur_nodes.append(item)
            else:
                self.pos += 1

        if cur_nodes or cur_cells:
            cell_ast = NodeList(self._group_fences(cur_nodes)) if len(cur_nodes) > 1 else (cur_nodes[0] if cur_nodes else NodeList([]))
            cur_cells.append(MatrixCell(cell_ast))
            rows.append(MatrixRow(cur_cells))

        if env_name in ['cases', 'dcases']:
            return CasesNode(rows=rows)
        elif env_name in ['aligned', 'align', 'align*', 'split', 'gathered']:
            eq_rows = []
            for r in rows:
                row_items = [c.content for c in r.cells]
                eq_rows.append(NodeList(row_items) if len(row_items) > 1 else (row_items[0] if row_items else NodeList([])))
            return EqArrayNode(rows=eq_rows)
        elif env_name in ['pmatrix']:
            return MatrixNode(rows=rows, delim_open="(", delim_close=")")
        elif env_name in ['bmatrix']:
            return MatrixNode(rows=rows, delim_open="[", delim_close="]")
        elif env_name in ['Bmatrix']:
            return MatrixNode(rows=rows, delim_open="{", delim_close="}")
        elif env_name in ['vmatrix']:
            return MatrixNode(rows=rows, delim_open="|", delim_close="|")
        elif env_name in ['Vmatrix']:
            return MatrixNode(rows=rows, delim_open="‖", delim_close="‖")
        else:
            return MatrixNode(rows=rows, delim_open="", delim_close="")

    def parse_left_right(self) -> ASTNode:
        """Parses \\left <delim> ... \\right <delim> structure (supports one-sided delims e.g. \\left. or \\left\\{)."""
        beg_delim = ""
        cur = self.current()
        if cur:
            beg_delim = cur.value
            self.advance()
        if beg_delim == '.':
            beg_delim = ""
        elif beg_delim == r'\{':
            beg_delim = "{"
        elif beg_delim == r'\}':
            beg_delim = "}"
        elif beg_delim == r'\|':
            beg_delim = "‖"

        nodes: List[ASTNode] = []
        end_delim = ""

        while self.pos < self.len:
            cur = self.current()
            if not cur:
                break
            if cur.kind == 'COMMAND' and cur.value == r"\right":
                self.advance()
                next_tok = self.current()
                if next_tok:
                    end_delim = next_tok.value
                    self.advance()
                if end_delim == '.':
                    end_delim = ""
                elif end_delim == r'\{':
                    end_delim = "{"
                elif end_delim == r'\}':
                    end_delim = "}"
                elif end_delim == r'\|':
                    end_delim = "‖"
                break

            item = self.parse_item()
            if item:
                nodes.append(item)
            else:
                self.pos += 1

        nodes = self._group_fences(nodes)
        content = NodeList(nodes) if len(nodes) > 1 else (nodes[0] if nodes else NodeList([]))
        return DelimNode(beg_chr=beg_delim, end_chr=end_delim, content=content, grow=True)

    def _group_fences(self, nodes: List[ASTNode]) -> List[ASTNode]:
        """
        ISO 80000-2 compliance:
        Single-Pass O(N) Stack-based grouping for balanced delimiters (..., [...], {...})
        into scalable DelimNode (<m:d>).
        Handles script on closing parenthesis, e.g. (-1)^k.
        """
        open_pairs = {'(': ')', '[': ']', '{': '}'}
        close_to_open = {')': '(', ']': '[', '}': '{'}
        stack = []
        current = []

        for n in nodes:
            if isinstance(n, SymbolNode) and n.char in open_pairs:
                stack.append((n.char, open_pairs[n.char], current))
                current = []
            elif isinstance(n, SymbolNode) and n.char in close_to_open:
                if stack and stack[-1][1] == n.char:
                    open_ch, target_close, prev_list = stack.pop()
                    inner = NodeList(current) if len(current) > 1 else (current[0] if current else NodeList([]))
                    delim = DelimNode(beg_chr=open_ch, end_chr=target_close, content=inner, grow=True)
                    prev_list.append(delim)
                    current = prev_list
                else:
                    current.append(n)
            elif isinstance(n, ScriptNode) and isinstance(n.base, SymbolNode) and n.base.char in close_to_open:
                if stack and stack[-1][1] == n.base.char:
                    open_ch, target_close, prev_list = stack.pop()
                    inner = NodeList(current) if len(current) > 1 else (current[0] if current else NodeList([]))
                    delim = DelimNode(beg_chr=open_ch, end_chr=target_close, content=inner, grow=True)
                    replacement = ScriptNode(base=delim, sub=n.sub, sup=n.sup)
                    prev_list.append(replacement)
                    current = prev_list
                else:
                    current.append(n)
            else:
                current.append(n)

        # Unwind any unclosed brackets
        while stack:
            open_ch, target_close, prev_list = stack.pop()
            prev_list.append(SymbolNode(open_ch))
            prev_list.extend(current)
            current = prev_list

        return current


# ---------------------------------------------------------------------------
# DIRECT OMML CODE GENERATOR
# ---------------------------------------------------------------------------

class OMMLBuilder:
    """Constructs native Microsoft Word OMML XML elements from AST."""
    def __init__(self):
        pass

    def build_omml_element(self, ast: ASTNode, is_para: bool = False) -> etree._Element:
        """Returns root <m:oMathPara> or <m:oMath> element."""
        if is_para:
            para = etree.Element(f"{MATH_NS_URI}oMathPara", nsmap=NSMAP)
            omath = etree.SubElement(para, f"{MATH_NS_URI}oMath")
            self._render_node(ast, omath)
            return para
        else:
            omath = etree.Element(f"{MATH_NS_URI}oMath", nsmap=NSMAP)
            self._render_node(ast, omath)
            return omath

    def _render_node(self, node: ASTNode, parent: etree._Element):
        if node is None:
            return

        if isinstance(node, NodeList):
            for child in node.nodes:
                self._render_node(child, parent)

        elif isinstance(node, TextNode):
            r = etree.SubElement(parent, f"{MATH_NS_URI}r")
            if node.is_normal:
                rPr = etree.SubElement(r, f"{MATH_NS_URI}rPr")
                etree.SubElement(rPr, f"{MATH_NS_URI}nor")
            t = etree.SubElement(r, f"{MATH_NS_URI}t")
            t.text = node.text

        elif isinstance(node, NumberNode):
            r = etree.SubElement(parent, f"{MATH_NS_URI}r")
            rPr = etree.SubElement(r, f"{MATH_NS_URI}rPr")
            etree.SubElement(rPr, f"{MATH_NS_URI}nor")
            t = etree.SubElement(r, f"{MATH_NS_URI}t")
            t.text = node.value

        elif isinstance(node, SymbolNode):
            r = etree.SubElement(parent, f"{MATH_NS_URI}r")
            t = etree.SubElement(r, f"{MATH_NS_URI}t")
            t.text = node.char

        elif isinstance(node, OperatorNode):
            r = etree.SubElement(parent, f"{MATH_NS_URI}r")
            t = etree.SubElement(r, f"{MATH_NS_URI}t")
            t.text = node.op

        elif isinstance(node, SpaceNode):
            r = etree.SubElement(parent, f"{MATH_NS_URI}r")
            t = etree.SubElement(r, f"{MATH_NS_URI}t")
            if node.kind == 'quad':
                t.text = "    "
            elif node.kind == 'qquad':
                t.text = "        "
            else:
                t.text = " "

        elif isinstance(node, FracNode):
            f = etree.SubElement(parent, f"{MATH_NS_URI}f")
            fPr = etree.SubElement(f, f"{MATH_NS_URI}fPr")
            if not node.has_bar:
                type_node = etree.SubElement(fPr, f"{MATH_NS_URI}type")
                type_node.set(f"{MATH_NS_URI}val", "noBar")
            num = etree.SubElement(f, f"{MATH_NS_URI}num")
            self._render_node(node.num, num)
            den = etree.SubElement(f, f"{MATH_NS_URI}den")
            self._render_node(node.den, den)

        elif isinstance(node, SqrtNode):
            rad = etree.SubElement(parent, f"{MATH_NS_URI}rad")
            radPr = etree.SubElement(rad, f"{MATH_NS_URI}radPr")
            if node.degree is None:
                deg_hide = etree.SubElement(radPr, f"{MATH_NS_URI}degHide")
                deg_hide.set(f"{MATH_NS_URI}val", "1")
            deg = etree.SubElement(rad, f"{MATH_NS_URI}deg")
            if node.degree is not None:
                self._render_node(node.degree, deg)
            e = etree.SubElement(rad, f"{MATH_NS_URI}e")
            self._render_node(node.radicand, e)

        elif isinstance(node, ScriptNode):
            if node.sub and node.sup:
                sSubSup = etree.SubElement(parent, f"{MATH_NS_URI}sSubSup")
                e = etree.SubElement(sSubSup, f"{MATH_NS_URI}e")
                self._render_node(node.base, e)
                sub = etree.SubElement(sSubSup, f"{MATH_NS_URI}sub")
                self._render_node(node.sub, sub)
                sup = etree.SubElement(sSubSup, f"{MATH_NS_URI}sup")
                self._render_node(node.sup, sup)
            elif node.sub:
                sSub = etree.SubElement(parent, f"{MATH_NS_URI}sSub")
                e = etree.SubElement(sSub, f"{MATH_NS_URI}e")
                self._render_node(node.base, e)
                sub = etree.SubElement(sSub, f"{MATH_NS_URI}sub")
                self._render_node(node.sub, sub)
            elif node.sup:
                sSup = etree.SubElement(parent, f"{MATH_NS_URI}sSup")
                e = etree.SubElement(sSup, f"{MATH_NS_URI}e")
                self._render_node(node.base, e)
                sup = etree.SubElement(sSup, f"{MATH_NS_URI}sup")
                self._render_node(node.sup, sup)
            else:
                self._render_node(node.base, parent)

        elif isinstance(node, NaryNode):
            nary = etree.SubElement(parent, f"{MATH_NS_URI}nary")
            naryPr = etree.SubElement(nary, f"{MATH_NS_URI}naryPr")
            chr_node = etree.SubElement(naryPr, f"{MATH_NS_URI}chr")
            chr_node.set(f"{MATH_NS_URI}val", node.operator)
            limLoc = etree.SubElement(naryPr, f"{MATH_NS_URI}limLoc")
            if node.operator in ["∫", "∬", "∭", "∮"]:
                limLoc.set(f"{MATH_NS_URI}val", "subSup")
            else:
                limLoc.set(f"{MATH_NS_URI}val", "undOvr")

            sub = etree.SubElement(nary, f"{MATH_NS_URI}sub")
            if node.sub:
                self._render_node(node.sub, sub)
            sup = etree.SubElement(nary, f"{MATH_NS_URI}sup")
            if node.sup:
                self._render_node(node.sup, sup)
            e = etree.SubElement(nary, f"{MATH_NS_URI}e")
            if node.arg:
                self._render_node(node.arg, e)

        elif isinstance(node, LimNode):
            if node.target:
                limLow = etree.SubElement(parent, f"{MATH_NS_URI}limLow")
                e = etree.SubElement(limLow, f"{MATH_NS_URI}e")
                r = etree.SubElement(e, f"{MATH_NS_URI}r")
                rPr = etree.SubElement(r, f"{MATH_NS_URI}rPr")
                etree.SubElement(rPr, f"{MATH_NS_URI}nor")
                t = etree.SubElement(r, f"{MATH_NS_URI}t")
                t.text = node.name
                lim = etree.SubElement(limLow, f"{MATH_NS_URI}lim")
                self._render_node(node.target, lim)
            else:
                r = etree.SubElement(parent, f"{MATH_NS_URI}r")
                rPr = etree.SubElement(r, f"{MATH_NS_URI}rPr")
                etree.SubElement(rPr, f"{MATH_NS_URI}nor")
                t = etree.SubElement(r, f"{MATH_NS_URI}t")
                t.text = node.name

        elif isinstance(node, FuncNode):
            func = etree.SubElement(parent, f"{MATH_NS_URI}func")
            fName = etree.SubElement(func, f"{MATH_NS_URI}fName")
            if node.sup:
                sSup = etree.SubElement(fName, f"{MATH_NS_URI}sSup")
                fe = etree.SubElement(sSup, f"{MATH_NS_URI}e")
                r = etree.SubElement(fe, f"{MATH_NS_URI}r")
                rPr = etree.SubElement(r, f"{MATH_NS_URI}rPr")
                etree.SubElement(rPr, f"{MATH_NS_URI}nor")
                t = etree.SubElement(r, f"{MATH_NS_URI}t")
                t.text = node.name
                sup = etree.SubElement(sSup, f"{MATH_NS_URI}sup")
                self._render_node(node.sup, sup)
            else:
                r = etree.SubElement(fName, f"{MATH_NS_URI}r")
                rPr = etree.SubElement(r, f"{MATH_NS_URI}rPr")
                etree.SubElement(rPr, f"{MATH_NS_URI}nor")
                t = etree.SubElement(r, f"{MATH_NS_URI}t")
                t.text = node.name
            e = etree.SubElement(func, f"{MATH_NS_URI}e")
            if node.arg:
                self._render_node(node.arg, e)

        elif isinstance(node, DelimNode):
            d = etree.SubElement(parent, f"{MATH_NS_URI}d")
            dPr = etree.SubElement(d, f"{MATH_NS_URI}dPr")
            if node.beg_chr:
                begChr = etree.SubElement(dPr, f"{MATH_NS_URI}begChr")
                begChr.set(f"{MATH_NS_URI}val", node.beg_chr)
            if node.end_chr:
                endChr = etree.SubElement(dPr, f"{MATH_NS_URI}endChr")
                endChr.set(f"{MATH_NS_URI}val", node.end_chr)
            sepChr = etree.SubElement(dPr, f"{MATH_NS_URI}sepChr")
            sepChr.set(f"{MATH_NS_URI}val", "")
            if not node.grow:
                grow = etree.SubElement(dPr, f"{MATH_NS_URI}grow")
                grow.set(f"{MATH_NS_URI}val", "0")

            e = etree.SubElement(d, f"{MATH_NS_URI}e")
            self._render_node(node.content, e)

        elif isinstance(node, AccentNode):
            acc = etree.SubElement(parent, f"{MATH_NS_URI}acc")
            accPr = etree.SubElement(acc, f"{MATH_NS_URI}accPr")
            chr_node = etree.SubElement(accPr, f"{MATH_NS_URI}chr")
            chr_node.set(f"{MATH_NS_URI}val", node.char)
            e = etree.SubElement(acc, f"{MATH_NS_URI}e")
            self._render_node(node.base, e)

        elif isinstance(node, MatrixNode):
            target_parent = parent
            if node.delim_open or node.delim_close:
                d = etree.SubElement(parent, f"{MATH_NS_URI}d")
                dPr = etree.SubElement(d, f"{MATH_NS_URI}dPr")
                if node.delim_open:
                    begChr = etree.SubElement(dPr, f"{MATH_NS_URI}begChr")
                    begChr.set(f"{MATH_NS_URI}val", node.delim_open)
                if node.delim_close:
                    endChr = etree.SubElement(dPr, f"{MATH_NS_URI}endChr")
                    endChr.set(f"{MATH_NS_URI}val", node.delim_close)
                sepChr = etree.SubElement(dPr, f"{MATH_NS_URI}sepChr")
                sepChr.set(f"{MATH_NS_URI}val", "")
                target_parent = etree.SubElement(d, f"{MATH_NS_URI}e")

            m = etree.SubElement(target_parent, f"{MATH_NS_URI}m")
            mPr = etree.SubElement(m, f"{MATH_NS_URI}mPr")
            baseJc = etree.SubElement(mPr, f"{MATH_NS_URI}baseJc")
            baseJc.set(f"{MATH_NS_URI}val", "center")

            for row in node.rows:
                mr = etree.SubElement(m, f"{MATH_NS_URI}mr")
                for cell in row.cells:
                    e = etree.SubElement(mr, f"{MATH_NS_URI}e")
                    self._render_node(cell.content, e)

        elif isinstance(node, CasesNode):
            d = etree.SubElement(parent, f"{MATH_NS_URI}d")
            dPr = etree.SubElement(d, f"{MATH_NS_URI}dPr")
            begChr = etree.SubElement(dPr, f"{MATH_NS_URI}begChr")
            begChr.set(f"{MATH_NS_URI}val", "{")
            sepChr = etree.SubElement(dPr, f"{MATH_NS_URI}sepChr")
            sepChr.set(f"{MATH_NS_URI}val", "")
            d_e = etree.SubElement(d, f"{MATH_NS_URI}e")

            eqArr = etree.SubElement(d_e, f"{MATH_NS_URI}eqArr")
            for row in node.rows:
                e = etree.SubElement(eqArr, f"{MATH_NS_URI}e")
                for c in row.cells:
                    self._render_node(c.content, e)

        elif isinstance(node, EqArrayNode):
            eqArr = etree.SubElement(parent, f"{MATH_NS_URI}eqArr")
            for row in node.rows:
                e = etree.SubElement(eqArr, f"{MATH_NS_URI}e")
                self._render_node(row, e)


# ---------------------------------------------------------------------------
# DIRECT MATHML PREVIEW GENERATOR (for UI Visual Rendering)
# ---------------------------------------------------------------------------

class MathMLPreviewBuilder:
    """Constructs clean W3C MathML for instant high-fidelity UI visual preview."""
    def build_mathml(self, ast: ASTNode, is_block: bool = True) -> str:
        disp = 'display="block"' if is_block else 'display="inline"'
        inner = self._render(ast)
        return f'<math xmlns="http://www.w3.org/1998/Math/MathML" {disp}>{inner}</math>'

    def _render(self, node: ASTNode) -> str:
        if node is None:
            return ""

        if isinstance(node, NodeList):
            return "".join(self._render(c) for c in node.nodes)

        elif isinstance(node, TextNode):
            if node.is_normal:
                return f"<mtext>{self._escape(node.text)}</mtext>"
            return f"<mi>{self._escape(node.text)}</mi>"

        elif isinstance(node, NumberNode):
            return f"<mn>{self._escape(node.value)}</mn>"

        elif isinstance(node, SymbolNode):
            return f"<mo>{self._escape(node.char)}</mo>"

        elif isinstance(node, OperatorNode):
            return f"<mo>{self._escape(node.op)}</mo>"

        elif isinstance(node, SpaceNode):
            return '<mspace width="0.278em"/>'

        elif isinstance(node, FracNode):
            num = self._render(node.num)
            den = self._render(node.den)
            linethickness = 'linethickness="1px"' if node.has_bar else 'linethickness="0"'
            return f"<mfrac {linethickness}><mrow>{num}</mrow><mrow>{den}</mrow></mfrac>"

        elif isinstance(node, SqrtNode):
            rad = self._render(node.radicand)
            if node.degree is not None:
                deg = self._render(node.degree)
                return f"<mroot><mrow>{rad}</mrow><mrow>{deg}</mrow></mroot>"
            return f"<msqrt><mrow>{rad}</mrow></msqrt>"

        elif isinstance(node, ScriptNode):
            base = self._render(node.base)
            if node.sub and node.sup:
                sub = self._render(node.sub)
                sup = self._render(node.sup)
                return f"<msubsup><mrow>{base}</mrow><mrow>{sub}</mrow><mrow>{sup}</mrow></msubsup>"
            elif node.sub:
                sub = self._render(node.sub)
                return f"<msub><mrow>{base}</mrow><mrow>{sub}</mrow></msub>"
            elif node.sup:
                sup = self._render(node.sup)
                return f"<msup><mrow>{base}</mrow><mrow>{sup}</mrow></msup>"
            return base

        elif isinstance(node, NaryNode):
            op = f"<mo>{self._escape(node.operator)}</mo>"
            if node.sub and node.sup:
                sub = self._render(node.sub)
                sup = self._render(node.sup)
                return f"<munderover>{op}<mrow>{sub}</mrow><mrow>{sup}</mrow></munderover>"
            elif node.sub:
                sub = self._render(node.sub)
                return f"<munder>{op}<mrow>{sub}</mrow></munder>"
            elif node.sup:
                sup = self._render(node.sup)
                return f"<mover>{op}<mrow>{sup}</mrow></mover>"
            return op

        elif isinstance(node, LimNode):
            name = f"<mo>{self._escape(node.name)}</mo>"
            if node.target:
                tgt = self._render(node.target)
                return f"<munder>{name}<mrow>{tgt}</mrow></munder>"
            return name

        elif isinstance(node, FuncNode):
            name = f"<mi mathvariant=\"normal\">{self._escape(node.name)}</mi>"
            if node.sup:
                sup = self._render(node.sup)
                return f"<msup>{name}<mrow>{sup}</mrow></msup>"
            return name

        elif isinstance(node, DelimNode):
            beg = f"<mo fence=\"true\" stretchy=\"true\">{self._escape(node.beg_chr)}</mo>" if node.beg_chr else ""
            end = f"<mo fence=\"true\" stretchy=\"true\">{self._escape(node.end_chr)}</mo>" if node.end_chr else ""
            content = self._render(node.content)
            return f"<mrow>{beg}{content}{end}</mrow>"

        elif isinstance(node, AccentNode):
            base = self._render(node.base)
            acc = f"<mo accent=\"true\">{self._escape(node.char)}</mo>"
            return f"<mover><mrow>{base}</mrow>{acc}</mover>"

        elif isinstance(node, MatrixNode):
            rows_html = []
            for r in node.rows:
                cells_html = "".join(f"<mtd>{self._render(c.content)}</mtd>" for c in r.cells)
                rows_html.append(f"<mtr>{cells_html}</mtr>")
            table = f"<mtable>{''.join(rows_html)}</mtable>"
            if node.delim_open or node.delim_close:
                beg = f"<mo fence=\"true\" stretchy=\"true\">{self._escape(node.delim_open)}</mo>" if node.delim_open else ""
                end = f"<mo fence=\"true\" stretchy=\"true\">{self._escape(node.delim_close)}</mo>" if node.delim_close else ""
                return f"<mrow>{beg}{table}{end}</mrow>"
            return table

        elif isinstance(node, CasesNode):
            rows_html = []
            for r in node.rows:
                cells_html = "".join(f"<mtd columnalign=\"left\">{self._render(c.content)}</mtd>" for c in r.cells)
                rows_html.append(f"<mtr>{cells_html}</mtr>")
            table = f"<mtable columnalign=\"left\">{''.join(rows_html)}</mtable>"
            return f"<mrow><mo fence=\"true\" stretchy=\"true\" form=\"prefix\">&#x0007B;</mo>{table}</mrow>"

        elif isinstance(node, EqArrayNode):
            rows_html = []
            for row in node.rows:
                cells_html = f"<mtd>{self._render(row)}</mtd>"
                rows_html.append(f"<mtr>{cells_html}</mtr>")
            return f"<mtable columnalign=\"left\">{''.join(rows_html)}</mtable>"

        return ""

    @staticmethod
    def _escape(text: str) -> str:
        return (text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# PUBLIC STUDIO COMPILER API
# ---------------------------------------------------------------------------

def _parse_segment(expr: str) -> ASTNode:
    lexer = LaTeXLexer(expr)
    tokens = lexer.tokenize()
    parser = LaTeXParser(tokens)
    return parser.parse()

def compile_raw_latex_for_studio(raw_input: str) -> Dict[str, Any]:
    """
    Main entry point for LaTeX Studio tab.
    Accurately handles:
    1. Pure raw LaTeX code (without $ or delimiters) -> inline mode (display="inline", left-aligned).
    2. Display math ($$...$$, \\[...\\], \\begin{equation}) -> block mode (display="block", centered).
    3. Inline math ($...$, \\(...\\)) -> inline mode (display="inline", left-aligned).
    4. Mixed text containing $...$, $$...$$, \\[...\\], \\(...\\).
    5. Multi-line equations and complex environments (aligned, cases, matrix).
    """
    start_time = time.perf_counter()
    raw_input = raw_input.strip()
    if not raw_input:
        return {"success": False, "error": "Input is empty"}

    try:
        clean = raw_input
        ast: ASTNode
        is_block = False

        # 1. Single display math formula
        if clean.startswith("$$") and clean.endswith("$$") and len(clean) >= 4 and "$$" not in clean[2:-2]:
            clean_math = clean[2:-2].strip()
            ast = _parse_segment(clean_math)
            is_block = True
        elif clean.startswith(r"\[") and clean.endswith(r"\]") and len(clean) >= 4 and r"\]" not in clean[2:-2]:
            clean_math = clean[2:-2].strip()
            ast = _parse_segment(clean_math)
            is_block = True
        elif (clean.startswith(r"\begin{equation}") and clean.endswith(r"\end{equation}")) or \
             (clean.startswith(r"\begin{equation*}") and clean.endswith(r"\end{equation*}")) or \
             (clean.startswith(r"\begin{displaymath}") and clean.endswith(r"\end{displaymath}")):
            ast = _parse_segment(clean)
            is_block = True
        # 2. Single inline math formula
        elif clean.startswith("$") and clean.endswith("$") and len(clean) >= 2 and not clean.startswith("$$") and "$" not in clean[1:-1]:
            clean_math = clean[1:-1].strip()
            ast = _parse_segment(clean_math)
            is_block = False
        elif clean.startswith(r"\(") and clean.endswith(r"\)") and len(clean) >= 4 and r"\)" not in clean[2:-2]:
            clean_math = clean[2:-2].strip()
            ast = _parse_segment(clean_math)
            is_block = False
        else:
            # 3. Check for mixed text
            pattern = re.compile(
                r'((?<!\\)\$\$.*?(?<!\\)\$\$|(?<!\\)\$.*?(?<!\\)\$|(?<!\\)\\\[.*?(?<!\\)\\\]|(?<!\\)\\\([\s\S]*?(?<!\\)\\\))',
                re.DOTALL
            )
            parts = pattern.split(clean)
            non_empty_text = [p.strip() for i, p in enumerate(parts) if i % 2 == 0 and p.strip()]
            math_segments = [p.strip() for i, p in enumerate(parts) if i % 2 == 1 and p.strip()]

            if len(math_segments) > 0 and len(non_empty_text) > 0:
                # Mixed text mode
                combined_nodes: List[ASTNode] = []
                for i, part in enumerate(parts):
                    if not part:
                        continue
                    if i % 2 == 1:
                        # Math segment
                        clean_math = part
                        if clean_math.startswith('$$') and clean_math.endswith('$$'):
                            clean_math = clean_math[2:-2]
                        elif clean_math.startswith('$') and clean_math.endswith('$'):
                            clean_math = clean_math[1:-1]
                        elif clean_math.startswith(r'\\[') and clean_math.endswith(r'\\]'):
                            clean_math = clean_math[2:-2]
                        elif clean_math.startswith(r'\\(') and clean_math.endswith(r'\\)'):
                            clean_math = clean_math[2:-2]
                        sub_ast = _parse_segment(clean_math.strip())
                        combined_nodes.append(sub_ast)
                    else:
                        # Regular text segment (preserve words and spaces)
                        combined_nodes.append(TextNode(text=part, is_normal=True))
                ast = NodeList(combined_nodes)
                is_block = False
            else:
                # 4. Pure raw LaTeX code (without $ or delimiters) defaults to inline math
                ast = _parse_segment(clean)
                is_block = False

        # Build OMML XML
        omml_builder = OMMLBuilder()
        omml_root = omml_builder.build_omml_element(ast, is_para=is_block)
        omml_xml = etree.tostring(omml_root, encoding="utf-8", pretty_print=True).decode("utf-8")

        # Build MathML for visual preview and clipboard paste
        preview_builder = MathMLPreviewBuilder()
        mathml_preview = preview_builder.build_mathml(ast, is_block=is_block)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return {
            "success": True,
            "latex": raw_input,
            "is_block": is_block,
            "omml": omml_xml,
            "mathml": mathml_preview,
            "time_ms": round(elapsed_ms, 2),
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "latex": raw_input
        }

def build_studio_docx_bytes(raw_input: str) -> bytes:
    """
    Builds a standalone Microsoft Word (.docx) document containing the compiled OMML math equation.
    Uses native [Content_Types].xml and document.xml structure.
    """
    res = compile_raw_latex_for_studio(raw_input)
    if not res["success"]:
        raise ValueError(f"Failed to compile LaTeX: {res.get('error')}")

    omml_node = etree.fromstring(res["omml"].encode("utf-8"))

    doc_xml = etree.Element(f"{WORD_NS_URI}document", nsmap=NSMAP)
    body = etree.SubElement(doc_xml, f"{WORD_NS_URI}body")
    p = etree.SubElement(body, f"{WORD_NS_URI}p")

    is_block = res.get("is_block", False)
    para = etree.SubElement(p, f"{MATH_NS_URI}oMathPara")
    para_pr = etree.SubElement(para, f"{MATH_NS_URI}oMathParaPr")
    jc = etree.SubElement(para_pr, f"{MATH_NS_URI}jc")
    jc.set(f"{MATH_NS_URI}val", "centerGroup" if is_block else "left")

    if omml_node.tag.endswith("oMath"):
        para.append(omml_node)
    else:
        omath_child = omml_node.find(f".//{MATH_NS_URI}oMath")
        para.append(omath_child if omath_child is not None else omml_node)

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>'
        )
        zout.writestr('[Content_Types].xml', content_types)

        rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>'
        )
        zout.writestr('_rels/.rels', rels)

        doc_xml_str = etree.tostring(doc_xml, encoding='UTF-8', xml_declaration=True)
        zout.writestr('word/document.xml', doc_xml_str)

    return stream.getvalue()


_FAST_OMML_CACHE: Dict[Tuple[str, bool], str] = {}

def compile_formula_fast_omml(latex_code: str, is_block: bool = False) -> Optional[str]:
    """
    Ultra-fast direct LaTeX AST -> OMML compiler for Word batch processing and file mode.
    Decoupled from MathML visual generation and XSLT stylesheets.
    Utilizes in-memory thread-safe AST caching for microsecond-level repeat compiles.
    """
    clean = latex_code.strip()
    if not clean:
        return None

    cache_key = (clean, is_block)
    cached = _FAST_OMML_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        # Strip outer delimiters if present
        if clean.startswith("$$") and clean.endswith("$$") and len(clean) >= 4:
            clean = clean[2:-2].strip()
            is_block = True
        elif clean.startswith("$") and clean.endswith("$") and len(clean) >= 2:
            clean = clean[1:-1].strip()
        elif clean.startswith(r"\[") and clean.endswith(r"\]") and len(clean) >= 4:
            clean = clean[2:-2].strip()
            is_block = True
        elif clean.startswith(r"\(") and clean.endswith(r"\)") and len(clean) >= 4:
            clean = clean[2:-2].strip()

        ast = _parse_segment(clean)
        builder = OMMLBuilder()
        omml_root = builder.build_omml_element(ast, is_para=is_block)
        omml_xml = etree.tostring(omml_root, encoding="utf-8").decode("utf-8")

        if len(_FAST_OMML_CACHE) > 5000:
            _FAST_OMML_CACHE.clear()

        _FAST_OMML_CACHE[cache_key] = omml_xml
        return omml_xml
    except Exception:
        return None
