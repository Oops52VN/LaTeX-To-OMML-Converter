use super::normalizer::normalize_latex;
use pyo3::prelude::*;
use std::collections::HashSet;
use std::sync::OnceLock;

#[pyclass(frozen, get_all)]
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FormulaSegment {
    /// True if mathematical formula ($..$, $$..$$, \[..\], \(..\), or raw LaTeX), False if plain text
    pub is_math: bool,
    /// True if display math block ($$...$$, \[..\], or standalone raw block), False if inline ($...$, \(..\), or inline raw math)
    pub is_block: bool,
    /// Text content or LaTeX code (delimiters stripped and \sin, \cos normalized if is_math=true)
    pub text: String,
    /// Starting byte index in original string
    pub start_byte: usize,
    /// Ending byte index in original string
    pub end_byte: usize,
}

#[pymethods]
impl FormulaSegment {
    fn __repr__(&self) -> String {
        format!(
            "FormulaSegment(is_math={}, is_block={}, text={:?}, range={}..{})",
            self.is_math, self.is_block, self.text, self.start_byte, self.end_byte
        )
    }
}

pub const MATH_INDICATORS: &[&str] = &[
    r"\frac", r"\dfrac", r"\tfrac", r"\cfrac", r"\sqrt", r"\sum", r"\int", r"\iint", r"\iiint",
    r"\oint", r"\lim", r"\liminf", r"\limsup", r"\prod", r"\coprod",
    r"\Delta", r"\Gamma", r"\Theta", r"\Lambda", r"\Xi", r"\Pi", r"\Sigma", r"\Upsilon", r"\Phi",
    r"\Psi", r"\Omega", r"\alpha", r"\beta", r"\gamma", r"\delta", r"\epsilon", r"\varepsilon",
    r"\zeta", r"\eta", r"\theta", r"\vartheta", r"\iota", r"\kappa", r"\lambda", r"\mu", r"\nu",
    r"\xi", r"\pi", r"\varpi", r"\rho", r"\varrho", r"\sigma", r"\varsigma", r"\tau", r"\upsilon",
    r"\phi", r"\varphi", r"\chi", r"\psi", r"\omega",
    r"\implies", r"\iff", r"\pm", r"\mp", r"\cdot", r"\times", r"\div",
    r"\partial", r"\infty", r"\neq", r"\ne", r"\le", r"\leq", r"\ge", r"\geq", r"\ll", r"\gg",
    r"\approx", r"\sim", r"\simeq", r"\cong", r"\equiv", r"\propto",
    r"\cup", r"\cap", r"\bigcup", r"\bigcap", r"\subset", r"\supset", r"\subseteq", r"\supseteq",
    r"\in", r"\notin", r"\ni", r"\owns", r"\emptyset", r"\varnothing",
    r"\mathbf", r"\mathrm", r"\mathit", r"\mathcal", r"\mathbb", r"\mathfrak", r"\mathsf",
    r"\mathtt", r"\boldsymbol", r"\text", r"\textbf", r"\textit", r"\mbox", r"\operatorname",
    r"\quad", r"\qquad", r"\left", r"\right", r"\big", r"\Big", r"\bigg", r"\Bigg",
    r"\sin", r"\cos", r"\tan", r"\cot", r"\sec", r"\csc", r"\tg", r"\ctg",
    r"\arcsin", r"\arccos", r"\arctan", r"\arccot", r"\sinh", r"\cosh", r"\tanh", r"\coth",
    r"\ln", r"\log", r"\lg", r"\exp",
    r"\vec", r"\hat", r"\widehat", r"\bar", r"\overline", r"\underline", r"\tilde", r"\widetilde",
    r"\dot", r"\ddot", r"\dddot", r"\acute", r"\grave", r"\breve", r"\check",
    r"\overrightarrow", r"\overleftarrow", r"\overbrace", r"\underbrace",
    r"\begin", r"\end", r"\det", r"\gcd", r"\binom", r"\dbinom", r"\tbinom", r"\mod", r"\bmod",
    r"\pmod", r"\arg", r"\max", r"\min", r"\sup", r"\inf", r"\dim", r"\ker", r"\hom", r"\deg",
    r"\over", r"\atop", r"\choose", r"\overset", r"\underset", r"\stackrel",
    r"\to", r"\rightarrow", r"\leftarrow", r"\gets", r"\leftrightarrow", r"\Rightarrow",
    r"\Leftarrow", r"\Leftrightarrow", r"\mapsto", r"\uparrow", r"\downarrow", r"\updownarrow",
    r"\nabla", r"\forall", r"\exists", r"\nexists", r"\bot", r"\top", r"\angle", r"\triangle",
    r"\perp", r"\parallel", r"\mid", r"\hbar", r"\ell", r"\Re", r"\Im", r"\wp", r"\aleph",
    r"\prime", r"\therefore", r"\because", r"\ldots", r"\cdots", r"\vdots", r"\ddots", r"\dots",
    r"\displaystyle", r"\textstyle", r"\scriptstyle", r"\limits", r"\nolimits", r"\not",
    r"\oplus", r"\ominus", r"\otimes", r"\oslash", r"\odot", r"\wedge", r"\vee", r"\setminus",
    r"\ast", r"\star", r"\circ", r"\bullet", r"\prec", r"\succ", r"\preceq", r"\succeq",
    r"\vdash", r"\dashv", r"\models",
];

fn math_cmd_set() -> &'static HashSet<&'static str> {
    static SET: OnceLock<HashSet<&'static str>> = OnceLock::new();
    SET.get_or_init(|| MATH_INDICATORS.iter().copied().collect())
}

fn is_op_cmd(cmd: &str) -> bool {
    matches!(
        cmd,
        r"\pm"
            | r"\mp"
            | r"\times"
            | r"\cdot"
            | r"\div"
            | r"\ast"
            | r"\star"
            | r"\circ"
            | r"\cap"
            | r"\cup"
            | r"\wedge"
            | r"\vee"
            | r"\setminus"
            | r"\oplus"
            | r"\ominus"
            | r"\otimes"
            | r"\oslash"
            | r"\odot"
            | r"\le"
            | r"\leq"
            | r"\ge"
            | r"\geq"
            | r"\ne"
            | r"\neq"
            | r"\ll"
            | r"\gg"
            | r"\approx"
            | r"\sim"
            | r"\simeq"
            | r"\cong"
            | r"\equiv"
            | r"\propto"
            | r"\perp"
            | r"\parallel"
            | r"\subset"
            | r"\supset"
            | r"\subseteq"
            | r"\supseteq"
            | r"\in"
            | r"\notin"
            | r"\ni"
            | r"\owns"
            | r"\prec"
            | r"\succ"
            | r"\preceq"
            | r"\succeq"
            | r"\vdash"
            | r"\dashv"
            | r"\models"
            | r"\to"
            | r"\rightarrow"
            | r"\leftarrow"
            | r"\gets"
            | r"\leftrightarrow"
            | r"\Rightarrow"
            | r"\implies"
            | r"\Leftarrow"
            | r"\Leftrightarrow"
            | r"\iff"
            | r"\mapsto"
            | r"\mid"
    )
}

fn is_binary_arg_cmd(cmd: &str) -> bool {
    matches!(
        cmd,
        r"\frac"
            | r"\dfrac"
            | r"\tfrac"
            | r"\cfrac"
            | r"\binom"
            | r"\dbinom"
            | r"\tbinom"
            | r"\overset"
            | r"\underset"
            | r"\stackrel"
    )
}

fn is_unary_arg_cmd(cmd: &str) -> bool {
    matches!(
        cmd,
        r"\sqrt"
            | r"\vec"
            | r"\hat"
            | r"\widehat"
            | r"\bar"
            | r"\overline"
            | r"\underline"
            | r"\tilde"
            | r"\widetilde"
            | r"\dot"
            | r"\ddot"
            | r"\dddot"
            | r"\acute"
            | r"\grave"
            | r"\breve"
            | r"\check"
            | r"\overrightarrow"
            | r"\overleftarrow"
            | r"\overbrace"
            | r"\underbrace"
            | r"\mathbf"
            | r"\mathrm"
            | r"\mathit"
            | r"\mathcal"
            | r"\mathbb"
            | r"\mathfrak"
            | r"\mathsf"
            | r"\mathtt"
            | r"\boldsymbol"
            | r"\text"
            | r"\textbf"
            | r"\textit"
            | r"\mbox"
            | r"\operatorname"
            | r"\pmod"
    )
}

