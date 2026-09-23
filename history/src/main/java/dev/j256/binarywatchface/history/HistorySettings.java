package dev.j256.binarywatchface.history;

import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;

public final class HistorySettings {
    public static final String HEART_PERMISSION = "android.permission.health.READ_HEART_RATE";
    public static final String BACKGROUND_PERMISSION = "android.permission.health.READ_HEALTH_DATA_IN_BACKGROUND";
    public static final String STATUS_PAUSED = "paused";
    public static final String STATUS_STARTING = "starting";
    public static final String STATUS_RECORDING = "recording";
    public static final String STATUS_PERMISSION = "permission";
    public static final String STATUS_UNSUPPORTED = "unsupported";
    public static final String STATUS_ERROR = "error";
    public static final String STATUS_STORAGE_ERROR = "storage_error";
    public static final String STATUS_SCHEDULE_ERROR = "schedule_error";
    private final SharedPreferences preferences;

    public HistorySettings(Context context) {
        preferences = context.getSharedPreferences("history-settings", Context.MODE_PRIVATE);
    }

    public HistorySeries.Span span() {
        return HistorySeries.Span.fromName(preferences.getString("span", HistorySeries.Span.HOUR.name()));
    }

    public void span(HistorySeries.Span value) {
        preferences.edit().putString("span", value.name()).apply();
    }

    public boolean recording() { return preferences.getBoolean("recording", false); }
    public boolean demo() { return preferences.getBoolean("demo", false); }
    public String status() { return preferences.getString("status", STATUS_PAUSED); }

    public void mode(boolean recording, boolean demo) {
        preferences.edit().putBoolean("recording", recording).putBoolean("demo", demo).apply();
    }

    public void status(String value) {
        preferences.edit().putString("status", value).apply();
    }

    public static boolean hasPermissions(Context context) {
        return context.checkSelfPermission(HEART_PERMISSION) == PackageManager.PERMISSION_GRANTED
                && context.checkSelfPermission(BACKGROUND_PERMISSION) == PackageManager.PERMISSION_GRANTED;
    }
}
