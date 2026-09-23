package dev.j256.binarywatchface.history;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffXfermode;
import android.graphics.Shader;
import android.graphics.Typeface;

import java.time.ZoneId;
import java.util.Locale;

/** Transparent monochrome image which WFF tints to the selected text color */
public final class GraphRenderer {
    public static final int WIDTH = 476;
    public static final int HEIGHT = 364;
    public static final int BACKGROUND_WIDTH = 450;
    public static final int BACKGROUND_HEIGHT = 300;
    private static final float MARK_HALF_LENGTH = 3.5f;
    private static final float MARK_STROKE_WIDTH = 1.1f;
    private static final int TIME_DETAIL_ALPHA = 210;
    // Keep side labels between the moving bezel tick and the hour row
    private static final float TIME_LABEL_INSET = 66;
    private static final float DAY_LABEL_INSET = 6;
    private static final float TIME_LABEL_BASELINE = 64;
    private static final float TIME_LABEL_SIZE = 10;
    private static final float DAY_LABEL_SIZE = 9;

    private GraphRenderer() {}

    public static Bitmap render(HistorySeries series, boolean demo, String emptyLabel) {
        return render(series, demo, emptyLabel, false, HistorySettings.Labels.RANGE);
    }

    public static Bitmap renderBackground(HistorySeries series, boolean demo, String emptyLabel,
            HistorySettings.Labels labels) {
        return render(series, demo, emptyLabel, true, labels);
    }

    private static Bitmap render(HistorySeries series, boolean demo, String emptyLabel, boolean background,
            HistorySettings.Labels labels) {
        int width = background ? BACKGROUND_WIDTH : WIDTH;
        int height = background ? BACKGROUND_HEIGHT : HEIGHT;
        float left = 16;
        float right = width - left;
        float top = background ? 28 : 79;
        float bottom = background ? height - 12 : height - 40;
        Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(bitmap);
        Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        paint.setColor(Color.WHITE);
        if (series.sampleCount > 0) {
            drawPlot(canvas, paint, series, left, top, right, bottom, background);
            if (background) fadeEdges(canvas, paint, width, height);
            if (background && labels != HistorySettings.Labels.NONE) {
                drawTimeMarks(canvas, paint, series, left, top, right, bottom);
            }
        }
        paint.reset();
        paint.setAntiAlias(true);
        paint.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        paint.setTextSize(background ? 10.5f : 21);
        paint.setColor(Color.WHITE);
        paint.setAlpha(background ? 245 : TIME_DETAIL_ALPHA);
        float captionBaseline = background ? 13.5f : 27;
        long ageMinutes = (series.endMs - series.latestMs) / HistorySeries.MINUTE_MS;
        String range = String.format(Locale.ROOT, "%.0f-%.0f", series.minimum, series.maximum);
        String status = series.sampleCount == 0 ? emptyLabel : series.isStale() ? "STALE " + ageMinutes + "m"
                : labels == HistorySettings.Labels.RANGE
                    ? range + (!demo && ageMinutes > 0 ? " / " + ageMinutes + "m" : " BPM") : "";
        if (background) {
            paint.setTextAlign(Paint.Align.CENTER);
            canvas.drawText(status, width / 2f, captionBaseline, paint);
            if (labels != HistorySettings.Labels.NONE) drawTimeLabels(canvas, paint, series, width);
        } else {
            String header = (demo ? "SAMPLE  /  " : "HEART  /  ")
                    + series.span.label.toUpperCase(Locale.ROOT);
            canvas.drawText(header, left, captionBaseline, paint);
            paint.setTextAlign(Paint.Align.RIGHT);
            canvas.drawText(status, right, captionBaseline, paint);
        }
        return bitmap;
    }

    private static void drawTimeMarks(Canvas canvas, Paint paint, HistorySeries series,
            float left, float top, float right, float bottom) {
        paint.reset();
        paint.setAntiAlias(true);
        paint.setColor(Color.WHITE);
        paint.setAlpha(TIME_DETAIL_ALPHA);
        paint.setStrokeWidth(MARK_STROKE_WIDTH);
        paint.setStrokeCap(Paint.Cap.ROUND);
        double scale = (bottom - top) / (series.upperBound() - series.lowerBound());
        for (HistoryTimeline.Mark mark : HistoryTimeline.marks(series)) {
            float x = (float) (left + (right - left) * mark.fraction());
            float y = y(mark.bpm(), series.lowerBound(), series.upperBound(), top, bottom);
            double dx = right - left;
            double dy = -mark.slope() * scale;
            double length = Math.hypot(dx, dy);
            float nx = (float) (-dy / length * MARK_HALF_LENGTH);
            float ny = (float) (dx / length * MARK_HALF_LENGTH);
            canvas.drawLine(x - nx, y - ny, x + nx, y + ny, paint);
        }
    }

