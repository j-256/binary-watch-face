package dev.j256.binarywatchface.history;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffColorFilter;
import android.graphics.Rect;
import android.util.Log;

import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Test;
import org.junit.runner.RunWith;

import static org.junit.Assert.*;

/** Exercise the rendered provider, tint and face opacity together, including pixel coverage */
@RunWith(AndroidJUnit4.class)
public class GraphVisibilityTest {
    private static final int[] FACE_ALPHAS = {GraphVisibility.FACE_FAINT_ALPHA,
            GraphVisibility.FACE_SUBTLE_ALPHA, GraphVisibility.FACE_CLEAR_ALPHA};
    private static final double[] TRACE_FLOORS = {GraphVisibility.FAINT_TRACE_MIN_RENDERED_CONTRAST,
            GraphVisibility.SUBTLE_TRACE_MIN_RENDERED_CONTRAST, GraphVisibility.CLEAR_TRACE_MIN_RENDERED_CONTRAST};
    private static final double[] MARK_FLOORS = {GraphVisibility.FAINT_MARKS_MIN_RENDERED_CONTRAST,
            GraphVisibility.SUBTLE_MARKS_MIN_RENDERED_CONTRAST, GraphVisibility.CLEAR_MARKS_MIN_RENDERED_CONTRAST};
    private static final double[] LABEL_FLOORS = {GraphVisibility.FAINT_TIME_LABELS_MIN_RENDERED_CONTRAST,
            GraphVisibility.SUBTLE_TIME_LABELS_MIN_RENDERED_CONTRAST, GraphVisibility.CLEAR_TIME_LABELS_MIN_RENDERED_CONTRAST};

    @Test public void finalCompositeRetainsContrastAndHierarchyAtWatchSizes() {
        long end = 1_800_000_000_000L;
        StringBuilder failures = new StringBuilder();
        for (HistorySeries.Span span : HistorySeries.Span.values()) {
            HistorySeries series = new HistorySeries(span, end);
            for (long time = series.startMs; time <= end; time += HistorySeries.MINUTE_MS) {
                series.add(new HistorySeries.Sample(time, 80));
            }
            Bitmap trace = GraphRenderer.renderBackground(series, false, "",
                    HistorySettings.Labels.WINDOW, HistorySettings.Markers.NONE);
            Bitmap marked = GraphRenderer.renderBackground(series, false, "",
                    HistorySettings.Labels.WINDOW, HistorySettings.Markers.TICKS);
            for (int width : new int[]{450, 454, 480}) {
                double scale = width / (double) GraphRenderer.BACKGROUND_WIDTH;
                for (int preset = 0; preset < FACE_ALPHAS.length; preset++) {
                    Bitmap face = composite(trace, width, FACE_ALPHAS[preset]);
                    Bitmap marks = composite(marked, width, FACE_ALPHAS[preset]);
                    double traceContrast = peakContrast(face, (int) (100 * scale), (int) (80 * scale),
                            (int) (350 * scale), face.getHeight());
                    double markContrast = peakContrast(marks, 0, (int) (80 * scale), width, marks.getHeight());
                    int traceRow = peakRow(face, width / 2, (int) (80 * scale));
                    double extensionContrast = Math.max(peakContrast(marks, 0, (int) (80 * scale), width, traceRow - 2),
                            peakContrast(marks, 0, traceRow + 3, width, marks.getHeight()));
                    double labelContrast = peakContrast(face, 0, (int) (35 * scale), width, (int) (80 * scale));
                    String context = span + "/" + width + "/" + preset;
                    Log.i("VisibilityTest", "event=visibility span=" + span + " width=" + width + " preset=" + preset
                            + " trace=" + traceContrast + " marks=" + extensionContrast + " intersection=" + markContrast + " labels=" + labelContrast);
                    if (traceContrast < TRACE_FLOORS[preset]) failures.append("Trace floor: ").append(context).append(" = ").append(traceContrast).append('\n');
                    if (extensionContrast < MARK_FLOORS[preset]) failures.append("Mark floor: ").append(context).append(" = ").append(extensionContrast).append('\n');
                    if (labelContrast < LABEL_FLOORS[preset]) failures.append("Label floor: ").append(context).append(" = ").append(labelContrast).append('\n');
                    assertTrue("Trace < marks < timestamps: " + context,
                            traceContrast < extensionContrast && extensionContrast <= markContrast && markContrast < labelContrast);
                    face.recycle();
                    marks.recycle();
                }
            }
            trace.recycle();
            marked.recycle();
        }
        assertEquals(failures.toString(), 0, failures.length());
    }

    private static Bitmap composite(Bitmap provider, int width, int alpha) {
        int height = Math.round(provider.getHeight() * width / (float) provider.getWidth());
        Bitmap result = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(result);
        canvas.drawColor(GraphVisibility.REFERENCE_BACKGROUND);
        Paint tint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
        tint.setColorFilter(new PorterDuffColorFilter(GraphVisibility.REFERENCE_FOREGROUND, PorterDuff.Mode.SRC_IN));
        tint.setAlpha(alpha);
        canvas.drawBitmap(provider, null, new Rect(0, 0, width, height), tint);
        return result;
    }

    private static double peakContrast(Bitmap image, int left, int top, int right, int bottom) {
        double background = luminance(GraphVisibility.REFERENCE_BACKGROUND);
        double peak = 1;
        for (int y = top; y < bottom; y++) for (int x = left; x < right; x++) {
            double pixel = luminance(image.getPixel(x, y));
            peak = Math.max(peak, (Math.max(pixel, background) + 0.05) / (Math.min(pixel, background) + 0.05));
        }
        return peak;
    }

    private static int peakRow(Bitmap image, int x, int top) {
        int peak = top;
        for (int y = top; y < image.getHeight(); y++) {
            if (luminance(image.getPixel(x, y)) > luminance(image.getPixel(x, peak))) peak = y;
        }
        return peak;
    }

    private static double luminance(int color) {
        return 0.2126 * linear(Color.red(color)) + 0.7152 * linear(Color.green(color)) + 0.0722 * linear(Color.blue(color));
    }

    private static double linear(int channel) {
        double value = channel / 255.0;
        return value <= 0.04045 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4);
    }
}
