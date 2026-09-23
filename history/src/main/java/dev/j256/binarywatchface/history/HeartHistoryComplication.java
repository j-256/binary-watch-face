package dev.j256.binarywatchface.history;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.graphics.drawable.Icon;
import android.os.SystemClock;
import android.os.RemoteException;
import android.util.Log;

import androidx.wear.watchface.complications.data.ComplicationData;
import androidx.wear.watchface.complications.data.ComplicationType;
import androidx.wear.watchface.complications.data.NoDataComplicationData;
import androidx.wear.watchface.complications.data.PhotoImageComplicationData;
import androidx.wear.watchface.complications.data.PlainComplicationText;
import androidx.wear.watchface.complications.data.TimeRange;
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceService;
import androidx.wear.watchface.complications.datasource.ComplicationRequest;

import java.time.Instant;
import java.util.UUID;

public final class HeartHistoryComplication extends ComplicationDataSourceService {
    private static final long IMAGE_LIFETIME_MS = 10 * HistorySeries.MINUTE_MS;

    @Override public void onComplicationRequest(ComplicationRequest request, ComplicationRequestListener listener) {
        if (request.getComplicationType() != ComplicationType.PHOTO_IMAGE) {
            deliver(listener, new NoDataComplicationData());
            return;
        }
        HistoryRuntime.IO.execute(() -> {
            long started = SystemClock.elapsedRealtime();
            String operation = UUID.randomUUID().toString().substring(0, 8);
            try {
                long now = System.currentTimeMillis();
                HistorySettings settings = new HistorySettings(this);
                HistorySeries series;
                if (settings.demo()) series = HistorySeries.demo(settings.span(), now);
                else if (HistorySettings.hasPermissions(this)) {
                    try (HistoryStore store = new HistoryStore(this)) {
                        series = store.read(settings.span(), now);
                    }
                } else series = new HistorySeries(settings.span(), now);
                String emptyLabel = settings.recording() ? "Waiting for readings" : "Open Heart History";
                deliver(listener, image(this, series, settings.demo(), emptyLabel, settings.labels()));
                String result = series.sampleCount == 0 ? "empty" : settings.demo() ? "sample" : series.isStale() ? "stale" : "ready";
                HistoryRuntime.log("image", operation, result, started, series.sampleCount);
            } catch (RuntimeException error) {
                deliver(listener, new NoDataComplicationData());
                HistoryRuntime.log("image", operation, error.getClass().getSimpleName(), started, 0);
            }
        });
    }

    @Override public ComplicationData getPreviewData(ComplicationType type) {
        if (type != ComplicationType.PHOTO_IMAGE) return null;
        return image(HistorySeries.demo(HistorySeries.Span.HOUR, System.currentTimeMillis()), true, "Sample",
                HistorySettings.Labels.NONE, TimeRange.ALWAYS, null);
    }

    private static void deliver(ComplicationRequestListener listener, ComplicationData data) {
        try {
            listener.onComplicationData(data);
        } catch (RemoteException error) {
            Log.w(HistoryRuntime.LOG_TAG, "event=image_delivery result=renderer_disconnected");
        }
    }

    static PhotoImageComplicationData image(Context context, HistorySeries series, boolean demo, String emptyLabel,
            HistorySettings.Labels labels) {
        Intent open = new Intent(context, HistoryActivity.class)
                .setAction(Intent.ACTION_MAIN)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent tap = PendingIntent.getActivity(context, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        return image(series, demo, emptyLabel, labels, TimeRange.between(Instant.ofEpochMilli(series.endMs),
                Instant.ofEpochMilli(series.endMs + IMAGE_LIFETIME_MS)), tap);
    }

    private static PhotoImageComplicationData image(HistorySeries series, boolean demo, String emptyLabel,
            HistorySettings.Labels labels, TimeRange validity, PendingIntent tap) {
        String description = demo ? "Sample heart-rate graph, " : "Heart-rate history, ";
        description += series.span.label + (series.sampleCount == 0 ? ", " + emptyLabel : series.isStale() ? ", readings are stale" : "");
        return new PhotoImageComplicationData.Builder(
                Icon.createWithBitmap(GraphRenderer.renderBackground(series, demo, emptyLabel, labels)),
                new PlainComplicationText.Builder(description).build())
                .setValidTimeRange(validity)
                .setTapAction(tap)
                .build();
    }
}
