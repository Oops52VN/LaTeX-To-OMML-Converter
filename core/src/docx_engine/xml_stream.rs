use crate::error::{QuastError, QuastResult};
use crate::tokenizer::scanner::scan_text_zero_copy;
use quick_xml::events::{BytesEnd, BytesStart, BytesText, Event};
use quick_xml::reader::Reader;
use quick_xml::writer::Writer;
use std::collections::HashMap;
use std::io::{Cursor, Write};

/// Extract list of all LaTeX formulas appearing in `word/document.xml`
pub fn scan_formulas_in_document_xml(xml_bytes: &[u8]) -> QuastResult<Vec<String>> {
    let mut reader = Reader::from_reader(Cursor::new(xml_bytes));
    reader.config_mut().trim_text(false);

    let mut buf = Vec::new();
    let mut formulas = Vec::new();

    let mut in_p = false;
    let mut p_text = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let local = e.local_name();
                if local.as_ref() == b"p" {
                    in_p = true;
                    p_text.clear();
                } else if in_p && local.as_ref() == b"t" {
                    if let Ok(t_event) = reader.read_event_into(&mut Vec::new()) {
                        if let Event::Text(t) = t_event {
                            if let Ok(s) = t.unescape() {
                                p_text.push_str(&s);
                            }
                        }
                    }
                }
            }
            Ok(Event::Empty(e)) => {
                if in_p {
                    let local = e.local_name();
                    if local.as_ref() == b"br" {
                        p_text.push('\n');
                    } else if local.as_ref() == b"tab" {
                        p_text.push('\t');
                    }
                }
            }
            Ok(Event::End(e)) => {
                let local = e.local_name();
                if local.as_ref() == b"p" {
                    in_p = false;
                    let segments = scan_text_zero_copy(&p_text);
                    for seg in segments {
                        if seg.is_math {
                            formulas.push(seg.text);
                        }
                    }
                }
            }
            Ok(Event::Eof) => break,
            Ok(_) => {}
            Err(e) => return Err(QuastError::Xml(e)),
        }
        buf.clear();
    }

    Ok(formulas)
}

/// Transform and embed OMML blocks into `word/document.xml`
pub fn transform_document_xml(
    input_xml: &[u8],
    omml_map: &HashMap<String, String>,
) -> QuastResult<Vec<u8>> {
    let mut reader = Reader::from_reader(Cursor::new(input_xml));
    reader.config_mut().trim_text(false);

    let mut writer = Writer::new(Cursor::new(Vec::with_capacity(input_xml.len() + 1024)));
    let mut buf = Vec::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) if e.local_name().as_ref() == b"p" => {
                let p_start = e.into_owned();
                process_paragraph(&mut reader, &mut writer, p_start, omml_map)?;
            }
            Ok(Event::Eof) => break,
            Ok(event) => {
                writer.write_event(event)?;
            }
            Err(e) => return Err(QuastError::Xml(e)),
        }
        buf.clear();
    }

    Ok(writer.into_inner().into_inner())
}

/// Process a `<w:p>` tag: preserve `<w:pPr>`, replace math-containing text with OMML nodes
fn process_paragraph<R: std::io::BufRead, W: Write>(
    reader: &mut Reader<R>,
    writer: &mut Writer<W>,
    p_start: BytesStart<'static>,
    omml_map: &HashMap<String, String>,
) -> QuastResult<()> {
    let mut inner_events: Vec<Event<'static>> = Vec::new();
    let mut depth = 1;
    let mut p_text = String::new();
    let mut p_pr_events: Vec<Event<'static>> = Vec::new();
    let mut in_p_pr = false;

    let mut buf = Vec::new();
    while depth > 0 {
        match reader.read_event_into(&mut buf)? {
            Event::Start(e) => {
                let local = e.local_name();
                if local.as_ref() == b"p" {
                    depth += 1;
                } else if local.as_ref() == b"pPr" && depth == 1 {
                    in_p_pr = true;
                } else if local.as_ref() == b"t" && depth == 1 {
                    let mut t_buf = Vec::new();
                    let t_event = reader.read_event_into(&mut t_buf)?;
                    if let Event::Text(ref t) = t_event {
                        if let Ok(s) = t.unescape() {
                            p_text.push_str(&s);
                        }
                    }
                    let owned_t_event = t_event.into_owned();
                    let end_t = reader.read_event_into(&mut Vec::new())?.into_owned();

                    let cloned_e = e.to_owned();
                    inner_events.push(Event::Start(cloned_e));
                    inner_events.push(owned_t_event);
                    inner_events.push(end_t);
                    continue;
                }

                let owned = Event::Start(e.into_owned());
                if in_p_pr {
                    p_pr_events.push(owned.clone());
                }
                inner_events.push(owned);
            }
            Event::Empty(e) => {
                let local = e.local_name();
                if depth == 1 {
                    if local.as_ref() == b"br" {
                        p_text.push('\n');
                    } else if local.as_ref() == b"tab" {
                        p_text.push('\t');
                    }
                }
                let owned = Event::Empty(e.into_owned());
                if in_p_pr {
                    p_pr_events.push(owned.clone());
                }
                inner_events.push(owned);
            }
            Event::End(e) => {
                let is_p = e.local_name().as_ref() == b"p";
                let is_p_pr = e.local_name().as_ref() == b"pPr";

                if is_p {
                    depth -= 1;
                    if depth == 0 {
                        break;
                    }
                } else if is_p_pr && depth == 1 {
                    in_p_pr = false;
                }

                let owned = Event::End(e.into_owned());
                if in_p_pr || is_p_pr {
                    p_pr_events.push(owned.clone());
                }
                inner_events.push(owned);
            }
            Event::Text(t) => {
                let owned = Event::Text(t.into_owned());
                if in_p_pr {
                    p_pr_events.push(owned.clone());
                }
                inner_events.push(owned);
            }
            Event::Eof => break,
            other => {
                let owned = other.into_owned();
                if in_p_pr {
                    p_pr_events.push(owned.clone());
                }
                inner_events.push(owned);
            }
        }
        buf.clear();
    }

    // Parse formula blocks in paragraph (supporting $..$, $$..$$, \[..\], \(..\), and raw LaTeX)
    let segments = scan_text_zero_copy(&p_text);
    let has_math = segments.iter().any(|s| s.is_math);

    if !has_math {
        writer.write_event(Event::Start(p_start))?;
        for ev in inner_events {
            writer.write_event(ev)?;
        }
        writer.write_event(Event::End(BytesEnd::new("w:p")))?;
        return Ok(());
    }

    // Begin writing new <w:p> with preserved <w:pPr>
    writer.write_event(Event::Start(p_start))?;
    for p_pr_ev in p_pr_events {
        writer.write_event(p_pr_ev)?;
    }

    let has_surrounding_text = segments
        .iter()
        .any(|s| !s.is_math && !s.text.trim().is_empty());

    // Write alternating text elements and OMML blocks
    for seg in segments {
        if !seg.is_math {
            write_text_run(writer, &seg.text)?;
        } else {
            // Lookup precompiled OMML
            if let Some(omml_xml) = omml_map.get(&seg.text) {
                let inline_mode = !seg.is_block || has_surrounding_text;
                write_omml_for_context(writer.get_mut(), omml_xml, inline_mode)?;
            } else {
                // Fallback if OMML is not found
                let fallback = if seg.is_block {
                    format!("$${}$$", seg.text)
                } else {
                    format!("${}$", seg.text)
                };
                write_text_run(writer, &fallback)?;
            }
        }
    }

    writer.write_event(Event::End(BytesEnd::new("w:p")))?;
    Ok(())
}