fn is_prefix_math_cmd(cmd: &str) -> bool {
    matches!(
        cmd,
        r"\int"
            | r"\iint"
            | r"\iiint"
            | r"\oint"
            | r"\sum"
            | r"\prod"
            | r"\coprod"
            | r"\bigcup"
            | r"\bigcap"
            | r"\bigvee"
            | r"\bigwedge"
            | r"\bigoplus"
            | r"\bigotimes"
            | r"\bigsqcup"
            | r"\lim"
            | r"\liminf"
            | r"\limsup"
            | r"\max"
            | r"\min"
            | r"\sup"
            | r"\inf"
            | r"\det"
            | r"\gcd"
            | r"\Pr"
            | r"\deg"
            | r"\sin"
            | r"\cos"
            | r"\tan"
            | r"\cot"
            | r"\sec"
            | r"\csc"
            | r"\tg"
            | r"\ctg"
            | r"\arcsin"
            | r"\arccos"
            | r"\arctan"
            | r"\arccot"
            | r"\sinh"
            | r"\cosh"
            | r"\tanh"
            | r"\coth"
            | r"\ln"
            | r"\log"
            | r"\lg"
            | r"\exp"
            | r"\dim"
            | r"\hom"
            | r"\ker"
            | r"\arg"
    )
}

fn is_bare_math_func(word: &str) -> bool {
    matches!(
        word,
        "sin"
            | "cos"
            | "tan"
            | "cot"
            | "sec"
            | "csc"
            | "arcsin"
            | "arccos"
            | "arctan"
            | "sinh"
            | "cosh"
            | "tanh"
            | "coth"
            | "log"
            | "ln"
            | "lg"
            | "exp"
            | "lim"
            | "det"
            | "gcd"
            | "lcm"
            | "max"
            | "min"
            | "sup"
            | "inf"
            | "arg"
            | "sgn"
    )
}

fn is_differential(word: &str) -> bool {
    let bytes = word.as_bytes();
    if bytes.len() != 2 || bytes[0] != b'd' || !bytes[1].is_ascii_alphabetic() {
        return false;
    }
    !matches!(word, "do" | "da" | "de" | "di")
}

fn is_unicode_math_char(ch: char) -> bool {
    matches!(
        ch,
        'α'..='ω'
            | 'Α'..='Ω'
            | 'ϑ'
            | 'ϕ'
            | 'ϖ'
            | 'ϱ'
            | '∞'
            | '∂'
            | '∇'
            | '∀'
            | '∃'
            | '∄'
            | '∅'
            | '∈'
            | '∉'
            | '∋'
            | '∏'
            | '∑'
            | '∫'
            | '∬'
            | '∭'
            | '∮'
            | '√'
            | '±'
            | '∓'
            | '×'
            | '÷'
            | '·'
            | '≤'
            | '≥'
            | '≠'
            | '≈'
            | '≡'
            | '∼'
            | '≃'
            | '≅'
            | '∝'
            | '⊥'
            | '∥'
            | '⊂'
            | '⊃'
            | '⊆'
            | '⊇'
            | '∪'
            | '∩'
            | '→'
            | '←'
            | '↔'
            | '⇒'
            | '⇐'
            | '⇔'
            | '↦'
            | '∠'
            | '△'
            | '∴'
            | '∵'
            | 'ℏ'
            | 'ℓ'
            | 'ℜ'
            | 'ℑ'
            | 'ℵ'
    )
}

#[derive(Clone, Debug, PartialEq, Eq)]
enum RawKind {
    Whitespace,
    ProseLocked,
    MathGroup, // \begin{env}...\end{env} or Unicode math symbol
    LatexCmd,
    BraceGroup,
    Word,
    Number,
    Op,
    Caret,
    Underscore,
    Prime,
    LParen,
    RParen,
    LBracket,
    RBracket,
    Punct,
    Other,
}

#[derive(Clone, Debug)]
struct RawTok {
    start: usize,
    end: usize,
    kind: RawKind,
}

fn find_matching_brace(input: &str, open_idx: usize) -> Option<usize> {
    let bytes = input.as_bytes();
    let len = bytes.len();
    if open_idx >= len || bytes[open_idx] != b'{' {
        return None;
    }
    let mut depth = 0usize;
    let mut i = open_idx;
    while i < len {
        let b = bytes[i];
        if b == b'\\' && i + 1 < len {
            i += 2;
            continue;
        }
        if b == b'{' {
            depth += 1;
        } else if b == b'}' {
            depth -= 1;
            if depth == 0 {
                return Some(i + 1);
            }
        }
        i += 1;
    }
    None
}

fn find_matching_env(input: &str, start_idx: usize, env_name: &str) -> Option<usize> {
    let begin_pat = format!(r"\begin{{{}}}", env_name);
    let end_pat = format!(r"\end{{{}}}", env_name);
    let mut depth = 1usize;
    let mut pos = start_idx + begin_pat.len();
    while pos < input.len() {
        let rest = &input[pos..];
        let next_begin = rest.find(&begin_pat);
        let next_end = rest.find(&end_pat);
        match (next_begin, next_end) {
            (Some(b), Some(e)) if b < e => {
                depth += 1;
                pos += b + begin_pat.len();
            }
            (_, Some(e)) => {
                depth -= 1;
                pos += e + end_pat.len();
                if depth == 0 {
                    return Some(pos);
                }
            }
            _ => return None,
        }
    }
    None
}

