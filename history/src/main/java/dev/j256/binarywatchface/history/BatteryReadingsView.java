package dev.j256.binarywatchface.history;

import android.content.Context;
import android.annotation.SuppressLint;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.view.View;

import static dev.j256.binarywatchface.history.HistoryColors.*;

/** Plot only observed points, without inventing a continuous discharge curve */
@SuppressLint("ViewConstructor") // Created with immutable trial data, never inflated from XML
final class BatteryReadingsView extends View {
    private final BatteryTrial.Run run;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);

    BatteryReadingsView(Context context, BatteryTrial.Run run) {
        super(context);
        this.run = run;
        setMinimumHeight(HistoryUi.dp(context, 130));
        StringBuilder description = new StringBuilder("Observed battery readings. ");
        for (BatteryTrial.Reading reading : run.readings()) {
            description.append(BatteryText.hours((reading.elapsedMs() - run.first().elapsedMs()) / (double) BatteryTrial.HOUR_MS))
                    .append(": ").append(reading.percent()).append(" percent. ");
        }
        setContentDescription(description);
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_YES);
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float density = getResources().getDisplayMetrics().density;
        float left = 28 * density;
        float right = getWidth() - 8 * density;
        float top = 14 * density;
        float bottom = getHeight() - 24 * density;
        paint.setTextSize(10 * density);
        paint.setColor(MUTED);
        paint.setTextAlign(Paint.Align.LEFT);
        canvas.drawText("100", 0, top + 4 * density, paint);
        canvas.drawText("0%", 0, bottom, paint);
        canvas.drawText("0 h", left, getHeight() - 5 * density, paint);
        paint.setTextAlign(Paint.Align.RIGHT);
        canvas.drawText(BatteryText.hours(Math.max(0, run.hours())), right, getHeight() - 5 * density, paint);
        paint.setColor(SURFACE);
        paint.setStrokeWidth(density);
        canvas.drawLine(left, top, right, top, paint);
        canvas.drawLine(left, bottom, right, bottom, paint);
        paint.setColor(ACCENT);
        for (BatteryTrial.Reading reading : run.readings()) {
            if (!reading.available() || reading.bootCount() != run.first().bootCount()) continue;
            double offset = (reading.elapsedMs() - run.first().elapsedMs()) / (double) Math.max(1, run.durationMs());
            if (offset < 0 || offset > 1) continue;
            canvas.drawCircle(left + (float) offset * (right - left),
                    bottom - reading.percent() / 100f * (bottom - top), 3 * density, paint);
        }
    }
}
