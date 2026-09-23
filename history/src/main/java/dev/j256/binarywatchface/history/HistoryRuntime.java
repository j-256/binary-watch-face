package dev.j256.binarywatchface.history;

import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;
import android.os.SystemClock;
import android.util.Log;

import androidx.health.services.client.HealthServices;
import androidx.health.services.client.PassiveMonitoringClient;
import androidx.health.services.client.data.DataType;
import androidx.health.services.client.data.PassiveListenerConfig;
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester;

import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/** Serializes registration, local storage work, and explicit user actions */
public final class HistoryRuntime {
    public static final ExecutorService IO = Executors.newSingleThreadExecutor();
    public static final ExecutorService HEALTH = Executors.newSingleThreadExecutor();
    public static final String LOG_TAG = "BinaryHistory";
    private static final int REGISTRATION_JOB = 410;
    private static final int MAINTENANCE_JOB = 411;
    private static final long MAINTENANCE_MS = 6 * 60 * HistorySeries.MINUTE_MS;
    private static final long HEALTH_SERVICE_TIMEOUT_SECONDS = 30;

    private HistoryRuntime() {}

    static PassiveMonitoringClient client(Context context) {
        return HealthServices.getClient(context).getPassiveMonitoringClient();
    }

    public static boolean register(Context context) {
        HistorySettings settings = new HistorySettings(context);
        if (!settings.recording()) return true;
        String operation = UUID.randomUUID().toString().substring(0, 8);
        long started = SystemClock.elapsedRealtime();
        if (!HistorySettings.hasPermissions(context)) {
            settings.mode(false, false);
            settings.status(HistorySettings.STATUS_PERMISSION);
            IO.execute(() -> {
                try (HistoryStore store = new HistoryStore(context)) {
                    store.clear();
                } catch (RuntimeException error) {
                    settings.status(HistorySettings.STATUS_STORAGE_ERROR);
                    Log.w(LOG_TAG, "event=permission_erase result=" + error.getClass().getSimpleName());
                }
                scheduleMaintenance(context);
                requestImage(context);
            });
            log("register", operation, "permission_missing", started, 0);
            return true;
        }
        try {
            PassiveMonitoringClient client = client(context);
            if (!client.getCapabilitiesAsync().get(HEALTH_SERVICE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
                    .getSupportedDataTypesPassiveMonitoring().contains(DataType.HEART_RATE_BPM)) {
                settings.mode(false, false);
                settings.status(HistorySettings.STATUS_UNSUPPORTED);
                log("register", operation, "unsupported", started, 0);
                return true;
            }
            PassiveListenerConfig config = new PassiveListenerConfig.Builder()
                    .setDataTypes(Set.of(DataType.HEART_RATE_BPM)).build();
            if (!settings.recording()) return true;
            client.setPassiveListenerServiceAsync(HeartRateListener.class, config)
                    .get(HEALTH_SERVICE_TIMEOUT_SECONDS, TimeUnit.SECONDS);
            if (settings.recording()) settings.status(HistorySettings.STATUS_RECORDING);
            log("register", operation, "ready", started, 0);
            return true;
        } catch (Exception error) {
            if (error instanceof InterruptedException) Thread.currentThread().interrupt();
            if (settings.recording()) settings.status(HistorySettings.STATUS_ERROR);
            log("register", operation, error.getClass().getSimpleName(), started, 0);
            return false;
        }
    }

    public static void start(Context context, Runnable complete) {
        Context app = context.getApplicationContext();
        IO.execute(() -> {
            HistorySettings settings = new HistorySettings(app);
            settings.mode(true, false);
            settings.status(HistorySettings.STATUS_STARTING);
            scheduleMaintenance(app);
            HEALTH.execute(() -> {
                boolean registered = register(app);
                if (!registered && settings.recording()) scheduleRegistration(app);
                requestImage(app);
                complete.run();
            });
        });
    }

    public static void stop(Context context, boolean demo, Runnable complete) {
        stop(context, demo, !demo, complete);
    }

    public static void pause(Context context, Runnable complete) {
        stop(context, false, false, complete);
    }

    private static void stop(Context context, boolean demo, boolean erase, Runnable complete) {
        Context app = context.getApplicationContext();
        IO.execute(() -> {
            HistorySettings settings = new HistorySettings(app);
            settings.mode(false, demo);
            settings.status(HistorySettings.STATUS_PAUSING);
            app.getSystemService(JobScheduler.class).cancel(REGISTRATION_JOB);
            try (HistoryStore store = new HistoryStore(app)) {
                if (erase) store.clear();
                else store.prune(System.currentTimeMillis());
            } catch (RuntimeException error) {
                settings.status(HistorySettings.STATUS_STORAGE_ERROR);
                Log.w(LOG_TAG, "event=erase result=" + error.getClass().getSimpleName());
            }
            HEALTH.execute(() -> {
                try {
                    client(app).clearPassiveListenerServiceAsync().get(HEALTH_SERVICE_TIMEOUT_SECONDS, TimeUnit.SECONDS);
                    if (HistorySettings.STATUS_PAUSING.equals(settings.status())) settings.status(HistorySettings.STATUS_PAUSED);
                } catch (Exception error) {
                    if (error instanceof InterruptedException) Thread.currentThread().interrupt();
                    settings.status(HistorySettings.STATUS_PAUSE_ERROR);
                    Log.w(LOG_TAG, "event=unregister result=" + error.getClass().getSimpleName());
                } finally {
                    scheduleMaintenance(app);
                    requestImage(app);
                    complete.run();
                }
            });
        });
    }

    public static void scheduleRegistration(Context context) {
        JobInfo job = new JobInfo.Builder(REGISTRATION_JOB, new ComponentName(context, HistoryJobService.class))
                .setMinimumLatency(HistorySeries.SECOND_MS)
                .setBackoffCriteria(30 * HistorySeries.SECOND_MS, JobInfo.BACKOFF_POLICY_EXPONENTIAL)
                .setPersisted(true).build();
        schedule(context, job);
    }

    public static void scheduleMaintenance(Context context) {
        HistorySettings settings = new HistorySettings(context);
        if (!settings.recording() && !settings.demo()) {
            context.getSystemService(JobScheduler.class).cancel(MAINTENANCE_JOB);
            return;
        }
        JobInfo job = new JobInfo.Builder(MAINTENANCE_JOB, new ComponentName(context, HistoryJobService.class))
                .setPeriodic(MAINTENANCE_MS).setPersisted(true).build();
        schedule(context, job);
    }

    private static void schedule(Context context, JobInfo job) {
        if (context.getSystemService(JobScheduler.class).schedule(job) != JobScheduler.RESULT_SUCCESS) {
            Log.w(LOG_TAG, "event=schedule result=rejected job=" + job.getId());
            new HistorySettings(context).status(HistorySettings.STATUS_SCHEDULE_ERROR);
        }
    }

    public static void requestImage(Context context) {
        ComplicationDataSourceUpdateRequester.create(context,
                new ComponentName(context, HeartHistoryComplication.class)).requestUpdateAll();
    }

    public static void log(String event, String operation, String result, long started, int samples) {
        Log.i(LOG_TAG, "event=" + event + " operation=" + operation + " result=" + result
                + " duration_ms=" + (SystemClock.elapsedRealtime() - started) + " samples=" + samples);
    }
}
