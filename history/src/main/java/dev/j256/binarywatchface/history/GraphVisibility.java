package dev.j256.binarywatchface.history;

// Generated from design/visibility.json by tools/generate_watchface.py
// Ratios describe reference contrast, not literal alpha or perceived brightness
final class GraphVisibility {
    static final int TRACE_ALPHA = 145;
    static final int MARKS_ALPHA = 168;
    static final int TIME_LABELS_ALPHA = 232;
    static final int STATUS_ALPHA = 245;
    static final int FILL_ALPHA = 12;
    static final int RANGE_ALPHA = 14;
    static final float TRACE_WIDTH = 2.25f;
    static final float MARK_HALF_LENGTH = 5.5f;
    static final float MARK_STROKE_WIDTH = 2.0f;
    static final float MARK_DOT_RADIUS = 2.7f;
    static final float MARK_TRIANGLE_HALF_WIDTH = 3.5f;
    static final float MARK_TRIANGLE_HALF_HEIGHT = 4.0f;
    static final float TIME_LABEL_SIZE = 13.5f;
    static final float DAY_LABEL_SIZE = 11.0f;
    static final float STATUS_SIZE = 10.5f;

    // Face-side values also exercise the final composite in Android rendering tests
    static final int FACE_FAINT_ALPHA = 82;
    static final double FAINT_TRACE_MIN_CONTRAST = 1.35;
    static final double FAINT_MARKS_MIN_CONTRAST = 1.45;
    static final double FAINT_TIME_LABELS_MIN_CONTRAST = 1.9;
    static final double FAINT_TRACE_MIN_RENDERED_CONTRAST = 1.3;
    static final double FAINT_MARKS_MIN_RENDERED_CONTRAST = 1.45;
    static final double FAINT_TIME_LABELS_MIN_RENDERED_CONTRAST = 1.9;
    static final int FACE_SUBTLE_ALPHA = 142;
    static final double SUBTLE_TRACE_MIN_CONTRAST = 2.0;
    static final double SUBTLE_MARKS_MIN_CONTRAST = 2.4;
    static final double SUBTLE_TIME_LABELS_MIN_CONTRAST = 3.8;
    static final double SUBTLE_TRACE_MIN_RENDERED_CONTRAST = 1.8;
    static final double SUBTLE_MARKS_MIN_RENDERED_CONTRAST = 2.4;
    static final double SUBTLE_TIME_LABELS_MIN_RENDERED_CONTRAST = 3.8;
    static final int FACE_CLEAR_ALPHA = 255;
    static final double CLEAR_TRACE_MIN_CONTRAST = 4.5;
    static final double CLEAR_MARKS_MIN_CONTRAST = 6.0;
    static final double CLEAR_TIME_LABELS_MIN_CONTRAST = 11.0;
    static final double CLEAR_TRACE_MIN_RENDERED_CONTRAST = 3.9;
    static final double CLEAR_MARKS_MIN_RENDERED_CONTRAST = 6.0;
    static final double CLEAR_TIME_LABELS_MIN_RENDERED_CONTRAST = 11.0;
    static final int REFERENCE_FOREGROUND = 0xFF28FE14;
    static final int REFERENCE_BACKGROUND = 0xFF000000;

    private GraphVisibility() {}
}