fn lex_raw_tokens(input: &str) -> Vec<RawTok> {
    let bytes = input.as_bytes();
    let len = bytes.len();
    let mut toks = Vec::new();
    let mut pos = 0usize;

    while pos < len {
        let b = bytes[pos];

        // 1. Code blocks ```...``` or `...`
        if b == b'`' {
            let start = pos;
            if pos + 2 < len && bytes[pos + 1] == b'`' && bytes[pos + 2] == b'`' {
                pos += 3;
                while pos + 2 < len {
                    if bytes[pos] == b'`' && bytes[pos + 1] == b'`' && bytes[pos + 2] == b'`' {
                        pos += 3;
                        break;
                    }
                    pos += 1;
                }
                if pos + 2 >= len && !input[start..].ends_with("```") {
                    pos = len;
                }
            } else {
                pos += 1;
                while pos < len {
                    if bytes[pos] == b'`' {
                        pos += 1;
                        break;
                    }
                    pos += 1;
                }
            }
            toks.push(RawTok {
                start,
                end: pos,
                kind: RawKind::ProseLocked,
            });
            continue;
        }

        // 2. URLs http:// or https://
        if (b == b'h')
            && (input[pos..].starts_with("http://") || input[pos..].starts_with("https://"))
        {
            let start = pos;
            while pos < len && !bytes[pos].is_ascii_whitespace() {
                pos += 1;
            }
            toks.push(RawTok {
                start,
                end: pos,
                kind: RawKind::ProseLocked,
            });
            continue;
        }

        // 3. Windows file paths like C:\Users\...
        if b.is_ascii_alphabetic()
            && pos + 2 < len
            && bytes[pos + 1] == b':'
            && bytes[pos + 2] == b'\\'
            && (pos == 0 || !bytes[pos - 1].is_ascii_alphanumeric())
        {
            let start = pos;
            while pos < len && !bytes[pos].is_ascii_whitespace() {
                pos += 1;
            }
            toks.push(RawTok {
                start,
                end: pos,
                kind: RawKind::ProseLocked,
            });
            continue;
        }

        // 4. UTF-8 char
        let ch = input[pos..].chars().next().unwrap();

        // Whitespace
        if ch.is_whitespace() {
            let start = pos;
            while pos < len {
                let c = input[pos..].chars().next().unwrap();
                if !c.is_whitespace() {
                    break;
                }
                pos += c.len_utf8();
            }
            toks.push(RawTok {
                start,
                end: pos,
                kind: RawKind::Whitespace,
            });
            continue;
        }

        // Backslash commands or \begin{...}
        if b == b'\\' {
            let start = pos;
            if input[pos..].starts_with(r"\begin{") {
                if let Some(close_br) = input[pos + 7..].find('}') {
                    let env_name = &input[pos + 7..pos + 7 + close_br];
                    if !env_name.is_empty() && env_name.bytes().all(|c| c.is_ascii_alphanumeric() || c == b'*') {
                        if let Some(end_idx) = find_matching_env(input, pos, env_name) {
                            pos = end_idx;
                            toks.push(RawTok {
                                start,
                                end: pos,
                                kind: RawKind::MathGroup,
                            });
                            continue;
                        }
                    }
                }
            }

            pos += 1;
            if pos < len {
                let next_c = input[pos..].chars().next().unwrap();
                if next_c.is_ascii_alphabetic() {
                    while pos < len && bytes[pos].is_ascii_alphabetic() {
                        pos += 1;
                    }
                    toks.push(RawTok {
                        start,
                        end: pos,
                        kind: RawKind::LatexCmd,
                    });
                    continue;
                } else if matches!(
                    next_c,
                    ',' | ':' | ';' | '!' | ' ' | '\\' | '{' | '}' | '|' | '%' | '$' | '&' | '#' | '_'
                ) {
                    pos += next_c.len_utf8();
                    toks.push(RawTok {
                        start,
                        end: pos,
                        kind: RawKind::LatexCmd,
                    });
                    continue;
                }
            }
            toks.push(RawTok {
                start,
                end: pos,
                kind: RawKind::Other,
            });
            continue;
        }

        // Balanced BraceGroup {...}
        if b == b'{' {
            if let Some(end_idx) = find_matching_brace(input, pos) {
                toks.push(RawTok {
                    start: pos,
                    end: end_idx,
                    kind: RawKind::BraceGroup,
                });
                pos = end_idx;
                continue;
            }
            toks.push(RawTok {
                start: pos,
                end: pos + 1,
                kind: RawKind::Other,
            });
            pos += 1;
            continue;
        }

        // Numbers [0-9]+(\.[0-9]+)?
        if b.is_ascii_digit() {
            let start = pos;
            while pos < len && bytes[pos].is_ascii_digit() {
                pos += 1;
            }
            if pos + 1 < len && bytes[pos] == b'.' && bytes[pos + 1].is_ascii_digit() {
                pos += 1;
                while pos < len && bytes[pos].is_ascii_digit() {
                    pos += 1;
                }
            }
            toks.push(RawTok {
                start,
                end: pos,
                kind: RawKind::Number,
            });
            continue;
        }

        // Unicode math symbol
        if is_unicode_math_char(ch) {
            let start = pos;
            pos += ch.len_utf8();
            toks.push(RawTok {
                start,
                end: pos,
                kind: RawKind::MathGroup,
            });
            continue;
        }

        // Words (ASCII or Unicode letters)
        if ch.is_alphabetic() {
            let start = pos;
            while pos < len {
                let c = input[pos..].chars().next().unwrap();
                if !c.is_alphabetic() || is_unicode_math_char(c) {
                    break;
                }
                pos += c.len_utf8();
            }
            toks.push(RawTok {
                start,
                end: pos,
                kind: RawKind::Word,
            });
            continue;
        }

        // Single-char punctuation / operators / delimiters
        let start = pos;
        pos += ch.len_utf8();
        let kind = match ch {
            '=' | '+' | '-' | '*' | '/' | '<' | '>' | '|' => RawKind::Op,
            '^' => RawKind::Caret,
            '_' => RawKind::Underscore,
            '\'' => {
                while pos < len && bytes[pos] == b'\'' {
                    pos += 1;
                }
                RawKind::Prime
            }
            '(' => RawKind::LParen,
            ')' => RawKind::RParen,
            '[' => RawKind::LBracket,
            ']' => RawKind::RBracket,
            ',' | '.' | ';' | ':' | '?' | '!' => RawKind::Punct,
            _ => RawKind::Other,
        };
        toks.push(RawTok { start, end: pos, kind });
    }

    toks
}

#[derive(Clone, Debug, PartialEq, Eq)]
enum AtomKind {
    Whitespace,
    ProseLocked,
    Math { is_anchor: bool, is_prefix: bool },
    Op { is_anchor: bool },
    Word,
    Number,
    Prime,
    LParen,
    RParen,
    LBracket,
    RBracket,
    Punct,
    Other,
}

#[derive(Clone, Debug)]
struct Atom {
    start: usize,
    end: usize,
    kind: AtomKind,
}

fn brace_has_math(s: &str) -> bool {
    s.contains('\\') || s.contains('^') || s.contains('_') || s.chars().any(is_unicode_math_char)
}

fn is_valid_single_arg_token(tok: &RawTok, input: &str) -> bool {
    match tok.kind {
        RawKind::BraceGroup | RawKind::MathGroup | RawKind::Number => true,
        RawKind::LatexCmd => math_cmd_set().contains(&input[tok.start..tok.end]),
        RawKind::Word => {
            let w = &input[tok.start..tok.end];
            w.chars().count() == 1 || is_differential(w)
        }
        _ => false,
    }
}

/// Consume a single LaTeX command (including its arguments if binary/unary command) starting at `idx`.
/// Returns `(end_byte, next_tok_idx, is_anchor, is_op, is_prefix)`
fn consume_latex_unit(input: &str, toks: &[RawTok], idx: usize) -> Option<(usize, usize, bool, bool, bool)> {
    let tok = toks.get(idx)?;
    if tok.kind != RawKind::LatexCmd {
        return None;
    }
    let cmd = &input[tok.start..tok.end];

    if matches!(cmd, r"\{" | r"\}" | r"\|" | r"\," | r"\:" | r"\;" | r"\!") {
        return Some((tok.end, idx + 1, matches!(cmd, r"\{" | r"\}" | r"\|"), false, false));
    }
    if !math_cmd_set().contains(cmd) {
        return None;
    }

    if is_op_cmd(cmd) {
        return Some((tok.end, idx + 1, true, true, false));
    }

    let mut cur = idx + 1;
    let mut end_byte = tok.end;

    if is_binary_arg_cmd(cmd) {
        for _ in 0..2 {
            let mut probe = cur;
            while probe < toks.len() && toks[probe].kind == RawKind::Whitespace {
                probe += 1;
            }
            if probe < toks.len() && is_valid_single_arg_token(&toks[probe], input) {
                if toks[probe].kind == RawKind::LatexCmd {
                    if let Some((e, nxt, _, _, _)) = consume_latex_unit(input, toks, probe) {
                        end_byte = e;
                        cur = nxt;
                        continue;
                    }
                }
                end_byte = toks[probe].end;
                cur = probe + 1;
            } else {
                break;
            }
        }
        return Some((end_byte, cur, true, false, false));
    }

    if is_unary_arg_cmd(cmd) {
        // Optional [...] for \sqrt
        if cmd == r"\sqrt" {
            let mut probe = cur;
            while probe < toks.len() && toks[probe].kind == RawKind::Whitespace {
                probe += 1;
            }
            if probe < toks.len() && toks[probe].kind == RawKind::LBracket {
                let mut k = probe + 1;
                while k < toks.len() && toks[k].kind != RawKind::RBracket {
                    k += 1;
                }
                if k < toks.len() {
                    end_byte = toks[k].end;
                    cur = k + 1;
                }
            }
        }
        let mut probe = cur;
        while probe < toks.len() && toks[probe].kind == RawKind::Whitespace {
            probe += 1;
        }
        if probe < toks.len() && is_valid_single_arg_token(&toks[probe], input) {
            if toks[probe].kind == RawKind::LatexCmd {
                if let Some((e, nxt, _, _, _)) = consume_latex_unit(input, toks, probe) {
                    end_byte = e;
                    cur = nxt;
                }
            } else {
                end_byte = toks[probe].end;
                cur = probe + 1;
            }
        }
        return Some((end_byte, cur, true, false, false));
    }

    Some((end_byte, cur, true, false, is_prefix_math_cmd(cmd)))
}

