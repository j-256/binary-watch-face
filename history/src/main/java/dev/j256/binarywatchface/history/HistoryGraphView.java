package dev.j256.binarywatchface.history;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffColorFilter;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.view.MotionEvent;
import android.view.View;

import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Locale;

import static dev.j256.binarywatchface.history.HistoryColors.ACCENT;
import static dev.j256.binarywatchface.history.HistoryColors.INK;
import static dev.j256.binarywatchface.history.HistoryColors.MUTED;

/** A cached chart with a cursor that lasts only for the active touch */
public final class HistoryGraphView extends View {
    private static final int NO_POINTER = -1;
    private static final Typeface LABEL_FONT = Typeface.create("sans-serif-medium", Typeface.NORMAL);
    private static final float PLOT_INSET_DP = 18;
    private static final float PLOT_TOP_DP = 49;
    private static final float PLOT_BOTTOM_DP = 36;
    private static final float COMPACT_HEIGHT_DP = 125;
    private static final float COMPACT_FONT_SCALE = 1.15f;
    private static final float COMPACT_PLOT_TOP_DP = 40;
    private static final float COMPACT_PLOT_BOTTOM_DP = 18;
    private final HistorySeries series;
    private final HistoryInspection inspection;
    private final boolean demo;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint chartPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF plot = new RectF();
    private final DateTimeFormatter timestamp = DateTimeFormatter.ofPattern("EEE HH:mm:ss", Locale.getDefault());
    private Bitmap chart;
    private boolean compact;
    private int pointer = NO_POINTER;
    private HistoryInspection.Selection selection;

    public HistoryGraphView(Context context, HistorySeries series, boolean demo) {
        super(context);
        this.series = series;
        this.demo = demo;
        inspection = new HistoryInspection(series);
        chartPaint.setColorFilter(new PorterDuffColorFilter(ACCENT, PorterDuff.Mode.SRC_IN));
        setClickable(true);
        setFocusable(true);
        setContentDescription(context.getString(R.string.graph_description, series.span.label));
    }

    @Override protected void onSizeChanged(int width, int height, int oldWidth, int oldHeight) {
        super.onSizeChanged(width, height, oldWidth, oldHeight);
        clearInspection();
        compact = height < dp(COMPACT_HEIGHT_DP) || getResources().getConfiguration().fontScale > COMPACT_FONT_SCALE;
        plot.set(dp(PLOT_INSET_DP), dp(compact ? COMPACT_PLOT_TOP_DP : PLOT_TOP_DP),
                width - dp(PLOT_INSET_DP), height - dp(compact ? COMPACT_PLOT_BOTTOM_DP : PLOT_BOTTOM_DP));
        chart = null;
        if (width <= 0 || height <= 0 || plot.height() <= 0) return;
        chart = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
        Paint trace = new Paint(Paint.ANTI_ALIAS_FLAG);
        trace.setColor(Color.WHITE);
        if (series.sampleCount > 0) {
            GraphRenderer.drawPlot(new Canvas(chart), trace, series, plot.left, plot.top, plot.right, plot.bottom, false);
        }
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        paint.reset();
        paint.setAntiAlias(true);
        paint.setTypeface(LABEL_FONT);
        if (chart != null) {
            canvas.drawBitmap(chart, 0, 0, chartPaint);
        }
        int compactTitle = demo ? R.string.preview_title : series.isStale() ? R.string.stale_title : R.string.title_compact;
        String title = getContext().getString(compact ? compactTitle : R.string.title);
        String detail = series.span.label;
        if (series.sampleCount > 0) {
            detail += String.format(Locale.getDefault(), "  /  %.0f-%.0f BPM", series.minimum, series.maximum);
        }
        if (selection != null) {
            title = selection.reading() == null ? getContext().getString(R.string.no_reading)
                    : String.format(Locale.getDefault(), "%.0f BPM", selection.reading().bpm());
            detail = timestamp.format(Instant.ofEpochMilli(selection.timeMs()).atZone(ZoneId.systemDefault()));
            float x = plot.left + plot.width() * (selection.timeMs() - series.startMs) / series.span.durationMs;
            paint.setColor(INK);
            paint.setStrokeWidth(dp(1));
            canvas.drawLine(x, plot.top, x, plot.bottom, paint);
            if (selection.reading() != null) {
                float y = (float) (plot.bottom - plot.height() * (selection.reading().bpm() - series.lowerBound())
                        / (series.upperBound() - series.lowerBound()));
                paint.setColor(Color.BLACK);
                canvas.drawCircle(x, y, dp(4), paint);
                paint.setColor(INK);
                canvas.drawCircle(x, y, dp(2.5f), paint);
            }
        }
        label(canvas, title, getWidth() / 2f, dp(compact ? 18 : 21), compact ? 14 : 18, INK, Paint.Align.CENTER);
        label(canvas, detail, getWidth() / 2f, dp(compact ? 34 : 39), compact ? 10 : 12, MUTED, Paint.Align.CENTER);
        if (series.sampleCount == 0) {
            label(canvas, getContext().getString(R.string.no_readings), getWidth() / 2f,
                    plot.centerY(), 14, MUTED, Paint.Align.CENTER);
        }
        boolean compactInspectionStatus = compact && selection != null && (demo || series.isStale());
        if (compactInspectionStatus) {
            label(canvas, getContext().getString(compactTitle), plot.centerX(), plot.bottom + dp(13), 10, MUTED, Paint.Align.CENTER);
        } else {
            for (boolean end : new boolean[]{false, true}) {
                HistoryTimeline.Label time = HistoryTimeline.label(series, end, ZoneId.systemDefault());
                String caption = time.day().isEmpty() ? time.time() : time.day() + " " + time.time();
                label(canvas, caption, end ? plot.right : plot.left, plot.bottom + dp(compact ? 13 : 15), 10, MUTED,
                        end ? Paint.Align.RIGHT : Paint.Align.LEFT);
            }
        }
        int hint = demo ? R.string.inspect_preview : series.sampleCount == 0 ? R.string.inspect_empty
                : series.isStale() ? R.string.inspect_stale : R.string.inspect_hint;
        if (!compact) label(canvas, getContext().getString(hint), getWidth() / 2f, getHeight() - dp(3), 10, MUTED, Paint.Align.CENTER);
    }

