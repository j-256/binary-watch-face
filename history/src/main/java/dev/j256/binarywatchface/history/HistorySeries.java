package dev.j256.binarywatchface.history;

import java.util.ArrayList;
import java.util.List;

/** Bounded graph projections with honest gaps and preserved extrema */
public final class HistorySeries {
    public static final long SECOND_MS = 1_000L;
    public static final long MINUTE_MS = 60 * SECOND_MS;
    public static final long RETENTION_MS = 24 * 60 * MINUTE_MS;
    public static final long MAX_GAP_MS = 2 * MINUTE_MS;
    public static final long STALE_AFTER_MS = 15 * MINUTE_MS;
    public static final int BUCKET_COUNT = 120;
    public static final double MIN_BPM = 25;
    public static final double MAX_BPM = 240;

    public enum Span {
        HALF_HOUR("30 min", 30 * MINUTE_MS),
        HOUR("1 hour", 60 * MINUTE_MS),
        SIX_HOURS("6 hours", 6 * 60 * MINUTE_MS),
        DAY("24 hours", RETENTION_MS);

        public final String label;
        public final long durationMs;

        Span(String label, long durationMs) {
            this.label = label;
            this.durationMs = durationMs;
        }

        public static Span fromName(String name) {
            for (Span span : values()) {
                if (span.name().equals(name)) return span;
            }
            return HOUR;
        }
    }

    public record Sample(long timeMs, double bpm) {}

    public static final class Bucket {
        public int count;
        public double minimum = Double.POSITIVE_INFINITY;
        public double maximum = Double.NEGATIVE_INFINITY;
        public double sum;
        public long firstMs = Long.MAX_VALUE;
        public long lastMs = Long.MIN_VALUE;

        void add(Sample sample) {
            count++;
            minimum = Math.min(minimum, sample.bpm());
            maximum = Math.max(maximum, sample.bpm());
            sum += sample.bpm();
            firstMs = Math.min(firstMs, sample.timeMs());
            lastMs = Math.max(lastMs, sample.timeMs());
        }

        public double average() {
            return sum / count;
        }
    }

    public final Span span;
    public final long endMs;
    public final long startMs;
    public final Bucket[] buckets = new Bucket[BUCKET_COUNT];
    public int sampleCount;
    public long latestMs;
    public double latestBpm;
    public double minimum = Double.POSITIVE_INFINITY;
    public double maximum = Double.NEGATIVE_INFINITY;

    public HistorySeries(Span span, long nowMs) {
        this.span = span;
        endMs = nowMs;
        startMs = nowMs - span.durationMs;
        for (int index = 0; index < buckets.length; index++) buckets[index] = new Bucket();
    }

    public static boolean valid(Sample sample, long nowMs) {
        return sample.timeMs() > 0 && sample.timeMs() <= nowMs
                && sample.timeMs() >= nowMs - RETENTION_MS
                && Double.isFinite(sample.bpm())
                && sample.bpm() >= MIN_BPM && sample.bpm() <= MAX_BPM;
    }

    public void add(Sample sample) {
        if (!valid(sample, endMs) || sample.timeMs() < startMs) return;
        int index = (int) ((sample.timeMs() - startMs) * BUCKET_COUNT / span.durationMs);
        buckets[Math.min(BUCKET_COUNT - 1, index)].add(sample);
        sampleCount++;
        minimum = Math.min(minimum, sample.bpm());
        maximum = Math.max(maximum, sample.bpm());
        if (sample.timeMs() >= latestMs) {
            latestMs = sample.timeMs();
            latestBpm = sample.bpm();
        }
    }

    public boolean isStale() {
        return sampleCount > 0 && endMs - latestMs > STALE_AFTER_MS;
    }

    public boolean connects(int previous, int next) {
        return previous >= 0 && next > previous && next < buckets.length
                && buckets[previous].count > 0 && buckets[next].count > 0
                && buckets[next].firstMs - buckets[previous].lastMs <= MAX_GAP_MS;
    }

    public double lowerBound() {
        return sampleCount == 0 ? 40 : Math.max(20, Math.floor((minimum - 10) / 20) * 20);
    }

    public double upperBound() {
        return sampleCount == 0 ? 160 : Math.max(lowerBound() + 60, Math.ceil((maximum + 10) / 20) * 20);
    }

    public static HistorySeries demo(Span span, long nowMs) {
        HistorySeries result = new HistorySeries(span, nowMs);
        for (Sample sample : demoSamples(nowMs)) result.add(sample);
        return result;
    }

    public static List<Sample> demoSamples(long nowMs) {
        List<Sample> result = new ArrayList<>();
        for (int minute = 0; minute <= 24 * 60; minute++) {
            long time = nowMs - RETENTION_MS + minute * MINUTE_MS;
            int remaining = 24 * 60 - minute;
            if ((remaining >= 18 && remaining <= 21) || (remaining >= 380 && remaining <= 410)) continue;
            double baseline = 67 + 6 * Math.sin(minute * 0.19) + 3 * Math.cos(minute * 0.67);
            double walk = 45 * Math.exp(-Math.pow((remaining - 42) / 13.0, 2));
            double workout = 91 * Math.exp(-Math.pow((remaining - 180) / 26.0, 2));
            double sleep = remaining > 600 && remaining < 1080 ? -13 : 0;
            result.add(new Sample(time, baseline + walk + workout + sleep));
        }
        return result;
    }
}