fn bind_math_atoms(input: &str, toks: &[RawTok]) -> Vec<Atom> {
    let mut atoms: Vec<Atom> = Vec::with_capacity(toks.len());
    let mut i = 0usize;

    while i < toks.len() {
        let t = &toks[i];
        match t.kind {
            RawKind::Whitespace => {
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::Whitespace,
                });
                i += 1;
            }
            RawKind::ProseLocked => {
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::ProseLocked,
                });
                i += 1;
            }
            RawKind::MathGroup => {
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::Math {
                        is_anchor: true,
                        is_prefix: false,
                    },
                });
                i += 1;
            }
            RawKind::LatexCmd => {
                if let Some((end_byte, nxt, is_anchor, is_op, is_prefix)) =
                    consume_latex_unit(input, toks, i)
                {
                    if is_op {
                        atoms.push(Atom {
                            start: t.start,
                            end: end_byte,
                            kind: AtomKind::Op { is_anchor },
                        });
                    } else {
                        atoms.push(Atom {
                            start: t.start,
                            end: end_byte,
                            kind: AtomKind::Math { is_anchor, is_prefix },
                        });
                    }
                    i = nxt;
                } else {
                    atoms.push(Atom {
                        start: t.start,
                        end: t.end,
                        kind: AtomKind::Other,
                    });
                    i += 1;
                }
            }
            RawKind::BraceGroup => {
                let s = &input[t.start..t.end];
                if brace_has_math(s) {
                    atoms.push(Atom {
                        start: t.start,
                        end: t.end,
                        kind: AtomKind::Math {
                            is_anchor: true,
                            is_prefix: false,
                        },
                    });
                } else {
                    atoms.push(Atom {
                        start: t.start,
                        end: t.end,
                        kind: AtomKind::Other,
                    });
                }
                i += 1;
            }
            RawKind::Word => {
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::Word,
                });
                i += 1;
            }
            RawKind::Number => {
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::Number,
                });
                i += 1;
            }
            RawKind::Op => {
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::Op { is_anchor: false },
                });
                i += 1;
            }
            RawKind::Caret => {
                // Bind base ^ rhs
                if let Some(base) = atoms.last() {
                    let base_ok = matches!(
                        base.kind,
                        AtomKind::Math { .. } | AtomKind::Word | AtomKind::Number | AtomKind::RParen | AtomKind::RBracket
                    );
                    if base_ok && i + 1 < toks.len() && is_valid_single_arg_token(&toks[i + 1], input) {
                        let (rhs_end, nxt_idx) = if toks[i + 1].kind == RawKind::LatexCmd {
                            if let Some((e, nxt, _, _, _)) = consume_latex_unit(input, toks, i + 1) {
                                (e, nxt)
                            } else {
                                (toks[i + 1].end, i + 2)
                            }
                        } else {
                            (toks[i + 1].end, i + 2)
                        };
                        let start = if matches!(base.kind, AtomKind::RParen | AtomKind::RBracket) {
                            // Try to include matching (...) / [...]
                            let open_k = if matches!(base.kind, AtomKind::RParen) {
                                AtomKind::LParen
                            } else {
                                AtomKind::LBracket
                            };
                            let close_k = base.kind.clone();
                            let mut depth = 0isize;
                            let mut found_open = None;
                            for k in (0..atoms.len()).rev() {
                                if atoms[k].kind == close_k {
                                    depth += 1;
                                } else if atoms[k].kind == open_k {
                                    depth -= 1;
                                    if depth == 0 {
                                        found_open = Some(k);
                                        break;
                                    }
                                }
                            }
                            if let Some(open_idx) = found_open {
                                let has_prose = atoms[open_idx + 1..atoms.len() - 1].iter().any(|a| {
                                    matches!(a.kind, AtomKind::Word)
                                        && input[a.start..a.end].chars().count() >= 2
                                        && !is_bare_math_func(&input[a.start..a.end])
                                        && !is_differential(&input[a.start..a.end])
                                });
                                if !has_prose {
                                    let st = atoms[open_idx].start;
                                    atoms.truncate(open_idx);
                                    st
                                } else {
                                    atoms.pop().unwrap().start
                                }
                            } else {
                                atoms.pop().unwrap().start
                            }
                        } else {
                            atoms.pop().unwrap().start
                        };

                        atoms.push(Atom {
                            start,
                            end: rhs_end,
                            kind: AtomKind::Math {
                                is_anchor: true,
                                is_prefix: false,
                            },
                        });
                        i = nxt_idx;
                        continue;
                    }
                }
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::Other,
                });
                i += 1;
            }
            RawKind::Underscore => {
                // Bind base _ rhs (avoid snake_case like my_variable_name)
                if let Some(base) = atoms.last() {
                    let base_word = &input[base.start..base.end];
                    let base_ok = match &base.kind {
                        AtomKind::Math { .. } | AtomKind::RParen | AtomKind::RBracket => true,
                        AtomKind::Word => {
                            base_word.chars().count() == 1 || is_bare_math_func(base_word)
                        }
                        _ => false,
                    };
                    if base_ok && i + 1 < toks.len() {
                        let rhs = &toks[i + 1];
                        let rhs_ok = match rhs.kind {
                            RawKind::BraceGroup | RawKind::MathGroup | RawKind::Number => true,
                            RawKind::LatexCmd => math_cmd_set().contains(&input[rhs.start..rhs.end]),
                            RawKind::Word => {
                                let rw = &input[rhs.start..rhs.end];
                                // Allow single char (x_i, \oint_C) or short sub when base is LatexCmd/Math
                                rw.chars().count() == 1
                                    || matches!(base.kind, AtomKind::Math { .. })
                            }
                            _ => false,
                        };
                        if rhs_ok {
                            let is_prefix = matches!(base.kind, AtomKind::Math { is_prefix: true, .. });
                            let (rhs_end, nxt_idx) = if rhs.kind == RawKind::LatexCmd {
                                if let Some((e, nxt, _, _, _)) = consume_latex_unit(input, toks, i + 1) {
                                    (e, nxt)
                                } else {
                                    (rhs.end, i + 2)
                                }
                            } else {
                                (rhs.end, i + 2)
                            };
                            let b = atoms.pop().unwrap();
                            atoms.push(Atom {
                                start: b.start,
                                end: rhs_end,
                                kind: AtomKind::Math {
                                    is_anchor: true,
                                    is_prefix,
                                },
                            });
                            i = nxt_idx;
                            continue;
                        }
                    }
                }
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::Other,
                });
                i += 1;
            }
            RawKind::Prime => {
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::Prime,
                });
                i += 1;
            }
            RawKind::LParen => {
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::LParen,
                });
                i += 1;
            }
            RawKind::RParen => {
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::RParen,
                });
                i += 1;
            }
            RawKind::LBracket => {
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::LBracket,
                });
                i += 1;
            }
            RawKind::RBracket => {
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::RBracket,
                });
                i += 1;
            }
            RawKind::Punct => {
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::Punct,
                });
                i += 1;
            }
            RawKind::Other => {
                atoms.push(Atom {
                    start: t.start,
                    end: t.end,
                    kind: AtomKind::Other,
                });
                i += 1;
            }
        }
    }

    // Sub-pass: merge directly adjacent (no whitespace) Math/1-char-Word/Number chains like `d\vec{l}`, `2x^2`, `e^x`
    // Wait: make sure `d\vec{l}` merges into one Math atom, and `2x^2` merges into one Math atom,
    // without merging `word\cmd` (only 1-char Word or Number before Math, or Math followed immediately by 1-char Word/Number).
    let mut merged: Vec<Atom> = Vec::with_capacity(atoms.len());
    for atom in atoms {
        if let Some(prev) = merged.last_mut() {
            if prev.end == atom.start {
                match (&prev.kind, &atom.kind) {
                    (AtomKind::Word, AtomKind::Math { is_anchor: true, .. })
                        if input[prev.start..prev.end].chars().count() == 1 =>
                    {
                        prev.end = atom.end;
                        prev.kind = AtomKind::Math {
                            is_anchor: true,
                            is_prefix: false,
                        };
                        continue;
                    }
                    (AtomKind::Number, AtomKind::Math { is_anchor: true, .. }) => {
                        prev.end = atom.end;
                        prev.kind = AtomKind::Math {
                            is_anchor: true,
                            is_prefix: false,
                        };
                        continue;
                    }
                    (AtomKind::Math { is_anchor: true, is_prefix }, AtomKind::Math { is_anchor: true, .. }) => {
                        prev.end = atom.end;
                        prev.kind = AtomKind::Math {
                            is_anchor: true,
                            is_prefix: *is_prefix,
                        };
                        continue;
                    }
                    (AtomKind::Math { is_anchor: true, .. }, AtomKind::Prime) => {
                        prev.end = atom.end;
                        continue;
                    }
                    _ => {}
                }
            }
        }
        merged.push(atom);
    }

    merged
}