/// Emit OMML as inline `<m:oMath>` when embedded in prose, or `<m:oMathPara>` when standalone display math.
fn write_omml_for_context<W: Write>(writer: &mut W, omml_xml: &str, inline: bool) -> QuastResult<()> {
    let trimmed = omml_xml.trim();
    if inline {
        if trimmed.starts_with("<m:oMathPara") {
            let start = trimmed.find("<m:oMath>").or_else(|| trimmed.find("<m:oMath "));
            if let (Some(s_idx), Some(e_idx)) = (start, trimmed.rfind("</m:oMath>")) {
                let end = e_idx + "</m:oMath>".len();
                let inner = &trimmed[s_idx..end];
                if inner.starts_with("<m:oMath>") {
                    writer.write_all(
                        b"<m:oMath xmlns:m=\"http://schemas.openxmlformats.org/officeDocument/2006/math\" xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">",
                    )?;
                    writer.write_all(&inner.as_bytes()["<m:oMath>".len()..])?;
                    return Ok(());
                }
                writer.write_all(inner.as_bytes())?;
                return Ok(());
            }
        }
        writer.write_all(trimmed.as_bytes())?;
        return Ok(());
    }

    if trimmed.starts_with("<m:oMath>") || trimmed.starts_with("<m:oMath ") {
        writer.write_all(
            b"<m:oMathPara xmlns:m=\"http://schemas.openxmlformats.org/officeDocument/2006/math\" xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">",
        )?;
        writer.write_all(trimmed.as_bytes())?;
        writer.write_all(b"</m:oMathPara>")?;
        return Ok(());
    }

    writer.write_all(trimmed.as_bytes())?;
    Ok(())
}

/// Write plain text segment into `<w:r><w:t>...</w:t></w:r>` structure
/// Supports newlines `\n` (<w:br/>) and indentation `\t` (<w:tab/>)
fn write_text_run<W: Write>(writer: &mut Writer<W>, text: &str) -> QuastResult<()> {
    if text.is_empty() {
        return Ok(());
    }

    for (i, line) in text.split('\n').enumerate() {
        if i > 0 {
            writer.write_event(Event::Start(BytesStart::new("w:r")))?;
            writer.write_event(Event::Empty(BytesStart::new("w:br")))?;
            writer.write_event(Event::End(BytesEnd::new("w:r")))?;
        }

        if !line.is_empty() {
            for (j, part) in line.split('\t').enumerate() {
                if j > 0 {
                    writer.write_event(Event::Start(BytesStart::new("w:r")))?;
                    writer.write_event(Event::Empty(BytesStart::new("w:tab")))?;
                    writer.write_event(Event::End(BytesEnd::new("w:r")))?;
                }

                if !part.is_empty() {
                    writer.write_event(Event::Start(BytesStart::new("w:r")))?;
                    let mut t_start = BytesStart::new("w:t");
                    t_start.push_attribute(("xml:space", "preserve"));
                    writer.write_event(Event::Start(t_start))?;
                    writer.write_event(Event::Text(BytesText::new(part)))?;
                    writer.write_event(Event::End(BytesEnd::new("w:t")))?;
                    writer.write_event(Event::End(BytesEnd::new("w:r")))?;
                }
            }
        }
    }

    Ok(())
}
