package dev.j256.binarywatchface.history;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Typeface;

import java.util.Locale;

/** Transparent monochrome image which WFF tints to the selected text color */
public final class GraphRenderer {
    public static final int WIDTH = 476;
    public static final int HEIGHT = 364;
    private static final float LEFT = 16;
    private static final float RIGHT = WIDTH - 16;
    private static final float TOP = 79;
    private static final float BOTTOM = HEIGHT - 40;

    private GraphRenderer() {}

    public static Bitmap render(HistorySeries series, boolean demo, String emptyLabel) {
        Bitmap bitmap = Bitmap.createBitmap(WIDTH, HEIGHT, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(bitmap);
        Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        paint.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        paint.setTextSize(21);
        paint.setColor(Color.WHITE);
        paint.setAlpha(210);
        String header = (demo ? "SAMPLE  /  " : "HEART  /  ") + series.span.label.toUpperCase(Locale.ROOT);
        canvas.drawText(header, LEFT, 27, paint);
        paint.setTextAlign(Paint.Align.RIGHT);
        long ageMinutes = (series.endMs - series.latestMs) / HistorySeries.MINUTE_MS;
        String range = String.format(Locale.ROOT, "%.0f-%.0f", series.minimum, series.maximum);
        String status = series.sampleCount == 0 ? emptyLabel : series.isStale() ? "STALE " + ageMinutes + "m"
                : range + (!demo && ageMinutes > 0 ? " / " + ageMinutes + "m" : " BPM");
        canvas.drawText(status, RIGHT, 27, paint);
        paint.setTextAlign(Paint.Align.LEFT);

        if (series.sampleCount == 0) return bitmap;

        double lower = series.lowerBound();
        double upper = series.upperBound();
        paint.setStrokeWidth(1);
        paint.setAlpha(40);
        for (int guide = 0; guide <= 2; guide++) {
            float y = TOP + (BOTTOM - TOP) * guide / 2;
            canvas.drawLine(LEFT, y, RIGHT, y, paint);
        }

        int previous = -1;
        Path line = new Path();
        for (int index = 0; index < series.buckets.length; index++) {
            HistorySeries.Bucket bucket = series.buckets[index];
            if (bucket.count == 0) {
                continue;
            }
            float x = LEFT + (RIGHT - LEFT) * (index + 0.5f) / series.buckets.length;
            float y = y(bucket.average(), lower, upper);
            paint.setAlpha(85);
            paint.setStrokeWidth((RIGHT - LEFT) / series.buckets.length);
            canvas.drawLine(x, y(bucket.minimum, lower, upper), x, y(bucket.maximum, lower, upper), paint);
            if (series.connects(previous, index)) line.lineTo(x, y);
            else line.moveTo(x, y);
            paint.setAlpha(220);
            canvas.drawCircle(x, y, 2, paint);
            previous = index;
        }
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeJoin(Paint.Join.ROUND);
        paint.setStrokeCap(Paint.Cap.ROUND);
        paint.setStrokeWidth(3);
        paint.setAlpha(230);
        canvas.drawPath(line, paint);
        return bitmap;
    }

    private static float y(double bpm, double lower, double upper) {
        return (float) (BOTTOM - (bpm - lower) / (upper - lower) * (BOTTOM - TOP));
    }
}
