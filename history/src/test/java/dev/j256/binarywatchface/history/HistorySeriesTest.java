package dev.j256.binarywatchface.history;

import org.junit.Test;

import static org.junit.Assert.*;

public class HistorySeriesTest {
    private static final long NOW = 1_800_000_000_000L;

    @Test public void binsUnsortedReadingsAndPreservesShortSpikes() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.DAY, NOW);
        series.add(new HistorySeries.Sample(NOW - 3_000, 72));
        series.add(new HistorySeries.Sample(NOW - 9_000, 182));
        series.add(new HistorySeries.Sample(NOW - 6_000, 65));
        assertEquals(3, series.sampleCount);
        assertEquals(182, series.maximum, 0);
        assertEquals(65, series.minimum, 0);
        assertEquals(72, series.latestBpm, 0);
        assertEquals(182, series.buckets[119].maximum, 0);
        assertEquals((72 + 182 + 65) / 3.0, series.buckets[119].average(), 0.001);
    }

    @Test public void rejectsInvalidFutureAndExpiredReadings() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.DAY, NOW);
        for (double bpm : new double[]{0, -1, 241, Double.NaN, Double.POSITIVE_INFINITY}) {
            series.add(new HistorySeries.Sample(NOW, bpm));
        }
        series.add(new HistorySeries.Sample(NOW + 1, 70));
        series.add(new HistorySeries.Sample(NOW - HistorySeries.RETENTION_MS - 1, 70));
        assertEquals(0, series.sampleCount);
        assertFalse(series.isStale());
    }

    @Test public void eachSpanHasAnInclusiveStartAndNowBoundary() {
        for (HistorySeries.Span span : HistorySeries.Span.values()) {
            HistorySeries series = new HistorySeries(span, NOW);
            series.add(new HistorySeries.Sample(NOW - span.durationMs, 60));
            series.add(new HistorySeries.Sample(NOW - span.durationMs - 1, 150));
            series.add(new HistorySeries.Sample(NOW, 80));
            assertEquals(2, series.sampleCount);
            assertEquals(1, series.buckets[0].count);
            assertEquals(1, series.buckets[119].count);
        }
    }

    @Test public void longPausesRemainGapsEvenInAdjacentLargeBuckets() {
        HistorySeries shortSeries = new HistorySeries(HistorySeries.Span.HALF_HOUR, NOW);
        shortSeries.add(new HistorySeries.Sample(NOW - 3 * HistorySeries.MINUTE_MS, 65));
        shortSeries.add(new HistorySeries.Sample(NOW, 75));
        assertFalse(shortSeries.connects(108, 119));
        HistorySeries day = new HistorySeries(HistorySeries.Span.DAY, NOW);
        day.add(new HistorySeries.Sample(NOW - 13 * HistorySeries.MINUTE_MS, 65));
        day.add(new HistorySeries.Sample(NOW, 75));
        assertFalse(day.connects(118, 119));
    }

    @Test public void adjacentContinuousBucketsConnect() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.HOUR, NOW);
        series.add(new HistorySeries.Sample(NOW - 31_000, 65));
        series.add(new HistorySeries.Sample(NOW - 29_000, 75));
        assertTrue(series.connects(118, 119));
        series.add(new HistorySeries.Sample(NOW - 2 * HistorySeries.MINUTE_MS, 60));
        assertTrue(series.connects(116, 119));
    }

    @Test public void stalenessUsesMeasurementTime() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.HOUR, NOW);
        series.add(new HistorySeries.Sample(NOW - HistorySeries.STALE_AFTER_MS - 1, 65));
        assertTrue(series.isStale());
        series.add(new HistorySeries.Sample(NOW - 1_000, 75));
        assertFalse(series.isStale());
    }

    @Test public void flatSeriesRetainsUsefulScale() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.HOUR, NOW);
        series.add(new HistorySeries.Sample(NOW, 70));
        assertTrue(series.upperBound() - series.lowerBound() >= 60);
        assertTrue(series.lowerBound() < 70);
        assertTrue(series.upperBound() > 70);
    }

    @Test public void demoOffersEverySpanAndDoesNotInventGapReadings() {
        for (HistorySeries.Span span : HistorySeries.Span.values()) {
            HistorySeries series = HistorySeries.demo(span, NOW);
            assertTrue(series.sampleCount > 0);
            assertFalse(series.isStale());
        }
        assertTrue(HistorySeries.demoSamples(NOW).stream().noneMatch(sample ->
                sample.timeMs() >= NOW - 21 * HistorySeries.MINUTE_MS
                && sample.timeMs() <= NOW - 18 * HistorySeries.MINUTE_MS));
        assertEquals(HistorySeries.Span.HOUR, HistorySeries.Span.fromName("unrecognized"));
    }
}