fn next_non_ws(atoms: &[Atom], mut idx: usize) -> Option<usize> {
    while idx < atoms.len() {
        if atoms[idx].kind != AtomKind::Whitespace {
            return Some(idx);
        }
        idx += 1;
    }
    None
}

fn prev_non_ws(atoms: &[Atom], idx: usize) -> Option<usize> {
    let mut i = idx;
    while i > 0 {
        i -= 1;
        if atoms[i].kind != AtomKind::Whitespace {
            return Some(i);
        }
    }
    None
}

fn is_prose_word(atoms: &[Atom], idx: usize, input: &str) -> bool {
    if atoms[idx].kind != AtomKind::Word {
        return false;
    }
    let w = &input[atoms[idx].start..atoms[idx].end];
    w.chars().count() >= 2 && !is_bare_math_func(w) && !is_differential(w)
}

fn is_prose_hyphen_or_slash(atoms: &[Atom], idx: usize, input: &str) -> bool {
    if !matches!(atoms[idx].kind, AtomKind::Op { .. }) {
        return false;
    }
    let op = &input[atoms[idx].start..atoms[idx].end];
    if op != "-" && op != "/" {
        return false;
    }
    if idx > 0 && idx + 1 < atoms.len() {
        let l = &atoms[idx - 1];
        let r = &atoms[idx + 1];
        if l.end == atoms[idx].start && atoms[idx].end == r.start {
            if is_prose_word(atoms, idx - 1, input) || is_prose_word(atoms, idx + 1, input) {
                return true;
            }
        }
    }
    false
}

fn find_matching_paren_forward(atoms: &[Atom], open_idx: usize) -> Option<usize> {
    let (open_k, close_k) = match atoms[open_idx].kind {
        AtomKind::LParen => (AtomKind::LParen, AtomKind::RParen),
        AtomKind::LBracket => (AtomKind::LBracket, AtomKind::RBracket),
        _ => return None,
    };
    let mut depth = 0usize;
    for k in open_idx..atoms.len() {
        if atoms[k].kind == open_k {
            depth += 1;
        } else if atoms[k].kind == close_k {
            depth -= 1;
            if depth == 0 {
                return Some(k);
            }
        }
    }
    None
}

fn find_matching_paren_backward(atoms: &[Atom], close_idx: usize) -> Option<usize> {
    let (open_k, close_k) = match atoms[close_idx].kind {
        AtomKind::RParen => (AtomKind::LParen, AtomKind::RParen),
        AtomKind::RBracket => (AtomKind::LBracket, AtomKind::RBracket),
        _ => return None,
    };
    let mut depth = 0usize;
    for k in (0..=close_idx).rev() {
        if atoms[k].kind == close_k {
            depth += 1;
        } else if atoms[k].kind == open_k {
            depth -= 1;
            if depth == 0 {
                return Some(k);
            }
        }
    }
    None
}

fn is_valid_math_paren_group(atoms: &[Atom], open_idx: usize, close_idx: usize, input: &str) -> bool {
    if close_idx <= open_idx + 1 {
        return false;
    }
    let mut has_math_content = false;
    for k in (open_idx + 1)..close_idx {
        match atoms[k].kind {
            AtomKind::Whitespace | AtomKind::LParen | AtomKind::RParen | AtomKind::LBracket | AtomKind::RBracket => {}
            AtomKind::Math { .. } | AtomKind::Op { .. } | AtomKind::Number | AtomKind::Prime => {
                has_math_content = true;
            }
            AtomKind::Word => {
                let w = &input[atoms[k].start..atoms[k].end];
                if w.chars().count() == 1 || is_bare_math_func(w) || is_differential(w) {
                    has_math_content = true;
                } else {
                    return false;
                }
            }
            AtomKind::Punct => {
                if &input[atoms[k].start..atoms[k].end] != "," {
                    return false;
                }
            }
            _ => return false,
        }
    }
    has_math_content
}

fn is_valid_math_rhs(atoms: &[Atom], op_idx: usize, input: &str) -> bool {
    let Some(rhs) = next_non_ws(atoms, op_idx + 1) else {
        return false;
    };
    match atoms[rhs].kind {
        AtomKind::Math { .. } | AtomKind::Number => true,
        AtomKind::Op { .. } => {
            // Unary + or - or \pm before math (e.g. = -1, = \pm \sqrt...)
            let op_s = &input[atoms[rhs].start..atoms[rhs].end];
            if matches!(op_s, "+" | "-" | r"\pm" | r"\mp") {
                is_valid_math_rhs(atoms, rhs, input)
            } else {
                false
            }
        }
        AtomKind::Word => {
            let w = &input[atoms[rhs].start..atoms[rhs].end];
            if is_differential(w) {
                return true;
            }
            if is_bare_math_func(w) {
                if let Some(after) = next_non_ws(atoms, rhs + 1) {
                    return matches!(
                        atoms[after].kind,
                        AtomKind::LParen | AtomKind::Math { .. } | AtomKind::Number | AtomKind::Word
                    );
                }
                return false;
            }
            if w.chars().count() == 1 {
                if matches!(w, "a" | "I") {
                    // Reject English article/pronoun followed by prose word (e.g. "= a good")
                    if let Some(after) = next_non_ws(atoms, rhs + 1) {
                        if is_prose_word(atoms, after, input) {
                            return false;
                        }
                    }
                }
                return true;
            }
            false
        }
        AtomKind::LParen | AtomKind::LBracket => {
            if let Some(close) = find_matching_paren_forward(atoms, rhs) {
                is_valid_math_paren_group(atoms, rhs, close, input)
            } else {
                false
            }
        }
        _ => false,
    }
}

fn is_valid_math_lhs(atoms: &[Atom], op_idx: usize, input: &str) -> bool {
    let Some(lhs) = prev_non_ws(atoms, op_idx) else {
        return false;
    };
    match atoms[lhs].kind {
        AtomKind::Math { .. } | AtomKind::Number => true,
        AtomKind::Prime => {
            if let Some(before) = prev_non_ws(atoms, lhs) {
                matches!(atoms[before].kind, AtomKind::Word | AtomKind::Math { .. } | AtomKind::RParen)
            } else {
                false
            }
        }
        AtomKind::Word => {
            let w = &input[atoms[lhs].start..atoms[lhs].end];
            w.chars().count() == 1 || is_differential(w)
        }
        AtomKind::RParen | AtomKind::RBracket => {
            if let Some(open) = find_matching_paren_backward(atoms, lhs) {
                is_valid_math_paren_group(atoms, open, lhs, input)
            } else {
                false
            }
        }
        _ => false,
    }
}

