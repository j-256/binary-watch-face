package dev.j256.binarywatchface.history;

import android.os.SystemClock;
import android.content.Context;

import androidx.health.services.client.PassiveListenerService;
import androidx.health.services.client.data.DataPointContainer;
import androidx.health.services.client.data.DataType;
import androidx.health.services.client.data.HeartRateAccuracy;
import androidx.health.services.client.data.SampleDataPoint;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public final class HeartRateListener extends PassiveListenerService {
    @Override public void onNewDataPointsReceived(DataPointContainer dataPoints) {
        ingest(this, dataPoints);
    }

    static void ingest(Context context, DataPointContainer dataPoints) {
        HistorySettings settings = new HistorySettings(context);
        if (!settings.recording() || !HistorySettings.hasPermissions(context)) return;
        long now = System.currentTimeMillis();
        long started = SystemClock.elapsedRealtime();
        long bootMs = now - started;
        String operation = UUID.randomUUID().toString().substring(0, 8);
        List<HistorySeries.Sample> samples = new ArrayList<>();
        for (SampleDataPoint<Double> point : dataPoints.getData(DataType.HEART_RATE_BPM)) {
            if (point.getAccuracy() instanceof HeartRateAccuracy accuracy
                    && (accuracy.getSensorStatus().equals(HeartRateAccuracy.SensorStatus.NO_CONTACT)
                    || accuracy.getSensorStatus().equals(HeartRateAccuracy.SensorStatus.UNRELIABLE))) continue;
            samples.add(new HistorySeries.Sample(bootMs + point.getTimeDurationFromBoot().toMillis(), point.getValue()));
        }
        HistoryRuntime.IO.execute(() -> {
            if (!settings.recording() || !HistorySettings.hasPermissions(context)) return;
            try (HistoryStore store = new HistoryStore(context)) {
                int accepted = store.append(samples, System.currentTimeMillis());
                settings.status(HistorySettings.STATUS_RECORDING);
                HistoryRuntime.log("batch", operation, "stored", started, accepted);
            } catch (RuntimeException error) {
                settings.status(HistorySettings.STATUS_STORAGE_ERROR);
                HistoryRuntime.log("batch", operation, error.getClass().getSimpleName(), started, 0);
            }
        });
    }

    @Override public void onPermissionLost() {
        HistoryRuntime.stop(this, false, () -> new HistorySettings(this).status(HistorySettings.STATUS_PERMISSION));
    }
}
