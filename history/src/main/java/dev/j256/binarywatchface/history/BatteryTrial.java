package dev.j256.binarywatchface.history;

import java.util.ArrayList;
import java.util.List;

/** Battery observations and comparison rules, independent of Android services */
public final class BatteryTrial {
    public static final long HOUR_MS = 60 * 60 * 1_000L;
    public static final long COMPARISON_MIN_MS = 12 * HOUR_MS;
    public static final int MAX_READINGS = 96;
    public static final int UNKNOWN = -1;

    public enum Mode {
        BASELINE(false, false), RECORDING(true, false), GRAPH(false, true), BOTH(true, true);

        public final boolean recording;
        public final boolean graph;

        Mode(boolean recording, boolean graph) {
            this.recording = recording;
            this.graph = graph;
        }

        public boolean demo() { return this == GRAPH; }
    }

    public enum Issue {
        NONE, CHARGING, RESTARTED, UPDATED, SETTINGS_CHANGED, RECORDING_FAILED,
        GAUGE_ROSE, REPORTED_INTERRUPTION, UNAVAILABLE, CLOCK_INVALID
    }

    public record Reading(long wallMs, long elapsedMs, int bootCount, int percent,
            int chargeUah, boolean plugged, long versionCode) {
        public boolean available() {
            return percent >= 0 && percent <= 100 && bootCount >= 0 && elapsedMs >= 0;
        }
    }

    public record Run(String id, Mode mode, boolean previousRecording, boolean previousDemo,
            long createdMs, String configuration, boolean ready, List<Reading> readings,
            boolean finished, Issue issue) {
        public Run {
            readings = List.copyOf(readings);
        }

        public boolean started() { return !readings.isEmpty(); }
        public Reading first() { return readings.get(0); }
        public Reading last() { return readings.get(readings.size() - 1); }
        public long durationMs() { return started() ? last().elapsedMs - first().elapsedMs : 0; }
        public double hours() { return durationMs() / (double) HOUR_MS; }
        public double percentPerHour() {
            return issue == Issue.NONE && hours() > 0 ? (first().percent - last().percent) / hours() : Double.NaN;
        }
        public double mahPerHour() {
            return issue == Issue.NONE && hours() > 0 && first().chargeUah >= 0 && last().chargeUah >= 0
                    ? (first().chargeUah - last().chargeUah) / 1_000.0 / hours() : Double.NaN;
        }
        public boolean comparable() {
            return finished && issue == Issue.NONE && durationMs() >= COMPARISON_MIN_MS;
        }
        public Run prepared(String config) {
            return new Run(id, mode, previousRecording, previousDemo, createdMs, config, true, readings, finished, issue);
        }
        public Run invalidate(Issue reason) {
            return new Run(id, mode, previousRecording, previousDemo, createdMs, configuration, ready,
                    readings, finished, issue == Issue.NONE ? reason : issue);
        }
        public Run observe(Reading reading, boolean finish, boolean uninterrupted) {
            Issue problem = issue;
            if (problem == Issue.NONE) problem = validate(readings, reading, finish);
            if (problem == Issue.NONE && !uninterrupted) problem = Issue.REPORTED_INTERRUPTION;
            List<Reading> points = new ArrayList<>(readings);
            if (points.size() >= MAX_READINGS) points.remove(1);
            points.add(reading);
            return new Run(id, mode, previousRecording, previousDemo, createdMs, configuration, ready,
                    points, finish, problem);
        }
    }

    public record Summary(Mode mode, int runs, double hours, double rate, double low, double high) {}

    public static Summary summarize(List<Run> runs, Mode mode, String configuration) {
        int count = 0;
        double hours = 0;
        double loss = 0;
        double low = Double.POSITIVE_INFINITY;
        double high = Double.NEGATIVE_INFINITY;
        for (Run run : runs) {
            if (run.mode != mode || !run.configuration.equals(configuration) || !run.comparable()) continue;
            count++;
            hours += run.hours();
            loss += run.first().percent - run.last().percent;
            low = Math.min(low, run.percentPerHour());
            high = Math.max(high, run.percentPerHour());
        }
        return new Summary(mode, count, hours, count == 0 ? Double.NaN : loss / hours, low, high);
    }

    private static Issue validate(List<Reading> readings, Reading next, boolean finish) {
        if (!next.available()) return Issue.UNAVAILABLE;
        if (next.plugged) return Issue.CHARGING;
        if (readings.isEmpty()) return Issue.NONE;
        Reading first = readings.get(0);
        Reading previous = readings.get(readings.size() - 1);
        if (next.bootCount != first.bootCount) return Issue.RESTARTED;
        if (next.versionCode != first.versionCode) return Issue.UPDATED;
        if (next.elapsedMs < previous.elapsedMs || (finish && next.elapsedMs <= first.elapsedMs)) return Issue.CLOCK_INVALID;
        if (next.percent > previous.percent
                || (next.chargeUah >= 0 && previous.chargeUah >= 0 && next.chargeUah > previous.chargeUah)) {
            return Issue.GAUGE_ROSE;
        }
        return Issue.NONE;
    }

    private BatteryTrial() {}
}
