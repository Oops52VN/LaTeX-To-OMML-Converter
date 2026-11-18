use crate::error::{QuastError, QuastResult};
use quick_xml::events::{BytesStart, Event};
use quick_xml::reader::Reader;
use quick_xml::writer::Writer;
use std::fs::File;
use std::io::{BufReader, BufWriter, Cursor, Read, Write};
use std::path::Path;
use zip::write::SimpleFileOptions;
use zip::{ZipArchive, ZipWriter};

/// Modify `word/settings.xml` to enable Print View, 100% Zoom, and Read-Only Preview
pub fn patch_docx_settings<P: AsRef<Path>, Q: AsRef<Path>>(
    src_path: P,
    dst_path: Q,
) -> QuastResult<bool> {
    let src_file = File::open(src_path.as_ref())?;
    let mut zip_in = ZipArchive::new(BufReader::new(src_file))?;

    let dst_file = File::create(dst_path.as_ref())?;
    let mut zip_out = ZipWriter::new(BufWriter::new(dst_file));

    let mut settings_patched = false;
    let file_count = zip_in.len();

    for i in 0..file_count {
        let name = {
            let entry = zip_in.by_index(i)?;
            entry.name().to_string()
        };

        if name == "word/settings.xml" {
            let mut entry = zip_in.by_index(i)?;
            let mut xml_bytes = Vec::with_capacity(entry.size() as usize + 512);
            entry.read_to_end(&mut xml_bytes)?;

            let modified_xml = patch_settings_xml(&xml_bytes)?;

            let options = SimpleFileOptions::default()
                .compression_method(zip::CompressionMethod::Deflated);
            zip_out.start_file(&name, options)?;
            zip_out.write_all(&modified_xml)?;
            settings_patched = true;
        } else {
            // Copy raw compressed data (raw_copy_file) directly at high speed without decompression & recompression
            let entry = zip_in.by_index_raw(i)?;
            zip_out.raw_copy_file(entry)?;
        }
    }

    zip_out.finish()?;
    Ok(settings_patched)
}

/// Modify XML content of `word/settings.xml` using Quick-XML Streaming
fn patch_settings_xml(input_xml: &[u8]) -> QuastResult<Vec<u8>> {
    let mut reader = Reader::from_reader(Cursor::new(input_xml));
    reader.config_mut().trim_text(false);

    let mut writer = Writer::new(Cursor::new(Vec::with_capacity(input_xml.len() + 256)));
    let mut buf = Vec::new();

    let mut inside_settings = false;
    let mut view_injected = false;

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Decl(d)) => {
                writer.write_event(Event::Decl(d))?;
            }
            Ok(Event::Start(e)) => {
                let local = e.local_name();
                if local.as_ref() == b"settings" {
                    inside_settings = true;
                    writer.write_event(Event::Start(e))?;

                    // Inject <w:view w:val="print"/>, <w:zoom w:percent="100"/>, <w:documentProtection.../>
                    if !view_injected {
                        inject_preview_nodes(&mut writer)?;
                        view_injected = true;
                    }
                } else if inside_settings
                    && (local.as_ref() == b"view"
                        || local.as_ref() == b"zoom"
                        || local.as_ref() == b"documentProtection")
                {
                    // Skip obsolete tags to replace them with the newly injected standard tags
                    reader.read_to_end_into(e.to_end().into_owned().name(), &mut Vec::new())?;
                } else {
                    writer.write_event(Event::Start(e))?;
                }
            }
            Ok(Event::Empty(e)) => {
                let local = e.local_name();
                if inside_settings
                    && (local.as_ref() == b"view"
                        || local.as_ref() == b"zoom"
                        || local.as_ref() == b"documentProtection")
                {
                    // Skip obsolete self-closing tag
                } else {
                    writer.write_event(Event::Empty(e))?;
                }
            }
            Ok(Event::End(e)) => {
                writer.write_event(Event::End(e))?;
            }
            Ok(Event::Eof) => break,
            Ok(other) => {
                writer.write_event(other)?;
            }
            Err(e) => return Err(QuastError::Xml(e)),
        }
        buf.clear();
    }

    Ok(writer.into_inner().into_inner())
}

#[inline]
fn inject_preview_nodes<W: Write>(writer: &mut Writer<W>) -> QuastResult<()> {
    // 1. <w:view w:val="print"/>
    let mut view = BytesStart::new("w:view");
    view.push_attribute(("w:val", "print"));
    writer.write_event(Event::Empty(view))?;

    // 2. <w:zoom w:percent="100"/>
    let mut zoom = BytesStart::new("w:zoom");
    zoom.push_attribute(("w:percent", "100"));
    writer.write_event(Event::Empty(zoom))?;

    // 3. <w:documentProtection w:edit="readOnly" w:enforcement="1"/>
    let mut prot = BytesStart::new("w:documentProtection");
    prot.push_attribute(("w:edit", "readOnly"));
    prot.push_attribute(("w:enforcement", "1"));
    writer.write_event(Event::Empty(prot))?;

    Ok(())
}