/// Extract raw (un-delimited) LaTeX / mathematical formula segments from prose or standalone formulas.
pub fn scan_raw_latex_segments(input: &str) -> Vec<FormulaSegment> {
    if input.is_empty() {
        return Vec::new();
    }

    let raw_toks = lex_raw_tokens(input);
    let atoms = bind_math_atoms(input, &raw_toks);

    // Collect anchor spans [L, R] (atom indices, inclusive)
    let mut spans: Vec<(usize, usize)> = Vec::new();
    for (idx, atom) in atoms.iter().enumerate() {
        let is_anchor = match atom.kind {
            AtomKind::Math { is_anchor, .. } => is_anchor,
            AtomKind::Op { is_anchor } => is_anchor,
            _ => false,
        };
        if is_anchor {
            spans.push((idx, idx));
        }
    }

    if spans.is_empty() {
        return vec![FormulaSegment {
            is_math: false,
            is_block: false,
            text: input.to_string(),
            start_byte: 0,
            end_byte: input.len(),
        }];
    }

    // Expand each anchor left and right
    let mut expanded: Vec<(usize, usize)> = Vec::with_capacity(spans.len());
    for (mut l, mut r) in spans {
        // Expand right
        loop {
            let Some(nxt) = next_non_ws(&atoms, r + 1) else {
                break;
            };
            match atoms[nxt].kind {
                AtomKind::Math { .. } => {
                    r = nxt;
                }
                AtomKind::Op { .. } => {
                    if !is_prose_hyphen_or_slash(&atoms, nxt, input) && is_valid_math_rhs(&atoms, nxt, input) {
                        r = nxt;
                    } else {
                        break;
                    }
                }
                AtomKind::Number => {
                    let attached = atoms[r].end == atoms[nxt].start;
                    let after_op = matches!(atoms[r].kind, AtomKind::Op { .. });
                    let followed_by_math_or_op = next_non_ws(&atoms, nxt + 1).map_or(false, |k| {
                        matches!(atoms[k].kind, AtomKind::Math { .. })
                            || (matches!(atoms[k].kind, AtomKind::Op { .. }) && is_valid_math_rhs(&atoms, k, input))
                            || (atoms[k].kind == AtomKind::Word && is_differential(&input[atoms[k].start..atoms[k].end]))
                    });
                    if attached || after_op || followed_by_math_or_op {
                        r = nxt;
                    } else {
                        break;
                    }
                }
                AtomKind::Word => {
                    let w = &input[atoms[nxt].start..atoms[nxt].end];
                    if is_differential(w) {
                        r = nxt;
                    } else if is_bare_math_func(w) {
                        let ok = next_non_ws(&atoms, nxt + 1).map_or(false, |k| {
                            matches!(
                                atoms[k].kind,
                                AtomKind::LParen | AtomKind::Math { .. } | AtomKind::Number
                            ) || (atoms[k].kind == AtomKind::Word
                                && input[atoms[k].start..atoms[k].end].chars().count() == 1)
                        });
                        if ok {
                            r = nxt;
                        } else {
                            break;
                        }
                    } else if w.chars().count() == 1 {
                        let attached = atoms[r].end == atoms[nxt].start;
                        let after_op = matches!(atoms[r].kind, AtomKind::Op { .. });
                        let after_prefix = matches!(atoms[r].kind, AtomKind::Math { is_prefix: true, .. });
                        let followed_by_prose = next_non_ws(&atoms, nxt + 1)
                            .map_or(false, |k| is_prose_word(&atoms, k, input));
                        let followed_by_math = next_non_ws(&atoms, nxt + 1).map_or(false, |k| {
                            matches!(atoms[k].kind, AtomKind::Math { .. } | AtomKind::Prime)
                                || (matches!(atoms[k].kind, AtomKind::Op { .. })
                                    && is_valid_math_rhs(&atoms, k, input))
                                || (atoms[k].kind == AtomKind::Word
                                    && is_differential(&input[atoms[k].start..atoms[k].end]))
                                || (atoms[k].kind == AtomKind::LParen
                                    && atoms[nxt].end == atoms[k].start
                                    && find_matching_paren_forward(&atoms, k)
                                        .map_or(false, |c| is_valid_math_paren_group(&atoms, k, c, input)))
                        });
                        if attached
                            || after_op
                            || followed_by_math
                            || (after_prefix && !(matches!(w, "a" | "I") && followed_by_prose))
                        {
                            r = nxt;
                        } else {
                            break;
                        }
                    } else {
                        break;
                    }
                }
                AtomKind::LParen | AtomKind::LBracket => {
                    if let Some(close) = find_matching_paren_forward(&atoms, nxt) {
                        if is_valid_math_paren_group(&atoms, nxt, close, input) {
                            let attached = atoms[r].end == atoms[nxt].start;
                            let after_op = matches!(atoms[r].kind, AtomKind::Op { .. });
                            let after_math = matches!(atoms[r].kind, AtomKind::Math { .. });
                            if attached || after_op || after_math {
                                r = close;
                                continue;
                            }
                        }
                    }
                    break;
                }
                AtomKind::Prime => {
                    if atoms[r].end == atoms[nxt].start
                        && !(nxt + 1 < atoms.len()
                            && atoms[nxt].end == atoms[nxt + 1].start
                            && atoms[nxt + 1].kind == AtomKind::Word)
                    {
                        r = nxt;
                    } else {
                        break;
                    }
                }
                _ => break,
            }
        }

        // Expand left
        loop {
            let Some(prv) = prev_non_ws(&atoms, l) else {
                break;
            };
            match atoms[prv].kind {
                AtomKind::Math { .. } => {
                    l = prv;
                }
                AtomKind::Op { .. } => {
                    if !is_prose_hyphen_or_slash(&atoms, prv, input) {
                        if is_valid_math_lhs(&atoms, prv, input) {
                            l = prv;
                            continue;
                        }
                        // Allow leading unary +/-/\pm before math if preceded by start/punct/prose-space
                        let op_s = &input[atoms[prv].start..atoms[prv].end];
                        if matches!(op_s, "+" | "-" | r"\pm" | r"\mp") {
                            let prev_is_boundary = prev_non_ws(&atoms, prv).map_or(true, |b| {
                                matches!(atoms[b].kind, AtomKind::Punct | AtomKind::ProseLocked | AtomKind::Other)
                                    || is_prose_word(&atoms, b, input)
                            });
                            if prev_is_boundary && (atoms[prv].end == atoms[l].start || op_s.starts_with('\\')) {
                                l = prv;
                                continue;
                            }
                        }
                    }
                    break;
                }
                AtomKind::Word => {
                    let w = &input[atoms[prv].start..atoms[prv].end];
                    if is_bare_math_func(w) {
                        l = prv;
                    } else if w.chars().count() == 1 {
                        let attached = atoms[prv].end == atoms[l].start;
                        let before_op = matches!(atoms[l].kind, AtomKind::Op { .. });
                        let preceded_by_op_or_math = prev_non_ws(&atoms, prv).map_or(false, |b| {
                            matches!(atoms[b].kind, AtomKind::Op { .. } | AtomKind::Math { .. })
                        });
                        if attached || before_op || preceded_by_op_or_math {
                            l = prv;
                        } else {
                            break;
                        }
                    } else {
                        break;
                    }
                }
                AtomKind::Number => {
                    let attached = atoms[prv].end == atoms[l].start;
                    let before_op = matches!(atoms[l].kind, AtomKind::Op { .. });
                    let preceded_by_op = prev_non_ws(&atoms, prv)
                        .map_or(false, |b| matches!(atoms[b].kind, AtomKind::Op { .. }));
                    if attached || before_op || preceded_by_op {
                        l = prv;
                    } else {
                        break;
                    }
                }
                AtomKind::RParen | AtomKind::RBracket => {
                    if let Some(open) = find_matching_paren_backward(&atoms, prv) {
                        if is_valid_math_paren_group(&atoms, open, prv, input) {
                            let attached = atoms[prv].end == atoms[l].start;
                            let before_op = matches!(atoms[l].kind, AtomKind::Op { .. });
                            if attached || before_op {
                                l = open;
                                continue;
                            }
                        }
                    }
                    break;
                }
                AtomKind::Prime => {
                    if let Some(before) = prev_non_ws(&atoms, prv) {
                        if matches!(atoms[before].kind, AtomKind::Word | AtomKind::Math { .. } | AtomKind::RParen)
                            && atoms[before].end == atoms[prv].start
                        {
                            l = prv;
                            continue;
                        }
                    }
                    break;
                }
                _ => break,
            }
        }

        expanded.push((l, r));
    }

    // Merge overlapping or whitespace-only separated spans
    expanded.sort_by_key(|&(l, r)| (l, r));
    let mut merged_spans: Vec<(usize, usize)> = Vec::new();
    for (l, r) in expanded {
        if let Some(last) = merged_spans.last_mut() {
            if l <= last.1 {
                if r > last.1 {
                    last.1 = r;
                }
                continue;
            }
            // Check if gap (last.1 + 1 .. l) is purely whitespace
            if atoms[last.1 + 1..l].iter().all(|a| a.kind == AtomKind::Whitespace) {
                last.1 = r;
                continue;
            }
        }
        merged_spans.push((l, r));
    }

    // Build FormulaSegments from merged byte ranges
    let mut byte_spans: Vec<(usize, usize)> = merged_spans
        .into_iter()
        .map(|(l, r)| (atoms[l].start, atoms[r].end))
        .collect();

    // Merge any overlapping byte spans
    let mut final_ranges: Vec<(usize, usize)> = Vec::new();
    for (sb, eb) in byte_spans.drain(..) {
        if let Some(last) = final_ranges.last_mut() {
            if sb <= last.1 {
                if eb > last.1 {
                    last.1 = eb;
                }
                continue;
            }
        }
        final_ranges.push((sb, eb));
    }

    // Determine whether there is any non-whitespace plain text outside math spans
    let mut has_surrounding_text = false;
    let mut check_cursor = 0usize;
    for &(sb, eb) in &final_ranges {
        if sb > check_cursor && !input[check_cursor..sb].trim().is_empty() {
            has_surrounding_text = true;
            break;
        }
        check_cursor = eb;
    }
    if !has_surrounding_text && check_cursor < input.len() && !input[check_cursor..].trim().is_empty() {
        has_surrounding_text = true;
    }

    let is_standalone_block = final_ranges.len() == 1 && !has_surrounding_text;

    let mut segments = Vec::new();
    let mut cursor = 0usize;
    for (sb, eb) in final_ranges {
        if sb > cursor {
            segments.push(FormulaSegment {
                is_math: false,
                is_block: false,
                text: input[cursor..sb].to_string(),
                start_byte: cursor,
                end_byte: sb,
            });
        }
        let raw_math = input[sb..eb].trim();
        let normalized = normalize_latex(raw_math);
        segments.push(FormulaSegment {
            is_math: true,
            is_block: is_standalone_block,
            text: normalized,
            start_byte: sb,
            end_byte: eb,
        });
        cursor = eb;
    }

    if cursor < input.len() {
        segments.push(FormulaSegment {
            is_math: false,
            is_block: false,
            text: input[cursor..].to_string(),
            start_byte: cursor,
            end_byte: input.len(),
        });
    }

    segments
}

