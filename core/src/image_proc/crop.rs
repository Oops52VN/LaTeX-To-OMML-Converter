use image::{GrayImage, Luma};

/// Find formula bounding box (dark/black pixels < 128)
/// and crop excess white borders, adding standardized padding for OCR models
pub fn auto_crop_formula(img: &GrayImage, padding: u32) -> (GrayImage, (u32, u32, u32, u32)) {
    let (w, h) = img.dimensions();
    if w == 0 || h == 0 {
        return (img.clone(), (0, 0, w, h));
    }

    let mut min_x = w;
    let mut min_y = h;
    let mut max_x = 0;
    let mut max_y = 0;
    let mut found = false;

    for y in 0..h {
        for x in 0..w {
            let val = img.get_pixel(x, y).0[0];
            // Ink pixel (black or dark gray)
            if val < 128 {
                if x < min_x { min_x = x; }
                if x > max_x { max_x = x; }
                if y < min_y { min_y = y; }
                if y > max_y { max_y = y; }
                found = true;
            }
        }
    }

    if !found {
        // Entirely white image; return original
        return (img.clone(), (0, 0, w, h));
    }

    let crop_w = (max_x - min_x + 1).max(1);
    let crop_h = (max_y - min_y + 1).max(1);

    let out_w = crop_w + 2 * padding;
    let out_h = crop_h + 2 * padding;

    // Create white background image (255)
    let mut out = GrayImage::from_pixel(out_w, out_h, Luma([255]));

    // Copy cropped formula region to center
    for y in 0..crop_h {
        for x in 0..crop_w {
            let src_pixel = img.get_pixel(min_x + x, min_y + y);
            out.put_pixel(padding + x, padding + y, *src_pixel);
        }
    }

    (out, (min_x, min_y, crop_w, crop_h))
}
