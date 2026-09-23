package dev.j256.binarywatchface.history;

import android.content.Context;
import android.content.ContextWrapper;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.os.SystemClock;

import androidx.health.services.client.data.DataPointContainer;
import androidx.health.services.client.data.DataType;
import androidx.health.services.client.data.HeartRateAccuracy;
import androidx.health.services.client.data.SampleDataPoint;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.List;
import java.time.Duration;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class HistoryIntegrationTest {
    private Context context;
    private long now;

    @Before public void setup() {
        context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        now = System.currentTimeMillis() / 1_000 * 1_000;
        new HistorySettings(context).mode(false, false);
        try (HistoryStore store = new HistoryStore(context)) { store.clear(); }
    }

    @After public void cleanup() {
        new HistorySettings(context).mode(false, false);
        try (HistoryStore store = new HistoryStore(context)) { store.clear(); }
    }

    @Test public void readingsSurviveReopenAndDeduplicateWithoutReplacingNewerData() {
        try (HistoryStore store = new HistoryStore(context)) {
            store.append(List.of(new HistorySeries.Sample(now - 100, 85)), now);
            store.append(List.of(new HistorySeries.Sample(now - 800, 70)), now);
            store.append(List.of(new HistorySeries.Sample(now - 100, 85)), now);
        }
        try (HistoryStore store = new HistoryStore(context)) {
            HistorySeries series = store.read(HistorySeries.Span.HOUR, now);
            assertEquals(1, series.sampleCount);
            assertEquals(85, series.latestBpm, 0);
        }
    }

    @Test public void expiryAndClockRollbackRemoveIneligibleData() {
        try (HistoryStore store = new HistoryStore(context)) {
            store.append(List.of(new HistorySeries.Sample(now - HistorySeries.RETENTION_MS, 70),
                    new HistorySeries.Sample(now - 1_000, 80)), now);
            assertEquals(1, store.read(HistorySeries.Span.DAY, now + 2_000).sampleCount);
            assertEquals(0, store.read(HistorySeries.Span.DAY, now - 10_000).sampleCount);
        }
    }

    @Test public void retentionUsesReadingTimeRatherThanTheDeduplicationSecond() {
        long fractionalNow = now + 500;
        try (HistoryStore store = new HistoryStore(context)) {
            store.append(List.of(new HistorySeries.Sample(fractionalNow - HistorySeries.RETENTION_MS, 70)), fractionalNow);
            assertEquals(1, store.read(HistorySeries.Span.DAY, fractionalNow).sampleCount);
            assertEquals(0, store.read(HistorySeries.Span.DAY, fractionalNow + 1).sampleCount);
        }
    }

    @Test public void passiveBatchesFilterUnreliableReadingsAndIgnoreCallbacksAfterStop() throws Exception {
        Context granted = permissions(PackageManager.PERMISSION_GRANTED);
        new HistorySettings(context).mode(true, false);
        long elapsed = SystemClock.elapsedRealtime();
        DataPointContainer batch = new DataPointContainer(List.of(
                point(82, elapsed - 1_000, HeartRateAccuracy.SensorStatus.ACCURACY_HIGH),
                point(150, elapsed - 2_000, HeartRateAccuracy.SensorStatus.NO_CONTACT),
                point(180, elapsed - 3_000, HeartRateAccuracy.SensorStatus.UNRELIABLE),
                point(Double.NaN, elapsed - 4_000, HeartRateAccuracy.SensorStatus.ACCURACY_HIGH),
                point(90, elapsed + 60_000, HeartRateAccuracy.SensorStatus.ACCURACY_HIGH)));
        HeartRateListener.ingest(granted, batch);
        HistoryRuntime.IO.submit(() -> {}).get(5, TimeUnit.SECONDS);
        try (HistoryStore store = new HistoryStore(context)) {
            HistorySeries series = store.read(HistorySeries.Span.HOUR, System.currentTimeMillis());
            assertEquals(1, series.sampleCount);
            assertEquals(82, series.latestBpm, 0);
            assertTrue(Math.abs(System.currentTimeMillis() - series.latestMs - 1_000) < 5_000);
        }
        CountDownLatch stopped = new CountDownLatch(1);
        HistoryRuntime.stop(context, false, stopped::countDown);
        assertTrue(stopped.await(5, TimeUnit.SECONDS));
        HeartRateListener.ingest(granted, batch);
        HistoryRuntime.IO.submit(() -> {}).get(5, TimeUnit.SECONDS);
        try (HistoryStore store = new HistoryStore(context)) {
            assertEquals(0, store.read(HistorySeries.Span.DAY, System.currentTimeMillis()).sampleCount);
        }
        assertFalse(new HistorySettings(context).recording());
    }

    @Test public void missingPermissionStopsRecordingAndErasesPreviouslyStoredReadings() throws Exception {
        new HistorySettings(context).mode(true, false);
        try (HistoryStore store = new HistoryStore(context)) {
            store.append(List.of(new HistorySeries.Sample(now, 80)), now);
        }
        assertTrue(HistoryRuntime.register(permissions(PackageManager.PERMISSION_DENIED)));
        HistoryRuntime.IO.submit(() -> {}).get(5, TimeUnit.SECONDS);
        assertFalse(new HistorySettings(context).recording());
        assertEquals("permission", new HistorySettings(context).status());
        try (HistoryStore store = new HistoryStore(context)) {
            assertEquals(0, store.read(HistorySeries.Span.DAY, now).sampleCount);
        }
    }

    @Test public void previewPausesRecordingWithoutOverwritingRealHistory() throws Exception {
        new HistorySettings(context).mode(true, false);
        try (HistoryStore store = new HistoryStore(context)) {
            store.append(List.of(new HistorySeries.Sample(now, 80)), now);
        }
        CountDownLatch paused = new CountDownLatch(1);
        HistoryRuntime.stop(context, true, paused::countDown);
        assertTrue(paused.await(5, TimeUnit.SECONDS));
        assertTrue(new HistorySettings(context).demo());
        assertFalse(new HistorySettings(context).recording());
        try (HistoryStore store = new HistoryStore(context)) {
            assertEquals(80, store.read(HistorySeries.Span.DAY, now).latestBpm, 0);
        }
    }

    private Context permissions(int result) {
        return new ContextWrapper(context) {
            @Override public int checkSelfPermission(String permission) { return result; }
        };
    }

    private SampleDataPoint<Double> point(double value, long elapsed, HeartRateAccuracy.SensorStatus status) {
        return new SampleDataPoint<>(DataType.HEART_RATE_BPM, value, Duration.ofMillis(elapsed),
                Bundle.EMPTY, new HeartRateAccuracy(status));
    }

    @Test public void sampleModeNeverPopulatesTheDatabaseAndSettingsPersist() {
        HistorySettings settings = new HistorySettings(context);
        settings.span(HistorySeries.Span.SIX_HOURS);
        assertEquals(HistorySeries.Span.SIX_HOURS, new HistorySettings(context).span());
        HistorySeries sample = HistorySeries.demo(settings.span(), now);
        assertTrue(sample.sampleCount > 0);
        try (HistoryStore store = new HistoryStore(context)) {
            assertEquals(0, store.read(HistorySeries.Span.DAY, now).sampleCount);
        }
        settings.span(HistorySeries.Span.HOUR);
    }

    @Test public void imagePayloadIsTransparentBoundedExpiresAndHasNoTapAction() {
        for (HistorySeries.Span span : HistorySeries.Span.values()) {
            HistorySeries series = HistorySeries.demo(span, now);
            Bitmap bitmap = GraphRenderer.render(series, true, "Sample");
            assertEquals(0, bitmap.getPixel(0, 0));
            assertTrue(bitmap.getAllocationByteCount() < 1_000_000);
            Bitmap background = GraphRenderer.renderBackground(series, true, "Sample", HistorySettings.Labels.NONE);
            assertTrue(background.getAllocationByteCount() < 1_000_000);
            for (int y = 0; y < background.getHeight(); y++) {
                assertEquals(0, background.getPixel(0, y));
                assertEquals(0, background.getPixel(background.getWidth() - 1, y));
            }
            var data = HeartHistoryComplication.image(series, true, "Sample", HistorySettings.Labels.NONE);
            assertNull(data.getTapAction());
            assertFalse(data.getValidTimeRange().contains(java.time.Instant.ofEpochMilli(now + 11 * HistorySeries.MINUTE_MS)));
        }
    }

    @Test public void backgroundFillDoesNotBridgeMissingReadings() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.HOUR, now);
        series.add(new HistorySeries.Sample(now - 45 * HistorySeries.MINUTE_MS, 70));
        series.add(new HistorySeries.Sample(now - 15 * HistorySeries.MINUTE_MS, 90));
        Bitmap background = GraphRenderer.renderBackground(series, false, "", HistorySettings.Labels.NONE);
        for (int y = 40; y < background.getHeight(); y++) {
            assertEquals(0, background.getPixel(background.getWidth() / 2, y));
        }
    }

    @Test public void labelsDefaultToNoneAndPersistAcrossSettingsInstances() {
        context.getSharedPreferences("history-settings", Context.MODE_PRIVATE).edit()
                .remove(HistorySettings.LABELS_KEY).commit();
        HistorySettings settings = new HistorySettings(context);
        assertEquals(HistorySettings.Labels.NONE, settings.labels());
        for (HistorySettings.Labels choice : HistorySettings.Labels.values()) {
            settings.labels(choice);
            assertEquals(choice, new HistorySettings(context).labels());
        }
        settings.labels(HistorySettings.Labels.NONE);
    }

    @Test public void labelsCanBeHiddenWithoutHidingSampleStaleOrEmptyNotices() {
        HistorySeries series = HistorySeries.demo(HistorySeries.Span.HOUR, now);
        Bitmap hidden = GraphRenderer.renderBackground(series, false, "", HistorySettings.Labels.NONE);
        Bitmap window = GraphRenderer.renderBackground(series, false, "", HistorySettings.Labels.WINDOW);
        Bitmap range = GraphRenderer.renderBackground(series, false, "", HistorySettings.Labels.RANGE);
        assertEquals(0, captionPixels(hidden));
        assertTrue(captionPixels(window) > 0);
        assertTrue(captionPixels(range) > captionPixels(window));
        assertTrue(captionPixels(GraphRenderer.renderBackground(series, true, "", HistorySettings.Labels.NONE)) > 0);
        HistorySeries stale = new HistorySeries(HistorySeries.Span.HOUR, now);
        stale.add(new HistorySeries.Sample(now - 20 * HistorySeries.MINUTE_MS, 70));
        assertTrue(captionPixels(GraphRenderer.renderBackground(stale, false, "", HistorySettings.Labels.NONE)) > 0);
        assertTrue(captionPixels(GraphRenderer.renderBackground(new HistorySeries(HistorySeries.Span.HOUR, now),
                false, "Waiting for readings", HistorySettings.Labels.NONE)) > 0);
    }

    private int captionPixels(Bitmap bitmap) {
        int visible = 0;
        for (int y = 0; y < 20; y++) {
            for (int x = 0; x < bitmap.getWidth(); x++) {
                if ((bitmap.getPixel(x, y) >>> 24) != 0) visible++;
            }
        }
        return visible;
    }
}
