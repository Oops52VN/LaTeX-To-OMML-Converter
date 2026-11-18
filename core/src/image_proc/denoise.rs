use image::GrayImage;
use rayon::prelude::*;

/// 3x3 median filter to eliminate salt-and-pepper noise while preserving thin strokes in mathematical formulas
pub fn median_filter_3x3(img: &GrayImage) -> GrayImage {
    let (w, h) = img.dimensions();
    if w < 3 || h < 3 {
        return img.clone();
    }

    let w_usize = w as usize;
    let mut out = img.clone();

    // Process rows in parallel from row 1 to h-2
    out.par_chunks_mut(w_usize)
        .enumerate()
        .for_each(|(y_idx, out_row)| {
            if y_idx == 0 || y_idx == (h as usize - 1) {
                return;
            }

            let y = y_idx as u32;
            for x in 1..(w - 1) {
                let mut p = [
                    img.get_pixel(x - 1, y - 1).0[0],
                    img.get_pixel(x, y - 1).0[0],
                    img.get_pixel(x + 1, y - 1).0[0],
                    img.get_pixel(x - 1, y).0[0],
                    img.get_pixel(x, y).0[0],
                    img.get_pixel(x + 1, y).0[0],
                    img.get_pixel(x - 1, y + 1).0[0],
                    img.get_pixel(x, y + 1).0[0],
                    img.get_pixel(x + 1, y + 1).0[0],
                ];

                out_row[x as usize] = fast_median_9(&mut p);
            }
        });

    out
}

/// Optimal 9-element sorting network to find median element p[4]
#[inline(always)]
fn fast_median_9(p: &mut [u8; 9]) -> u8 {
    macro_default_swap(p, 1, 2);
    macro_default_swap(p, 4, 5);
    macro_default_swap(p, 7, 8);
    macro_default_swap(p, 0, 1);
    macro_default_swap(p, 3, 4);
    macro_default_swap(p, 6, 7);
    macro_default_swap(p, 1, 2);
    macro_default_swap(p, 4, 5);
    macro_default_swap(p, 7, 8);
    macro_default_swap(p, 0, 3);
    macro_default_swap(p, 5, 8);
    macro_default_swap(p, 4, 7);
    macro_default_swap(p, 3, 6);
    macro_default_swap(p, 1, 4);
    macro_default_swap(p, 2, 5);
    macro_default_swap(p, 4, 7);
    macro_default_swap(p, 4, 2);
    macro_default_swap(p, 6, 4);
    macro_default_swap(p, 4, 2);

    p[4]
}

#[inline(always)]
fn macro_default_swap(p: &mut [u8; 9], a: usize, b: usize) {
    if p[a] > p[b] {
        p.swap(a, b);
    }
}