    @Override public boolean onTouchEvent(MotionEvent event) {
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN -> {
                if (!plot.contains(event.getX(), event.getY())) return false;
                pointer = event.getPointerId(0);
                if (getParent() != null) getParent().requestDisallowInterceptTouchEvent(true);
                inspect(event.getX());
                return true;
            }
            case MotionEvent.ACTION_MOVE -> {
                int index = event.findPointerIndex(pointer);
                if (index >= 0) inspect(event.getX(index));
                return true;
            }
            case MotionEvent.ACTION_POINTER_UP -> {
                if (event.getPointerId(event.getActionIndex()) == pointer) clearInspection();
                return true;
            }
            case MotionEvent.ACTION_UP -> {
                clearInspection();
                performClick();
                return true;
            }
            case MotionEvent.ACTION_CANCEL -> {
                clearInspection();
                return true;
            }
            default -> { return pointer != NO_POINTER; }
        }
    }

    @Override public boolean performClick() {
        super.performClick();
        return true;
    }

    @Override public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        if (!focused) clearInspection();
    }

    @Override protected void onDetachedFromWindow() {
        clearInspection();
        super.onDetachedFromWindow();
    }

    @Override protected void onVisibilityChanged(View changed, int visibility) {
        super.onVisibilityChanged(changed, visibility);
        if (visibility != VISIBLE) clearInspection();
    }

    private void inspect(float x) {
        selection = inspection.select((x - plot.left) / plot.width());
        invalidate();
    }

    private void clearInspection() {
        pointer = NO_POINTER;
        selection = null;
        if (getParent() != null) getParent().requestDisallowInterceptTouchEvent(false);
        invalidate();
    }

    private void label(Canvas canvas, String value, float x, float y, float size, int color, Paint.Align align) {
        paint.setColor(color);
        paint.setTextAlign(align);
        paint.setTextSize(size * getResources().getDisplayMetrics().scaledDensity);
        canvas.drawText(value, x, y, paint);
    }

    private float dp(float value) {
        return value * getResources().getDisplayMetrics().density;
    }
}