    private static void drawTimeLabels(Canvas canvas, Paint paint, HistorySeries series, int width) {
        paint.setAlpha(TIME_DETAIL_ALPHA);
        ZoneId zone = ZoneId.systemDefault();
        for (boolean end : new boolean[]{false, true}) {
            HistoryTimeline.Label label = HistoryTimeline.label(series, end, zone);
            float x = end ? width - TIME_LABEL_INSET : TIME_LABEL_INSET;
            paint.setTextAlign(end ? Paint.Align.RIGHT : Paint.Align.LEFT);
            paint.setTextSize(TIME_LABEL_SIZE);
            canvas.drawText(label.time(), x, TIME_LABEL_BASELINE, paint);
            if (!label.day().isEmpty()) {
                float dayX = x + (end ? -DAY_LABEL_INSET : DAY_LABEL_INSET);
                paint.setTextSize(DAY_LABEL_SIZE);
                canvas.drawText(label.day(), dayX, TIME_LABEL_BASELINE - TIME_LABEL_SIZE, paint);
            }
        }
    }

    static void drawPlot(Canvas canvas, Paint paint, HistorySeries series,
            float left, float top, float right, float bottom, boolean background) {
        double lower = series.lowerBound();
        double upper = series.upperBound();
        paint.setStrokeWidth(1);
        paint.setAlpha(40);
        if (!background) {
            for (int guide = 0; guide <= 2; guide++) {
                float y = top + (bottom - top) * guide / 2;
                canvas.drawLine(left, y, right, y, paint);
            }
        }

        int previous = -1;
        float previousX = 0;
        Path line = new Path();
        Path fill = new Path();
        for (int index = 0; index < series.buckets.length; index++) {
            HistorySeries.Bucket bucket = series.buckets[index];
            if (bucket.count == 0) {
                continue;
            }
            float x = left + (right - left) * (index + 0.5f) / series.buckets.length;
            float y = y(bucket.average(), lower, upper, top, bottom);
            paint.setAlpha(background ? 55 : 85);
            paint.setStrokeWidth((right - left) / series.buckets.length);
            canvas.drawLine(x, y(bucket.minimum, lower, upper, top, bottom),
                    x, y(bucket.maximum, lower, upper, top, bottom), paint);
            if (series.connects(previous, index)) {
                line.lineTo(x, y);
                fill.lineTo(x, y);
            } else {
                if (previous >= 0) {
                    fill.lineTo(previousX, bottom);
                    fill.close();
                }
                line.moveTo(x, y);
                fill.moveTo(x, bottom);
                fill.lineTo(x, y);
            }
            paint.setAlpha(background ? 170 : 220);
            canvas.drawCircle(x, y, background ? 0.8f : 2, paint);
            previous = index;
            previousX = x;
        }
        if (background) {
            fill.lineTo(previousX, bottom);
            fill.close();
            paint.setAlpha(255);
            paint.setShader(new LinearGradient(0, top, 0, bottom,
                    0x30FFFFFF, 0x00FFFFFF, Shader.TileMode.CLAMP));
            canvas.drawPath(fill, paint);
            paint.setShader(null);
        }
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeJoin(Paint.Join.ROUND);
        paint.setStrokeCap(Paint.Cap.ROUND);
        paint.setStrokeWidth(background ? 1.5f : 3);
        paint.setAlpha(background ? 180 : 230);
        canvas.drawPath(line, paint);
    }

    private static void fadeEdges(Canvas canvas, Paint paint, int width, int height) {
        paint.setStyle(Paint.Style.FILL);
        paint.setAlpha(255);
        paint.setXfermode(new PorterDuffXfermode(PorterDuff.Mode.DST_IN));
        int[] colors = {0x00FFFFFF, Color.WHITE, Color.WHITE, 0x00FFFFFF};
        paint.setShader(new LinearGradient(0, 0, width, 0, colors,
                new float[]{0, 0.16f, 0.84f, 1}, Shader.TileMode.CLAMP));
        canvas.drawRect(0, 0, width, height, paint);
        paint.setShader(new LinearGradient(0, 0, 0, height, colors,
                new float[]{0, 0.07f, 0.8f, 1}, Shader.TileMode.CLAMP));
        canvas.drawRect(0, 0, width, height, paint);
    }

    private static float y(double bpm, double lower, double upper, float top, float bottom) {
        return (float) (bottom - (bpm - lower) / (upper - lower) * (bottom - top));
    }
}