/// Check whether a paragraph or table cell is a standalone raw LaTeX mathematical formula (without $ delimiter)
pub fn is_pure_latex_formula(s: &str) -> bool {
    let t = s.trim();
    if t.is_empty() {
        return false;
    }

    // 1. Standard LaTeX delimiters covering the whole string
    if (t.starts_with(r"\[") && t.ends_with(r"\]")) || (t.starts_with(r"\(") && t.ends_with(r"\)")) {
        return true;
    }

    // 2. Run raw LaTeX segmenter: pure formula iff it yields a single math segment covering the trimmed string
    let segs = scan_raw_latex_segments(t);
    segs.len() == 1 && segs[0].is_math
}

/// Tokenizer text scanner:
/// 1. Extract $...$, $$...$$, \[...\], \(...\)
/// 2. Also detect standalone or prose-embedded raw LaTeX formulas cleanly.
pub fn scan_text_zero_copy(input: &str) -> Vec<FormulaSegment> {
    let has_dollar = input.contains('$');
    let has_bracket_math = input.contains(r"\[") || input.contains(r"\(");

    if !has_dollar && !has_bracket_math {
        return scan_raw_latex_segments(input);
    }

    let bytes = input.as_bytes();
    let len = bytes.len();
    let mut segments = Vec::new();

    let mut cursor = 0;
    let mut text_start = 0;

    while cursor < len {
        let b = bytes[cursor];

        // 1. Check Code Block ``` or `
        if b == b'`' {
            if cursor + 2 < len && bytes[cursor + 1] == b'`' && bytes[cursor + 2] == b'`' {
                cursor += 3;
                while cursor + 2 < len {
                    if bytes[cursor] == b'`' && bytes[cursor + 1] == b'`' && bytes[cursor + 2] == b'`' {
                        cursor += 3;
                        break;
                    }
                    cursor += 1;
                }
                continue;
            } else {
                cursor += 1;
                while cursor < len {
                    if bytes[cursor] == b'`' {
                        cursor += 1;
                        break;
                    }
                    cursor += 1;
                }
                continue;
            }
        }

        // 2. Escape character \$
        if b == b'\\' && cursor + 1 < len && bytes[cursor + 1] == b'$' {
            cursor += 2;
            continue;
        }

        // 3. LaTeX display block: \[ ... \]
        if b == b'\\' && cursor + 1 < len && bytes[cursor + 1] == b'[' {
            let math_open = cursor;
            let content_start = cursor + 2;
            let mut search = content_start;
            let mut found_close = None;

            while search + 1 < len {
                if bytes[search] == b'\\' && bytes[search + 1] == b']' {
                    found_close = Some(search);
                    break;
                }
                search += 1;
            }

            if let Some(close_idx) = found_close {
                if math_open > text_start {
                    segments.extend(scan_raw_latex_segments(&input[text_start..math_open]));
                }

                let raw_content = &input[content_start..close_idx];
                let normalized = normalize_latex(raw_content.trim());

                segments.push(FormulaSegment {
                    is_math: true,
                    is_block: true,
                    text: normalized,
                    start_byte: math_open,
                    end_byte: close_idx + 2,
                });

                cursor = close_idx + 2;
                text_start = cursor;
                continue;
            }
        }

        // 4. LaTeX inline block: \( ... \)
        if b == b'\\' && cursor + 1 < len && bytes[cursor + 1] == b'(' {
            let math_open = cursor;
            let content_start = cursor + 2;
            let mut search = content_start;
            let mut found_close = None;

            while search + 1 < len {
                if bytes[search] == b'\\' && bytes[search + 1] == b')' {
                    found_close = Some(search);
                    break;
                }
                search += 1;
            }

            if let Some(close_idx) = found_close {
                if math_open > text_start {
                    segments.extend(scan_raw_latex_segments(&input[text_start..math_open]));
                }

                let raw_content = &input[content_start..close_idx];
                let normalized = normalize_latex(raw_content.trim());

                segments.push(FormulaSegment {
                    is_math: true,
                    is_block: false,
                    text: normalized,
                    start_byte: math_open,
                    end_byte: close_idx + 2,
                });

                cursor = close_idx + 2;
                text_start = cursor;
                continue;
            }
        }

        // 5. Display block: $$...$$
        if b == b'$' && cursor + 1 < len && bytes[cursor + 1] == b'$' {
            if is_escaped(bytes, cursor) {
                cursor += 2;
                continue;
            }

            let math_open = cursor;
            let content_start = cursor + 2;
            let mut search = content_start;
            let mut found_close = None;

            while search + 1 < len {
                if bytes[search] == b'$' && bytes[search + 1] == b'$' && !is_escaped(bytes, search) {
                    found_close = Some(search);
                    break;
                }
                search += 1;
            }

            if let Some(close_idx) = found_close {
                if math_open > text_start {
                    segments.extend(scan_raw_latex_segments(&input[text_start..math_open]));
                }

                let raw_content = &input[content_start..close_idx];
                let normalized = normalize_latex(raw_content.trim());

                segments.push(FormulaSegment {
                    is_math: true,
                    is_block: true,
                    text: normalized,
                    start_byte: math_open,
                    end_byte: close_idx + 2,
                });

                cursor = close_idx + 2;
                text_start = cursor;
                continue;
            } else {
                cursor += 2;
                continue;
            }
        }

        // 6. Inline block: $...$
        if b == b'$' {
            if is_escaped(bytes, cursor) {
                cursor += 1;
                continue;
            }

            if cursor > 0 && bytes[cursor - 1].is_ascii_digit() {
                cursor += 1;
                continue;
            }

            if cursor + 1 >= len || is_whitespace(bytes[cursor + 1]) || bytes[cursor + 1] == b'$' {
                cursor += 1;
                continue;
            }

            let math_open = cursor;
            let content_start = cursor + 1;
            let mut search = content_start;
            let mut found_close = None;

            while search < len {
                if bytes[search] == b'$' && !is_escaped(bytes, search) {
                    let prev_ok = !is_whitespace(bytes[search - 1]);
                    let next_ok = if search + 1 < len { !bytes[search + 1].is_ascii_digit() } else { true };

                    if prev_ok && next_ok {
                        found_close = Some(search);
                        break;
                    }
                }
                search += 1;
            }

            if let Some(close_idx) = found_close {
                if math_open > text_start {
                    segments.extend(scan_raw_latex_segments(&input[text_start..math_open]));
                }

                let raw_content = &input[content_start..close_idx];
                let normalized = normalize_latex(raw_content.trim());

                segments.push(FormulaSegment {
                    is_math: true,
                    is_block: false,
                    text: normalized,
                    start_byte: math_open,
                    end_byte: close_idx + 1,
                });

                cursor = close_idx + 1;
                text_start = cursor;
                continue;
            }
        }

        cursor += 1;
    }

    if text_start < len {
        segments.extend(scan_raw_latex_segments(&input[text_start..len]));
    }

    segments
}

