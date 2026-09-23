package dev.j256.binarywatchface.history;

import java.util.Locale;

final class BatteryText {
    static String mode(BatteryTrial.Mode mode) {
        return switch (mode) {
            case BASELINE -> "Baseline";
            case RECORDING -> "Tracking only";
            case GRAPH -> "Graph only";
            case BOTH -> "Tracking + graph";
        };
    }

    static String issue(BatteryTrial.Issue issue) {
        return switch (issue) {
            case NONE -> "";
            case CHARGING -> "Charging observed";
            case RESTARTED -> "Watch restarted";
            case UPDATED -> "App updated";
            case SETTINGS_CHANGED -> "Settings changed";
            case RECORDING_FAILED -> "Recording mode failed or changed";
            case GAUGE_ROSE -> "Battery gauge increased";
            case REPORTED_INTERRUPTION -> "Interruption reported";
            case UNAVAILABLE -> "Battery reading unavailable";
            case CLOCK_INVALID -> "Elapsed time unavailable";
        };
    }

    static String rate(double value) { return String.format(Locale.getDefault(), "%.2f pp/h", value); }
    static String hours(double value) {
        long minutes = (long) (Math.max(0, value) * 60);
        return String.format(Locale.getDefault(), "%dh %02dm", minutes / 60, minutes % 60);
    }
    private BatteryText() {}
}
