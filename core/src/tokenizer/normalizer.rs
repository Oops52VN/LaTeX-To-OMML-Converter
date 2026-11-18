use once_cell::sync::Lazy;
use regex::Regex;

static FUNC_PATTERN: Lazy<Regex> = Lazy::new(|| {
    Regex::new(
        r"\\(sin|cos|tan|cot|sec|csc|log|ln|lim|arcsin|arccos|arctan|sinh|cosh|tanh|coth)((?:[_^](?:[^{}\s]+|\{[^}]+\}))*)\s+([a-zA-Z0-9\\])"
    ).expect("Valid function normalization regex")
});

/// Normalize trigonometric / logarithmic functions in LaTeX formulas
/// Example: `\sin x` -> `\sin\, x`
pub fn normalize_latex(latex: &str) -> String {
    if !latex.contains('\\') {
        return latex.to_string();
    }

    FUNC_PATTERN.replace_all(latex, r"\$1$2\, $3").into_owned()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normalize_latex() {
        let input = r"\sin x + \cos^2(y) - \log_{10} z";
        let expected = r"\sin\, x + \cos^2(y) - \log_{10}\, z";
        assert_eq!(normalize_latex(input), expected);
    }
}