#[inline(always)]
fn is_whitespace(b: u8) -> bool {
    b == b' ' || b == b'\t' || b == b'\n' || b == b'\r'
}

#[inline(always)]
fn is_escaped(bytes: &[u8], pos: usize) -> bool {
    let mut backslashes = 0;
    let mut i = pos;
    while i > 0 && bytes[i - 1] == b'\\' {
        backslashes += 1;
        i -= 1;
    }
    backslashes % 2 == 1
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_scanner_basic() {
        let text = r"Given function $f(x) = \sin x + \cos x$. Compute $$I = \int_0^1 f(x)dx$$ with price \$100.";
        let segments = scan_text_zero_copy(text);

        assert_eq!(segments.len(), 5);
        assert!(!segments[0].is_math);
        assert_eq!(segments[0].text, "Given function ");

        assert!(segments[1].is_math);
        assert!(!segments[1].is_block);
        assert_eq!(segments[1].text, r"f(x) = \sin\, x + \cos\, x");

        assert!(!segments[2].is_math);
        assert_eq!(segments[2].text, ". Compute ");

        assert!(segments[3].is_math);
        assert!(segments[3].is_block);
        assert_eq!(segments[3].text, r"I = \int_0^1 f(x)dx");

        assert!(!segments[4].is_math);
        assert_eq!(segments[4].text, r" with price \$100.");
    }

    #[test]
    fn test_pure_raw_latex() {
        let raw = r"ax^2 + bx + c = 0 \implies x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}";
        let segments = scan_text_zero_copy(raw);

        assert_eq!(segments.len(), 1);
        assert!(segments[0].is_math);
        assert!(segments[0].is_block);
        assert_eq!(segments[0].text, raw);
        assert!(is_pure_latex_formula(raw));
    }

    #[test]
    fn test_bracket_latex() {
        let text = r"See \[ \int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2} \] and \( a + b = c \)";
        let segments = scan_text_zero_copy(text);

        assert_eq!(segments.len(), 4);
        assert!(!segments[0].is_math);
        assert!(segments[1].is_math);
        assert!(segments[1].is_block);
        assert!(!segments[2].is_math);
        assert!(segments[3].is_math);
        assert!(!segments[3].is_block);
    }

    #[test]
    fn test_mixed_english_raw_latex() {
        let cases = [
            (
                r"To evaluate the behavior of the system, observe that x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}, as a foundational principle.",
                "To evaluate the behavior of the system, observe that ",
                r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
                ", as a foundational principle.",
            ),
            (
                r"In theoretical physics and mathematics, we often encounter \int_{0}^{\infty} x^2 dx, for any continuous and differentiable function.",
                "In theoretical physics and mathematics, we often encounter ",
                r"\int_{0}^{\infty} x^2 dx",
                ", for any continuous and differentiable function.",
            ),
            (
                r"A classic result in classical mechanics and analysis states: \nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon_0}, which holds true across various domains.",
                "A classic result in classical mechanics and analysis states: ",
                r"\nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon_0}",
                ", which holds true across various domains.",
            ),
            (
                r"Consider the fundamental relation given by \oint_C \vec{B} \cdot d\vec{l} = \mu_0 I_{enc}, which holds true across various domains.",
                "Consider the fundamental relation given by ",
                r"\oint_C \vec{B} \cdot d\vec{l} = \mu_0 I_{enc}",
                ", which holds true across various domains.",
            ),
            (
                r"Consider the fundamental relation given by \frac{d}{dx} e^x = e^x, for any continuous and differentiable function.",
                "Consider the fundamental relation given by ",
                r"\frac{d}{dx} e^x = e^x",
                ", for any continuous and differentiable function.",
            ),
            (
                r"A classic result in classical mechanics and analysis states: a^2 + b^2 = c^2, as a foundational principle.",
                "A classic result in classical mechanics and analysis states: ",
                "a^2 + b^2 = c^2",
                ", as a foundational principle.",
            ),
            (
                r"From first principles, one can directly derive E = mc^2, which holds true across various domains.",
                "From first principles, one can directly derive ",
                "E = mc^2",
                ", which holds true across various domains.",
            ),
            (
                r"This expression plays a crucial role in modern science: e^{i\pi} + 1 = 0, which holds true across various domains.",
                "This expression plays a crucial role in modern science: ",
                r"e^{i\pi} + 1 = 0",
                ", which holds true across various domains.",
            ),
            (
                r"By applying standard analytical methods, it follows that F = G \frac{m_1 m_2}{r^2}, under ideal physical assumptions.",
                "By applying standard analytical methods, it follows that ",
                r"F = G \frac{m_1 m_2}{r^2}",
                ", under ideal physical assumptions.",
            ),
            (
                r"Furthermore, under boundary conditions, we obtain \sum_{i=1}^{n} i = \frac{n(n+1)}{2}, for any continuous and differentiable function.",
                "Furthermore, under boundary conditions, we obtain ",
                r"\sum_{i=1}^{n} i = \frac{n(n+1)}{2}",
                ", for any continuous and differentiable function.",
            ),
            (
                r"This expression plays a crucial role in modern science: \lim_{x \to 0} \frac{\sin x}{x} = 1, as a foundational principle.",
                "This expression plays a crucial role in modern science: ",
                r"\lim_{x \to 0}\, \frac{\sin\, x}{x} = 1",
                ", as a foundational principle.",
            ),
        ];

        for (input, prefix, math, suffix) in cases {
            assert!(!is_pure_latex_formula(input), "Should NOT be pure formula: {}", input);
            let segs = scan_text_zero_copy(input);
            assert_eq!(segs.len(), 3, "Failed len for: {} -> {:?}", input, segs);
            assert!(!segs[0].is_math);
            assert_eq!(segs[0].text, prefix);
            assert!(segs[1].is_math);
            assert!(!segs[1].is_block);
            assert_eq!(segs[1].text, math);
            assert!(!segs[2].is_math);
            assert_eq!(segs[2].text, suffix);
        }
    }

    #[test]
    fn test_no_false_positives_on_prose_paths_snakecase() {
        let non_math = [
            r"Open file C:\tools\include\bar\test.txt to inspect.",
            "This is a well-known end-to-end solution for my_variable_name.",
            "In 2026, it's important that you don't break anything.",
            "Cho phương trình bậc hai với hệ số thực.",
        ];
        for text in non_math {
            let segs = scan_text_zero_copy(text);
            assert!(!segs.iter().any(|s| s.is_math), "False positive on: {} -> {:?}", text, segs);
        }
    }
}
