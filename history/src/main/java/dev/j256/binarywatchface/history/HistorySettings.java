package dev.j256.binarywatchface.history;

import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;

public final class HistorySettings {
    public static final String HEART_PERMISSION = "android.permission.health.READ_HEART_RATE";
    public static final String BACKGROUND_PERMISSION = "android.permission.health.READ_HEALTH_DATA_IN_BACKGROUND";
    public static final String STATUS_PAUSED = "paused";
    public static final String STATUS_PAUSING = "pausing";
    public static final String STATUS_PAUSE_ERROR = "pause_error";
    public static final String STATUS_STARTING = "starting";
    public static final String STATUS_RECORDING = "recording";
    public static final String STATUS_PERMISSION = "permission";
    public static final String STATUS_UNSUPPORTED = "unsupported";
    public static final String STATUS_ERROR = "error";
    public static final String STATUS_STORAGE_ERROR = "storage_error";
    public static final String STATUS_SCHEDULE_ERROR = "schedule_error";
    static final String LABELS_KEY = "labels";
    static final String MARKERS_KEY = "markers";
    private static final String DENSITY_PREFIX = "marker-density-";

    public enum Labels {
        NONE(R.string.labels_none), WINDOW(R.string.labels_window), RANGE(R.string.labels_range);

        public final int title;

        Labels(int title) { this.title = title; }
    }

    public enum Markers {
        NONE(R.string.markers_none), TICKS(R.string.markers_ticks),
        DOTS(R.string.markers_dots), TRIANGLES(R.string.markers_triangles);

        public final int title;

        Markers(int title) { this.title = title; }
    }

    private final SharedPreferences preferences;
    private final Context context;

    public HistorySettings(Context context) {
        this.context = context.getApplicationContext();
        preferences = context.getSharedPreferences("history-settings", Context.MODE_PRIVATE);
        synchronized (HistorySettings.class) {
            if (!preferences.contains(MARKERS_KEY)) {
                // Preserve the old combined labels-and-ticks preference on upgrade
                preferences.edit().putString(MARKERS_KEY,
                        (labels() == Labels.NONE ? Markers.NONE : Markers.TICKS).name()).apply();
            }
        }
    }

    public HistorySeries.Span span() {
        return HistorySeries.Span.fromName(preferences.getString("span", HistorySeries.Span.HOUR.name()));
    }

    public void span(HistorySeries.Span value) {
        if (value != span()) BatteryTestStore.invalidate(context, BatteryTrial.Issue.SETTINGS_CHANGED);
        preferences.edit().putString("span", value.name()).apply();
    }

    public Labels labels() {
        String name = preferences.getString(LABELS_KEY, Labels.NONE.name());
        for (Labels value : Labels.values()) if (value.name().equals(name)) return value;
        return Labels.NONE;
    }

    public void labels(Labels value) {
        if (value != labels()) BatteryTestStore.invalidate(context, BatteryTrial.Issue.SETTINGS_CHANGED);
        preferences.edit().putString(LABELS_KEY, value.name()).apply();
    }

    public Markers markers() {
        String name = preferences.getString(MARKERS_KEY, Markers.NONE.name());
        for (Markers value : Markers.values()) if (value.name().equals(name)) return value;
        return Markers.NONE;
    }

    public void markers(Markers value) {
        if (value != markers()) BatteryTestStore.invalidate(context, BatteryTrial.Issue.SETTINGS_CHANGED);
        preferences.edit().putString(MARKERS_KEY, value.name()).apply();
    }

    public HistoryTimeline.Density density() { return density(span()); }

    public HistoryTimeline.Density density(HistorySeries.Span span) {
        String name = preferences.getString(DENSITY_PREFIX + span.name(), HistoryTimeline.Density.REGULAR.name());
        for (HistoryTimeline.Density value : HistoryTimeline.Density.values()) if (value.name().equals(name)) return value;
        return HistoryTimeline.Density.REGULAR;
    }

    public void density(HistorySeries.Span span, HistoryTimeline.Density value) {
        if (span == span() && value != density(span)) {
            BatteryTestStore.invalidate(context, BatteryTrial.Issue.SETTINGS_CHANGED);
        }
        preferences.edit().putString(DENSITY_PREFIX + span.name(), value.name()).apply();
    }

    public boolean recording() { return preferences.getBoolean("recording", false); }
    public boolean demo() { return preferences.getBoolean("demo", false); }
    public String status() { return preferences.getString("status", STATUS_PAUSED); }

    public void mode(boolean recording, boolean demo) {
        if (recording != recording() || demo != demo()) {
            BatteryTestStore.invalidate(context, BatteryTrial.Issue.SETTINGS_CHANGED);
        }
        preferences.edit().putBoolean("recording", recording).putBoolean("demo", demo).apply();
    }

    public void status(String value) {
        if (STATUS_PERMISSION.equals(value) || STATUS_UNSUPPORTED.equals(value) || STATUS_ERROR.equals(value)
                || STATUS_STORAGE_ERROR.equals(value) || STATUS_SCHEDULE_ERROR.equals(value) || STATUS_PAUSE_ERROR.equals(value)) {
            BatteryTestStore.invalidate(context, BatteryTrial.Issue.RECORDING_FAILED);
        }
        preferences.edit().putString("status", value).apply();
    }

    public static boolean hasPermissions(Context context) {
        return context.checkSelfPermission(HEART_PERMISSION) == PackageManager.PERMISSION_GRANTED
                && context.checkSelfPermission(BACKGROUND_PERMISSION) == PackageManager.PERMISSION_GRANTED;
    }
}
