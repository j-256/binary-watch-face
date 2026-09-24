package dev.j256.binarywatchface.history;

import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Time marks follow the same connected bucket segments as the visible trace */
public final class HistoryTimeline {
    public enum Density {
        SPARSE("Sparse", 3), REGULAR("Regular", 6), DENSE("Dense", 12);

        public final String title;
        private final int intervals;

        Density(String title, int intervals) {
            this.title = title;
            this.intervals = intervals;
        }

        public int intervalCount(HistorySeries.Span span) {
            // Two-minute spacing keeps the shortest dense window easy to count
            return this == DENSE && span == HistorySeries.Span.HALF_HOUR ? 15 : intervals;
        }
    }
    private static final DateTimeFormatter CLOCK = DateTimeFormatter.ofPattern("HH:mm", Locale.ROOT);
    private static final DateTimeFormatter DAY = DateTimeFormatter.ofPattern("EEE", Locale.ROOT);

    public record Mark(long timeMs, double fraction, double bpm) {}
    public record Label(String time, String day) {}

    private HistoryTimeline() {}

    public static long intervalMs(HistorySeries.Span span) {
        return intervalMs(span, Density.REGULAR);
    }

    public static long intervalMs(HistorySeries.Span span, Density density) {
        return span.durationMs / density.intervalCount(span);
    }

    public static List<Mark> marks(HistorySeries series) {
        return marks(series, Density.REGULAR);
    }

    public static List<Mark> marks(HistorySeries series, Density density) {
        List<Mark> result = new ArrayList<>();
        int intervals = density.intervalCount(series.span);
        for (int step = 0; step <= intervals; step++) {
            long timeMs = series.startMs + step * intervalMs(series.span, density);
            Mark mark = at(series, timeMs, (double) step / intervals);
            if (mark != null) result.add(mark);
        }
        return result;
    }

    private static Mark at(HistorySeries series, long timeMs, double fraction) {
        int previous = -1;
        for (int index = 0; index < series.buckets.length; index++) {
            HistorySeries.Bucket bucket = series.buckets[index];
            if (bucket.count == 0) continue;
            double current = fraction(series, index);
            if (fraction <= current) {
                if (previous < 0) {
                    if (index != 0) return null;
                    return new Mark(timeMs, current, bucket.average());
                }
                if (!series.connects(previous, index)) return null;
                double slope = slope(series, previous, index);
                double bpm = series.buckets[previous].average()
                        + slope * (fraction - fraction(series, previous));
                return new Mark(timeMs, fraction, bpm);
            }
            previous = index;
        }
        if (previous != series.buckets.length - 1) return null;
        return new Mark(timeMs, fraction(series, previous), series.buckets[previous].average());
    }

    private static double fraction(HistorySeries series, int index) {
        return (index + 0.5) / series.buckets.length;
    }

    private static double slope(HistorySeries series, int first, int last) {
        return (series.buckets[last].average() - series.buckets[first].average())
                / (fraction(series, last) - fraction(series, first));
    }

    public static Label label(HistorySeries series, boolean end, ZoneId zone) {
        var startTime = Instant.ofEpochMilli(series.startMs).atZone(zone);
        var endTime = Instant.ofEpochMilli(series.endMs).atZone(zone);
        var time = end ? endTime : startTime;
        boolean crossesDay = !startTime.toLocalDate().equals(endTime.toLocalDate());
        return new Label(CLOCK.format(time), crossesDay ? DAY.format(time) : "");
    }
}
