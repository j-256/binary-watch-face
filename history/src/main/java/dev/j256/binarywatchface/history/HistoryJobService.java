package dev.j256.binarywatchface.history;

import android.app.job.JobParameters;
import android.app.job.JobService;
import android.util.Log;

public final class HistoryJobService extends JobService {
    @Override public boolean onStartJob(JobParameters parameters) {
        HistoryRuntime.HEALTH.execute(() -> {
            boolean retry = false;
            try (HistoryStore store = new HistoryStore(this)) {
                store.prune(System.currentTimeMillis());
                retry = !HistoryRuntime.register(this);
            } catch (RuntimeException error) {
                new HistorySettings(this).status(HistorySettings.STATUS_STORAGE_ERROR);
                Log.w(HistoryRuntime.LOG_TAG, "event=maintenance result=" + error.getClass().getSimpleName());
                retry = true;
            } finally {
                jobFinished(parameters, retry);
            }
        });
        return true;
    }

    @Override public boolean onStopJob(JobParameters parameters) {
        return new HistorySettings(this).recording();
    }
}
