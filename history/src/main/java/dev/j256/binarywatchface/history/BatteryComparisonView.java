package dev.j256.binarywatchface.history;

import android.content.Context;
import android.annotation.SuppressLint;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.view.View;

import java.util.List;

import static dev.j256.binarywatchface.history.HistoryColors.*;

/** Shared zero-based scale; dots preserve the variation between individual runs */
@SuppressLint("ViewConstructor") // Created with immutable trial data, never inflated from XML
final class BatteryComparisonView extends View {
    private final List<BatteryTrial.Run> runs;
    private final String configuration;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final BatteryTrial.Mode[] modes = BatteryTrial.Mode.values();
    private final BatteryTrial.Summary[] summaries = new BatteryTrial.Summary[modes.length];
    private final String[] rates = new String[modes.length];
    private float maxRate = 1;

    BatteryComparisonView(Context context, List<BatteryTrial.Run> runs, String configuration) {
        super(context);
        this.runs = List.copyOf(runs);
        this.configuration = configuration;
        paint.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL));
        StringBuilder description = new StringBuilder("Battery drain comparison. ");
        for (BatteryTrial.Mode mode : modes) {
            BatteryTrial.Summary summary = BatteryTrial.summarize(runs, mode, configuration);
            summaries[mode.ordinal()] = summary;
            rates[mode.ordinal()] = summary.runs() == 0 ? "No runs" : BatteryText.rate(summary.rate());
            if (summary.runs() > 0) maxRate = Math.max(maxRate, (float) summary.high());
            description.append(BatteryText.mode(mode)).append(": ")
                    .append(summary.runs() == 0 ? "no eligible runs" : BatteryText.rate(summary.rate()))
                    .append(". ");
        }
        setContentDescription(description);
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_YES);
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float scale = getResources().getDisplayMetrics().density;
        float width = getWidth() - 8 * scale;
        float rowHeight = getHeight() / (float) modes.length;
        paint.setTextSize(11 * scale);
        for (BatteryTrial.Mode mode : modes) {
            BatteryTrial.Summary summary = summaries[mode.ordinal()];
            float y = rowHeight * mode.ordinal();
            paint.setTextAlign(Paint.Align.LEFT);
            paint.setColor(INK);
            canvas.drawText(BatteryText.mode(mode), 4 * scale, y + 14 * scale, paint);
            paint.setTextAlign(Paint.Align.RIGHT);
            paint.setColor(MUTED);
            canvas.drawText(rates[mode.ordinal()],
                    getWidth() - 4 * scale, y + 14 * scale, paint);
            paint.setColor(SURFACE);
            canvas.drawRoundRect(4 * scale, y + 22 * scale, getWidth() - 4 * scale, y + 29 * scale, 3 * scale, 3 * scale, paint);
            if (summary.runs() == 0) continue;
            paint.setColor(mode == BatteryTrial.Mode.BASELINE ? MUTED : ACCENT);
            canvas.drawRoundRect(4 * scale, y + 22 * scale,
                    4 * scale + width * (float) summary.rate() / maxRate, y + 29 * scale, 3 * scale, 3 * scale, paint);
            paint.setColor(INK);
            for (BatteryTrial.Run run : runs) {
                if (run.mode() == mode && run.configuration().equals(configuration) && run.comparable()) {
                    canvas.drawCircle(4 * scale + width * (float) run.percentPerHour() / maxRate, y + 25.5f * scale, 2 * scale, paint);
                }
            }
        }
    }
}
