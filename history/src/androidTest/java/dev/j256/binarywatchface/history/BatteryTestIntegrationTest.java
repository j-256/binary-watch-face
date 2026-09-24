package dev.j256.binarywatchface.history;

import android.app.job.JobScheduler;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.Uri;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import android.os.SystemClock;
import android.os.BatteryManager;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.core.content.FileProvider;

import org.json.JSONObject;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.List;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

import static dev.j256.binarywatchface.history.BatteryTrial.*;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class BatteryTestIntegrationTest {
    private Context context;
    private BatteryTestStore store;
    private long now;

    @Before public void setup() throws Exception {
        context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        HistoryRuntime.HEALTH.submit(() -> {}).get(40, TimeUnit.SECONDS);
        HistoryRuntime.IO.submit(() -> {}).get(5, TimeUnit.SECONDS);
        context.getSharedPreferences(BatteryTestStore.PREFERENCES, Context.MODE_PRIVATE).edit().clear().commit();
        new HistorySettings(context).mode(false, false);
        new HistorySettings(context).status(HistorySettings.STATUS_PAUSED);
        store = new BatteryTestStore(context);
        now = System.currentTimeMillis();
    }

    @After public void cleanup() throws Exception {
        HistoryRuntime.HEALTH.submit(() -> {}).get(40, TimeUnit.SECONDS);
        HistoryRuntime.IO.submit(() -> {}).get(5, TimeUnit.SECONDS);
        context.getSharedPreferences(BatteryTestStore.PREFERENCES, Context.MODE_PRIVATE).edit().clear().commit();
        CountDownLatch paused = new CountDownLatch(1);
        HistoryRuntime.pause(context, paused::countDown);
        assertTrue(paused.await(40, TimeUnit.SECONDS));
        try (HistoryStore history = new HistoryStore(context)) { history.clear(); }
    }

    @Test public void androidBatteryReaderReportsRealCapabilitiesWithoutAssumingChargeSupport() {
        Reading reading = BatteryReader.read(context);
        assertTrue(reading.available());
        assertTrue(reading.versionCode() > 0);
        assertTrue(reading.chargeUah() == UNKNOWN || reading.chargeUah() >= 0);
        Intent battery = context.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        assertEquals(BatteryReader.percent(battery), reading.percent());
    }

    @Test public void systemBatteryLevelIsNormalizedAndMissingOrInvalidGaugesStayUnavailable() {
        assertEquals(UNKNOWN, BatteryReader.percent(null));
        Intent battery = new Intent(Intent.ACTION_BATTERY_CHANGED);
        assertEquals(UNKNOWN, BatteryReader.percent(battery));
        battery.putExtra(BatteryManager.EXTRA_SCALE, 200).putExtra(BatteryManager.EXTRA_LEVEL, 180);
        assertEquals(90, BatteryReader.percent(battery));
        battery.putExtra(BatteryManager.EXTRA_LEVEL, 0);
        assertEquals(0, BatteryReader.percent(battery));
        battery.putExtra(BatteryManager.EXTRA_LEVEL, 201);
        assertEquals(UNKNOWN, BatteryReader.percent(battery));
        battery.putExtra(BatteryManager.EXTRA_LEVEL, -1);
        assertEquals(UNKNOWN, BatteryReader.percent(battery));
        battery.putExtra(BatteryManager.EXTRA_LEVEL, 1).putExtra(BatteryManager.EXTRA_SCALE, 0);
        assertEquals(UNKNOWN, BatteryReader.percent(battery));
        battery.putExtra(BatteryManager.EXTRA_LEVEL, Integer.MAX_VALUE).putExtra(BatteryManager.EXTRA_SCALE, Integer.MAX_VALUE);
        assertEquals(100, BatteryReader.percent(battery));
    }

    @Test public void pauseRetainsHistoryAndCancelsRecorderJobsBeforeCompleting() throws Exception {
        try (HistoryStore history = new HistoryStore(context)) {
            history.append(List.of(new HistorySeries.Sample(now, 78)), now);
        }
        CountDownLatch paused = new CountDownLatch(1);
        HistoryRuntime.pause(context, paused::countDown);
        assertTrue(paused.await(40, TimeUnit.SECONDS));
        assertTrue(BatteryTestCoordinator.matches(context, false, false));
        assertTrue(context.getSystemService(JobScheduler.class).getAllPendingJobs().isEmpty());
        try (HistoryStore history = new HistoryStore(context)) {
            assertEquals(78, history.read(HistorySeries.Span.HOUR, now).latestBpm, 0);
        }
    }

    @Test public void activeRunSurvivesRecreationAndSettingChangesStayExcluded() {
        Run run = run("persist", now).observe(reading(0, 90), false, true);
        store.active(run);
        assertEquals(run, new BatteryTestStore(context).active());
        HistorySettings settings = new HistorySettings(context);
        HistorySeries.Span original = settings.span();
        settings.span(original == HistorySeries.Span.HOUR ? HistorySeries.Span.DAY : HistorySeries.Span.HOUR);
        settings.span(original);
        assertEquals(Issue.SETTINGS_CHANGED, store.active().issue());
        store.active(run.observe(reading(12, 75), false, true));
        assertEquals(Issue.SETTINGS_CHANGED, store.active().issue());
        store.finish(run.observe(reading(24, 60), true, true));
        assertEquals(Issue.SETTINGS_CHANGED, store.results(now).get(0).issue());
    }

    @Test public void rebootAndPackageReplacementInvalidateMeasurements() {
        store.active(run("restart", now).observe(reading(0, 90), false, true));
        new HistoryBootReceiver().onReceive(context, new Intent(Intent.ACTION_BOOT_COMPLETED));
        assertEquals(Issue.RESTARTED, store.active().issue());
        store.active(null);
        store.active(run("update", now).observe(reading(0, 90), false, true));
        new HistoryBootReceiver().onReceive(context, new Intent(Intent.ACTION_MY_PACKAGE_REPLACED));
        assertEquals(Issue.UPDATED, store.active().issue());
    }

    @Test public void markerChangesSeparateComparisonsAndPermanentlyExcludeAnActiveRun() {
        HistorySettings settings = new HistorySettings(context);
        settings.markers(HistorySettings.Markers.NONE);
        String original = BatteryReader.configuration(context);
        store.active(run("markers", now).observe(reading(0, 90), false, true));
        settings.markers(HistorySettings.Markers.TRIANGLES);
        assertNotEquals(original, BatteryReader.configuration(context));
        settings.markers(HistorySettings.Markers.NONE);
        assertEquals(original, BatteryReader.configuration(context));
        assertEquals(Issue.SETTINGS_CHANGED, store.active().issue());
    }

    @Test public void resultsAreBoundedExpiredAndExportedWithRawBatteryObservations() throws Exception {
        for (int index = 0; index < BatteryTestStore.MAX_RUNS + 3; index++) {
            Run run = run("run-" + index, now).observe(reading(0, 90), false, true).observe(reading(12, 75), true, true);
            store.finish(run);
            store.active(null);
        }
        assertEquals(BatteryTestStore.MAX_RUNS, store.results(now).size());
        JSONObject report = new JSONObject(store.report(now));
        assertEquals(1, report.getInt("schemaVersion"));
        assertEquals(90, report.getJSONArray("runs").getJSONObject(0).getJSONArray("readings").getJSONObject(0).getInt("percent"));
        assertFalse(report.toString().contains("bpm"));
        assertFalse(report.toString().contains("sample_time"));
        assertTrue(store.results(now + BatteryTestStore.RETENTION_MS + 1).isEmpty());
        store.active(run("active", now));
        store.clearResults();
        assertNotNull(store.active());
    }

    @Test public void setupCancellationRestoresPreviewAndLeavesNoMeasurementJobs() throws Exception {
        new HistorySettings(context).mode(false, true);
        assertNull(await(done -> BatteryTestCoordinator.prepare(context, Mode.BASELINE, done)));
        assertTrue(store.active().ready());
        assertFalse(new HistorySettings(context).demo());
        assertTrue(context.getSystemService(JobScheduler.class).getAllPendingJobs().isEmpty());
        assertNull(await(done -> BatteryTestCoordinator.cancel(context, done)));
        assertTrue(new HistorySettings(context).demo());
        assertNull(store.active());
        assertTrue(store.results(now).isEmpty());
    }

    @Test public void finishedRunCanRestoreAfterCoordinatorAndActivityRecreationWithoutDuplicatingResults() throws Exception {
        Run run = run("restore", now).observe(reading(0, 90), false, true).observe(reading(12, 75), true, true);
        store.finish(run);
        try (ActivityScenario<BatteryTestActivity> scenario = ActivityScenario.launch(BatteryTestActivity.class)) {
            scenario.recreate();
            assertEquals(run, new BatteryTestStore(context).active());
        }
        assertNull(await(done -> BatteryTestCoordinator.finish(context, true, done)));
        assertNull(store.active());
        assertEquals(1, store.results(now).size());
        assertTrue(BatteryTestCoordinator.matches(context, false, false));
    }

    @Test public void pluggedInStartIsRejectedWithoutDestroyingPreparedSession() throws Exception {
        assertNull(await(done -> BatteryTestCoordinator.prepare(context, Mode.BASELINE, done)));
        Reading reading = BatteryReader.read(context);
        String result = await(done -> BatteryTestCoordinator.start(context, done));
        if (reading.plugged()) {
            assertEquals("Unplug the watch before starting", result);
            assertFalse(store.active().started());
        } else {
            assertNull(result);
            assertTrue(store.active().started());
        }
    }

    @Test public void plotsDrawSparseObservationsAndExposeAccessibleValues() {
        Run run = run("plot", now).observe(reading(0, 90), false, true).observe(reading(12, 75), true, true);
        try (ActivityScenario<BatteryTestActivity> scenario = ActivityScenario.launch(BatteryTestActivity.class)) {
            scenario.onActivity(activity -> {
                View plot = new BatteryReadingsView(activity, run);
                assertTrue(plot.getContentDescription().toString().contains("90 percent"));
                assertTrue(plot.getContentDescription().toString().contains("75 percent"));
                draw(plot, 340, 230);
                View comparison = new BatteryComparisonView(activity, List.of(run), run.configuration());
                assertTrue(comparison.getContentDescription().toString().contains("1.25 pp/h"));
                draw(comparison, 340, 360);
            });
        }
    }

    @Test public void sharingExportsOnlyBatteryJsonWithReadPermissionAndClearingRemovesTheCopy() throws Exception {
        store.finish(run("export", now).observe(reading(0, 90), false, true).observe(reading(12, 75), true, true));
        Intent share = BatteryReport.intent(context);
        assertEquals("application/json", share.getType());
        assertEquals(Intent.FLAG_GRANT_READ_URI_PERMISSION, share.getFlags());
        Uri uri = share.getParcelableExtra(Intent.EXTRA_STREAM, Uri.class);
        assertNotNull(uri);
        assertEquals("content", uri.getScheme());
        assertThrows(IllegalArgumentException.class, () -> FileProvider.getUriForFile(context,
                context.getPackageName() + ".battery-reports", context.getDatabasePath("heart-history.db")));
        try (var input = context.getContentResolver().openInputStream(uri)) {
            JSONObject report = new JSONObject(new String(input.readAllBytes(), StandardCharsets.UTF_8));
            assertEquals(1, report.getJSONArray("runs").length());
            assertFalse(report.toString().contains("bpm"));
        }
        Uri replacement = BatteryReport.intent(context).getParcelableExtra(Intent.EXTRA_STREAM, Uri.class);
        assertNotEquals(uri, replacement);
        assertThrows(java.io.FileNotFoundException.class, () -> context.getContentResolver().openInputStream(uri));
        store.clearResults();
        assertThrows(java.io.FileNotFoundException.class, () -> context.getContentResolver().openInputStream(replacement));
    }

    @Test public void recreatedScreenReceivesCompletionOfAnInFlightSetup() throws Exception {
        CountDownLatch releaseHealth = new CountDownLatch(1);
        CountDownLatch complete = new CountDownLatch(1);
        HistoryRuntime.HEALTH.execute(() -> {
            try { releaseHealth.await(10, TimeUnit.SECONDS); }
            catch (InterruptedException error) { Thread.currentThread().interrupt(); }
        });
        try (ActivityScenario<BatteryTestActivity> scenario = ActivityScenario.launch(BatteryTestActivity.class)) {
            BatteryTestCoordinator.prepare(context, Mode.BASELINE, error -> complete.countDown());
            HistoryRuntime.IO.submit(() -> {}).get(5, TimeUnit.SECONDS);
            scenario.recreate();
            releaseHealth.countDown();
            assertTrue(complete.await(40, TimeUnit.SECONDS));
            AtomicBoolean ready = new AtomicBoolean();
            long deadline = SystemClock.elapsedRealtime() + 5_000;
            while (!ready.get() && SystemClock.elapsedRealtime() < deadline) {
                scenario.onActivity(activity -> ready.set(hasText(activity.getWindow().getDecorView(), "Recording mode is ready.")));
                if (!ready.get()) Thread.sleep(50);
            }
            assertTrue("Recreated screen never received setup completion", ready.get());
        } finally { releaseHealth.countDown(); }
    }

    @Test public void unreadableBatteryLedgerCannotBreakRecordingSettingsAndCanBeResetSeparately() {
        try (HistoryStore history = new HistoryStore(context)) {
            history.append(List.of(new HistorySeries.Sample(now, 78)), now);
        }
        context.getSharedPreferences(BatteryTestStore.PREFERENCES, Context.MODE_PRIVATE).edit().putString("active", "broken").commit();
        new HistorySettings(context).mode(true, false);
        assertTrue(new HistorySettings(context).recording());
        assertThrows(IllegalStateException.class, store::active);
        store.reset();
        assertNull(store.active());
        try (HistoryStore history = new HistoryStore(context)) {
            assertEquals(78, history.read(HistorySeries.Span.HOUR, now).latestBpm, 0);
        }
    }

    private boolean hasText(View view, String text) {
        if (view instanceof TextView label && text.contentEquals(label.getText())) return true;
        if (view instanceof ViewGroup group) {
            for (int index = 0; index < group.getChildCount(); index++) if (hasText(group.getChildAt(index), text)) return true;
        }
        return false;
    }

    private void draw(View view, int width, int height) {
        view.measure(View.MeasureSpec.makeMeasureSpec(width, View.MeasureSpec.EXACTLY), View.MeasureSpec.makeMeasureSpec(height, View.MeasureSpec.EXACTLY));
        view.layout(0, 0, width, height);
        Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
        view.draw(new Canvas(bitmap));
        bitmap.recycle();
    }

    private String await(Consumer<Consumer<String>> operation) throws Exception {
        CountDownLatch finished = new CountDownLatch(1);
        AtomicReference<String> result = new AtomicReference<>();
        operation.accept(value -> { result.set(value); finished.countDown(); });
        assertTrue(finished.await(40, TimeUnit.SECONDS));
        return result.get();
    }

    private Run run(String id, long created) {
        return new Run(id, Mode.BASELINE, false, false, created, BatteryReader.configuration(context), true,
                List.of(), false, Issue.NONE);
    }

    private Reading reading(long hours, int percent) {
        return new Reading(now + hours * HOUR_MS, hours * HOUR_MS, 4, percent, percent * 5_000, false, 2);
    }
}
