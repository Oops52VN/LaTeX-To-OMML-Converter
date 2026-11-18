use crate::docx_engine::preview_patch::patch_docx_settings;
use crate::docx_engine::xml_stream::{scan_formulas_in_document_xml, transform_document_xml};
use crate::error::QuastResult;
use rayon::prelude::*;
use std::collections::{HashMap, HashSet};
use std::fs::File;
use std::io::{BufReader, BufWriter, Read, Write};
use std::path::Path;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use zip::write::SimpleFileOptions;
use zip::{ZipArchive, ZipWriter};

/// Extract all unique mathematical formulas across docx files in parallel
/// Uses Rayon's lock-free Map-Reduce architecture: each thread collects into a local HashSet, then merges
pub fn extract_unique_formulas_from_batch(docx_paths: &[String]) -> Vec<String> {
    let unique_set: HashSet<String> = docx_paths
        .par_iter()
        .map(|path_str| {
            let mut local_set = HashSet::new();
            if let Ok(file) = File::open(path_str) {
                if let Ok(mut archive) = ZipArchive::new(BufReader::new(file)) {
                    if let Ok(mut doc_entry) = archive.by_name("word/document.xml") {
                        let mut xml_bytes = Vec::with_capacity(doc_entry.size() as usize);
                        if doc_entry.read_to_end(&mut xml_bytes).is_ok() {
                            if let Ok(formulas) = scan_formulas_in_document_xml(&xml_bytes) {
                                for f in formulas {
                                    local_set.insert(f);
                                }
                            }
                        }
                    }
                }
            }
            local_set
        })
        .reduce(HashSet::new, |mut acc, item| {
            acc.extend(item);
            acc
        });

    let mut result: Vec<String> = unique_set.into_iter().collect();
    result.sort();
    result
}

/// Convert a single docx file: transform word/document.xml and raw_copy other bundled entries
pub fn convert_single_docx<P: AsRef<Path>, Q: AsRef<Path>>(
    src_path: P,
    dst_path: Q,
    omml_map: &HashMap<String, String>,
) -> QuastResult<()> {
    let src_file = File::open(src_path.as_ref())?;
    let mut zip_in = ZipArchive::new(BufReader::new(src_file))?;

    let dst_file = File::create(dst_path.as_ref())?;
    let mut zip_out = ZipWriter::new(BufWriter::new(dst_file));

    let file_count = zip_in.len();

    for i in 0..file_count {
        let name = {
            let entry = zip_in.by_index(i)?;
            entry.name().to_string()
        };

        if name == "word/document.xml" {
            let mut entry = zip_in.by_index(i)?;
            let mut xml_bytes = Vec::with_capacity(entry.size() as usize);
            entry.read_to_end(&mut xml_bytes)?;

            let transformed_xml = transform_document_xml(&xml_bytes, omml_map)?;

            let options = SimpleFileOptions::default()
                .compression_method(zip::CompressionMethod::Deflated);
            zip_out.start_file(&name, options)?;
            zip_out.write_all(&transformed_xml)?;
        } else {
            // Raw copy uncompressed entries directly for images (media) and styles/settings
            let entry = zip_in.by_index_raw(i)?;
            zip_out.raw_copy_file(entry)?;
        }
    }

    zip_out.finish()?;
    Ok(())
}

/// Result for each individual file in batch
#[derive(Debug, Clone)]
pub struct BatchResult {
    pub input_path: String,
    pub output_path: String,
    pub success: bool,
    pub error_msg: Option<String>,
}

/// Execute batch docx conversion in parallel using Rayon
pub fn convert_batch_parallel(
    inputs: &[String],
    output_dir: &str,
    omml_map: &HashMap<String, String>,
    progress_counter: Option<Arc<AtomicUsize>>,
) -> Vec<BatchResult> {
    let out_dir_path = Path::new(output_dir);

    inputs
        .par_iter()
        .map(|in_path| {
            let path_obj = Path::new(in_path);
            let file_name = path_obj
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("document.docx");

            let out_name = if file_name.starts_with("OMML_") {
                format!("Converted_{file_name}")
            } else {
                format!("OMML_{file_name}")
            };

            let out_path = out_dir_path.join(out_name);
            let out_path_str = out_path.to_string_lossy().to_string();

            let mut success = true;
            let mut error_msg = None;

            if let Err(e) = convert_single_docx(in_path, &out_path, omml_map) {
                success = false;
                error_msg = Some(e.to_string());
            }

            if let Some(ref counter) = progress_counter {
                counter.fetch_add(1, Ordering::Relaxed);
            }

            BatchResult {
                input_path: in_path.clone(),
                output_path: out_path_str,
                success,
                error_msg,
            }
        })
        .collect()
}

/// Preprocess batch of docx files for preview in WebMainWindow in parallel
pub fn patch_preview_batch_parallel(
    inputs: &[String],
    temp_dir: &str,
) -> Vec<(String, String, bool)> {
    let temp_dir_path = Path::new(temp_dir);

    inputs
        .par_iter()
        .map(|in_path| {
            let path_obj = Path::new(in_path);
            let stem = path_obj
                .file_stem()
                .and_then(|n| n.to_str())
                .unwrap_or("doc");
            let out_name = format!("quast_bg_{}_{}.docx", stem, fast_id());
            let out_path = temp_dir_path.join(out_name);
            let out_str = out_path.to_string_lossy().to_string();

            let res = patch_docx_settings(in_path, &out_path);
            let ok = res.is_ok();

            (in_path.clone(), out_str, ok)
        })
        .collect()
}

fn fast_id() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos() as u64)
        .unwrap_or(0)
}
