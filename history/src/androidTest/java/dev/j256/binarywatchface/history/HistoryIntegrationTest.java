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
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.ZoneId;
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

    @Test public void imagePayloadIsTransparentBoundedExpiresAndOpensHistory() {
        for (HistorySeries.Span span : HistorySeries.Span.values()) {
            HistorySeries series = HistorySeries.demo(span, now);
            Bitmap bitmap = GraphRenderer.render(series, true, "Sample");
            assertEquals(0, bitmap.getPixel(0, 0));
            assertTrue(bitmap.getAllocationByteCount() < 1_000_000);
            Bitmap background = GraphRenderer.renderBackground(series, true, "Sample", HistorySettings.Labels.NONE, HistorySettings.Markers.NONE);
            assertTrue(background.getAllocationByteCount() < 1_000_000);
            for (int y = 0; y < background.getHeight(); y++) {
                assertEquals(0, background.getPixel(0, y));
                assertEquals(0, background.getPixel(background.getWidth() - 1, y));
            }
            var data = HeartHistoryComplication.image(context, series, true, "Sample", HistorySettings.Labels.NONE, HistorySettings.Markers.NONE, HistoryTimeline.Density.REGULAR);
            assertNotNull(data.getTapAction());
            assertTrue(data.getTapAction().isImmutable());
            assertTrue(data.getTapAction().isActivity());
            assertFalse(data.getValidTimeRange().contains(java.time.Instant.ofEpochMilli(now + 11 * HistorySeries.MINUTE_MS)));
        }
    }

    @Test public void backgroundFillDoesNotBridgeMissingReadings() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.HOUR, now);
        series.add(new HistorySeries.Sample(now - 45 * HistorySeries.MINUTE_MS, 70));
        series.add(new HistorySeries.Sample(now - 15 * HistorySeries.MINUTE_MS, 90));
        for (HistorySettings.Markers markers : HistorySettings.Markers.values()) {
            Bitmap background = GraphRenderer.renderBackground(series, false, "", HistorySettings.Labels.WINDOW, markers);
            for (int y = 40; y < background.getHeight(); y++) {
                assertEquals(0, background.getPixel(background.getWidth() / 2, y));
            }
            background.recycle();
        }
    }

    @Test public void backgroundTraceRemainsVisibleAboveItsFaintFill() {
        for (HistorySeries.Span span : HistorySeries.Span.values()) {
            HistorySeries series = new HistorySeries(span, now);
            for (long time = series.startMs; time <= now; time += HistorySeries.MINUTE_MS) {
                series.add(new HistorySeries.Sample(time, 80));
            }
            Bitmap image = GraphRenderer.renderBackground(series, false, "",
                    HistorySettings.Labels.NONE, HistorySettings.Markers.NONE);
            int middle = image.getWidth() / 2;
            int traceAlpha = maxAlpha(image, middle, 80, middle + 1, image.getHeight());
            assertTrue("The trace must survive the face's additional opacity", traceAlpha >= 140);
            assertTrue("The trace must remain secondary to markers and labels", traceAlpha <= 160);
            int visibleRows = 0;
            for (int y = 80; y < image.getHeight(); y++) {
                if ((image.getPixel(middle, y) >>> 24) >= traceAlpha / 3) visibleRows++;
            }
            assertTrue("The trace must span more than a hairline", visibleRows >= 3);
            int fillAlpha = maxAlpha(image, middle, 245, middle + 1, 275);
            assertTrue("The fill must remain present but faint", fillAlpha > 0 && fillAlpha <= 12);
            image.recycle();

            HistorySeries isolated = new HistorySeries(span, now);
            isolated.add(new HistorySeries.Sample(now, 80));
            Bitmap point = GraphRenderer.renderBackground(isolated, false, "",
                    HistorySettings.Labels.NONE, HistorySettings.Markers.NONE);
            assertTrue("An isolated reading must retain the trace's brightness",
                    maxAlpha(point, 0, 80, point.getWidth(), point.getHeight()) >= traceAlpha - 30);
            point.recycle();
        }
    }

    private int maxAlpha(Bitmap image, int left, int top, int right, int bottom) {
        int maximum = 0;
        for (int y = top; y < bottom; y++) for (int x = left; x < right; x++) {
            maximum = Math.max(maximum, image.getPixel(x, y) >>> 24);
        }
        return maximum;
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

    @Test public void markerUpgradePreservesAppearanceAndThenSeparatesMarkersFromLabels() {
        var preferences = context.getSharedPreferences("history-settings", Context.MODE_PRIVATE);
        for (HistorySettings.Labels labels : HistorySettings.Labels.values()) {
            preferences.edit().putString(HistorySettings.LABELS_KEY, labels.name())
                    .remove(HistorySettings.MARKERS_KEY).commit();
            HistorySettings settings = new HistorySettings(context);
            assertEquals(labels == HistorySettings.Labels.NONE ? HistorySettings.Markers.NONE
                    : HistorySettings.Markers.TICKS, settings.markers());
            for (HistorySettings.Markers markers : HistorySettings.Markers.values()) {
                settings.markers(markers);
                settings.labels(HistorySettings.Labels.NONE);
                assertEquals(markers, new HistorySettings(context).markers());
                settings.labels(HistorySettings.Labels.WINDOW);
                assertEquals(markers, new HistorySettings(context).markers());
            }
        }
        new HistorySettings(context).labels(HistorySettings.Labels.NONE);
        new HistorySettings(context).markers(HistorySettings.Markers.NONE);
    }

    @Test public void markerShapesAreDistinctDimAndIndependentOfTimeLabels() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.HOUR, now);
        for (long time = series.startMs; time <= now; time += HistorySeries.MINUTE_MS) {
            series.add(new HistorySeries.Sample(time, 80));
        }
        java.util.ArrayList<Bitmap> images = new java.util.ArrayList<>();
        for (HistorySettings.Markers markers : HistorySettings.Markers.values()) {
            Bitmap image = GraphRenderer.renderBackground(series, false, "", HistorySettings.Labels.NONE, markers);
            for (Bitmap previous : images) assertFalse(previous.sameAs(image));
            images.add(image);
            Bitmap labeled = GraphRenderer.renderBackground(series, false, "", HistorySettings.Labels.WINDOW, markers);
            int labelAlpha = maxAlpha(labeled, 0, 0, labeled.getWidth(), 80);
            for (int y = 0; y < image.getHeight(); y++) for (int x = 0; x < image.getWidth(); x++) {
                assertTrue("Trace and markers must remain dimmer than timestamps", (image.getPixel(x, y) >>> 24) < labelAlpha);
            }
            assertFalse(image.sameAs(labeled));
            for (int y = 90; y < image.getHeight(); y++) for (int x = 0; x < image.getWidth(); x++) {
                assertEquals("Labels must not change the trace or markers", image.getPixel(x, y), labeled.getPixel(x, y));
            }
            labeled.recycle();
        }
        for (Bitmap image : images) image.recycle();
    }

    @Test public void eachTimeWindowRemembersItsOwnDensityAcrossRecreation() {
        HistorySettings settings = new HistorySettings(context);
        for (HistorySeries.Span span : HistorySeries.Span.values()) settings.density(span, HistoryTimeline.Density.REGULAR);
        settings.density(HistorySeries.Span.HALF_HOUR, HistoryTimeline.Density.SPARSE);
        settings.density(HistorySeries.Span.DAY, HistoryTimeline.Density.DENSE);
        for (HistorySeries.Span span : HistorySeries.Span.values()) {
            settings.span(span);
            HistoryTimeline.Density expected = span == HistorySeries.Span.HALF_HOUR ? HistoryTimeline.Density.SPARSE
                    : span == HistorySeries.Span.DAY ? HistoryTimeline.Density.DENSE : HistoryTimeline.Density.REGULAR;
            assertEquals(expected, new HistorySettings(context).density());
        }
        for (HistorySeries.Span span : HistorySeries.Span.values()) settings.density(span, HistoryTimeline.Density.REGULAR);
        settings.span(HistorySeries.Span.HOUR);
    }

    @Test public void everySideTimeAndWeekdayClearsTheBezelTickAndFitsTheOuterHourGutters() {
        ZoneId zone = ZoneId.systemDefault();
        LocalDate monday = LocalDate.of(2026, 1, 5);
        int[] pixels = new int[GraphRenderer.BACKGROUND_WIDTH * GraphRenderer.BACKGROUND_HEIGHT];
        for (int minute = 0; minute < Duration.ofDays(1).toMinutes(); minute++) {
            long time = monday.atStartOfDay().plusMinutes(minute).atZone(zone).toInstant().toEpochMilli();
            assertSideLabelClearance(time, zone, pixels);
        }
        for (DayOfWeek day : DayOfWeek.values()) {
            long time = monday.plusDays(day.getValue() - DayOfWeek.MONDAY.getValue())
                    .atStartOfDay(zone).toInstant().toEpochMilli();
            assertSideLabelClearance(time, zone, pixels);
        }
    }

    private void assertSideLabelClearance(long time, ZoneId zone, int[] pixels) {
        HistorySeries series = new HistorySeries(HistorySeries.Span.DAY, time);
        Bitmap image = GraphRenderer.renderBackground(series, false, "", HistorySettings.Labels.WINDOW, HistorySettings.Markers.NONE);
        int width = image.getWidth();
        image.getPixels(pixels, 0, width, 0, 0, width, image.getHeight());
        image.recycle();
        String labels = HistoryTimeline.label(series, false, zone) + " / " + HistoryTimeline.label(series, true, zone);
        int faceCenter = GraphRenderer.BACKGROUND_WIDTH / 2;
        int graphTop = 60;
        int leftGutterEdge = 95;
        int rightGutterEdge = 357;
        int captionTop = 35;
        int captionBottom = 79;
        int bezelClearRadius = 194;
        int leftPixels = 0;
        int rightPixels = 0;
        for (int index = 0; index < pixels.length; index++) {
            if ((pixels[index] >>> 24) == 0) continue;
            int x = index % width;
            int y = index / width;
            String pixel = labels + " pixel " + x + "," + y;
            assertTrue(pixel + " overlaps the hour row", x <= leftGutterEdge || x >= rightGutterEdge);
            assertTrue(pixel + " leaves the side gutter", y >= captionTop && y <= captionBottom);
            assertTrue(pixel + " reaches the bezel tick",
                    Math.hypot(x - faceCenter, y + graphTop - faceCenter) <= bezelClearRadius);
            if (x < faceCenter) leftPixels++;
            else rightPixels++;
        }
        assertTrue(labels + " has no start label", leftPixels > 0);
        assertTrue(labels + " has no end label", rightPixels > 0);
    }

    @Test public void labelsCanBeHiddenInEitherModeWithoutHidingStaleOrEmptyNotices() {
        HistorySeries series = HistorySeries.demo(HistorySeries.Span.HOUR, now);
        Bitmap hidden = GraphRenderer.renderBackground(series, false, "", HistorySettings.Labels.NONE, HistorySettings.Markers.NONE);
        Bitmap window = GraphRenderer.renderBackground(series, false, "", HistorySettings.Labels.WINDOW, HistorySettings.Markers.NONE);
        Bitmap range = GraphRenderer.renderBackground(series, false, "", HistorySettings.Labels.RANGE, HistorySettings.Markers.NONE);
        assertEquals(0, captionPixels(hidden));
        assertEquals(0, captionPixels(window));
        assertFalse(hidden.sameAs(window));
        assertTrue(captionPixels(range) > captionPixels(window));
        for (HistorySettings.Labels labels : HistorySettings.Labels.values()) {
            assertTrue(GraphRenderer.renderBackground(series, false, "", labels, HistorySettings.Markers.TICKS)
                    .sameAs(GraphRenderer.renderBackground(series, true, "", labels, HistorySettings.Markers.TICKS)));
        }
        assertFalse(GraphRenderer.render(series, false, "").sameAs(GraphRenderer.render(series, true, "")));
        HistorySeries stale = new HistorySeries(HistorySeries.Span.HOUR, now);
        stale.add(new HistorySeries.Sample(now - 20 * HistorySeries.MINUTE_MS, 70));
        assertTrue(captionPixels(GraphRenderer.renderBackground(stale, false, "", HistorySettings.Labels.NONE, HistorySettings.Markers.NONE)) > 0);
        assertTrue(captionPixels(GraphRenderer.renderBackground(new HistorySeries(HistorySeries.Span.HOUR, now),
                false, "Waiting for readings", HistorySettings.Labels.NONE, HistorySettings.Markers.NONE)) > 0);
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
