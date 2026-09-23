package dev.j256.binarywatchface.history;

import org.junit.Test;

import java.time.Instant;

import static org.junit.Assert.*;

public class HistoryInspectionTest {
    private static final long NOW = Instant.parse("2026-09-23T14:30:00Z").toEpochMilli();

    @Test public void inspectionReturnsTheRecordedTimestampAndValueInsteadOfTheBucketAverage() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.DAY, NOW);
        HistorySeries.Sample first = new HistorySeries.Sample(NOW - 30_000, 70);
        HistorySeries.Sample second = new HistorySeries.Sample(NOW - 10_000, 110);
        series.add(first);
        series.add(second);
        HistoryInspection inspection = new HistoryInspection(series);
        assertEquals(first, inspection.select(fraction(series, NOW - 28_000)).reading());
        assertEquals(second, inspection.select(fraction(series, NOW - 9_000)).reading());
        assertEquals(second.timeMs(), inspection.select(1).timeMs());
    }

    @Test public void gapsAndUnrecordedPartsOfTheWindowHaveNoValue() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.HOUR, NOW);
        series.add(new HistorySeries.Sample(NOW - 45 * HistorySeries.MINUTE_MS, 70));
        series.add(new HistorySeries.Sample(NOW - 15 * HistorySeries.MINUTE_MS, 90));
        HistoryInspection inspection = new HistoryInspection(series);
        assertNull(inspection.select(0).reading());
        assertNull(inspection.select(0.5).reading());
        assertNull(inspection.select(1).reading());
        assertEquals(NOW - 30 * HistorySeries.MINUTE_MS, inspection.select(0.5).timeMs());
        assertEquals(70, inspection.select(0.25).reading().bpm(), 0);
    }

    @Test public void readingsCanArriveOutOfOrderWithoutChangingTheProjection() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.HOUR, NOW);
        series.add(new HistorySeries.Sample(NOW, 90));
        series.add(new HistorySeries.Sample(NOW - HistorySeries.MINUTE_MS, 70));
        HistoryInspection inspection = new HistoryInspection(series);
        assertEquals(70, inspection.select(fraction(series, NOW - 40_000)).reading().bpm(), 0);
        assertEquals(90, inspection.select(1).reading().bpm(), 0);
        assertEquals(NOW, series.readings().get(0).timeMs());
    }

    @Test public void emptyHistoryAndTouchesOutsideThePlotStayWithinTheSelectedWindow() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.HALF_HOUR, NOW);
        series.add(new HistorySeries.Sample(NOW, Double.NaN));
        HistoryInspection inspection = new HistoryInspection(series);
        assertEquals(new HistoryInspection.Selection(series.startMs, null), inspection.select(-1));
        assertEquals(new HistoryInspection.Selection(series.endMs, null), inspection.select(2));
        assertTrue(series.readings().isEmpty());
    }

    private double fraction(HistorySeries series, long time) {
        return (double) (time - series.startMs) / series.span.durationMs;
    }
}
