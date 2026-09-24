package dev.j256.binarywatchface.history;

import org.junit.Test;

import java.time.Instant;
import java.time.ZoneId;

import static org.junit.Assert.*;

public class HistoryTimelineTest {
    private static final long NOW = Instant.parse("2026-09-23T14:30:00Z").toEpochMilli();

    @Test public void marksDivideEveryWindowIntoEqualElapsedIntervals() {
        long[] minutes = {5, 10, 60, 240};
        for (HistorySeries.Span span : HistorySeries.Span.values()) {
            HistorySeries series = filled(span, NOW);
            var marks = HistoryTimeline.marks(series);
            assertEquals(minutes[span.ordinal()] * HistorySeries.MINUTE_MS, HistoryTimeline.intervalMs(span));
            assertEquals(7, marks.size());
            assertEquals(series.startMs, marks.get(0).timeMs());
            assertEquals(series.endMs, marks.get(marks.size() - 1).timeMs());
            for (int index = 1; index < marks.size(); index++) {
                assertEquals(HistoryTimeline.intervalMs(span), marks.get(index).timeMs() - marks.get(index - 1).timeMs());
                assertTrue(marks.get(index).fraction() > marks.get(index - 1).fraction());
            }
        }
    }

    @Test public void markPositionsInterpolateTheRenderedTrace() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.HOUR, NOW);
        for (int index = 0; index < series.buckets.length; index++) {
            double fraction = (index + 0.5) / series.buckets.length;
            series.add(new HistorySeries.Sample(series.startMs + (long) (fraction * series.span.durationMs),
                    60 + 100 * fraction));
        }
        for (HistoryTimeline.Mark mark : HistoryTimeline.marks(series)) {
            assertEquals(60 + 100 * mark.fraction(), mark.bpm(), 0.0001);
        }
    }

    @Test public void densitiesUseCountableIntervalsInEveryWindowIncludingAcrossDaylightSaving() {
        long[][] minutes = {{10, 5, 2}, {20, 10, 5}, {120, 60, 30}, {480, 240, 120}};
        long dstEnd = Instant.parse("2026-11-01T07:30:00Z").toEpochMilli();
        for (HistorySeries.Span span : HistorySeries.Span.values()) {
            for (HistoryTimeline.Density density : HistoryTimeline.Density.values()) {
                HistorySeries series = filled(span, dstEnd);
                long interval = minutes[span.ordinal()][density.ordinal()] * HistorySeries.MINUTE_MS;
                assertEquals(interval, HistoryTimeline.intervalMs(span, density));
                var marks = HistoryTimeline.marks(series, density);
                assertEquals(span.durationMs / interval + 1, marks.size());
                assertEquals(series.startMs, marks.get(0).timeMs());
                assertEquals(series.endMs, marks.get(marks.size() - 1).timeMs());
                for (int index = 1; index < marks.size(); index++) {
                    assertEquals(interval, marks.get(index).timeMs() - marks.get(index - 1).timeMs());
                }
            }
        }
    }

    @Test public void noDensityPlacesMarkersInGapsOrOutsideRecordedHistory() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.HOUR, NOW);
        for (int minute = 10; minute <= 50; minute++) {
            if (minute >= 24 && minute <= 36) continue;
            series.add(new HistorySeries.Sample(series.startMs + minute * HistorySeries.MINUTE_MS, 70));
        }
        for (HistoryTimeline.Density density : HistoryTimeline.Density.values()) {
            var marks = HistoryTimeline.marks(series, density);
            assertFalse(marks.isEmpty());
            for (HistoryTimeline.Mark mark : marks) {
                long minute = (mark.timeMs() - series.startMs) / HistorySeries.MINUTE_MS;
                assertTrue(minute >= 10 && minute <= 50);
                assertTrue(minute < 24 || minute > 36);
            }
        }
    }

    @Test public void marksNeverBridgeGapsOrExtendPartialHistory() {
        HistorySeries series = new HistorySeries(HistorySeries.Span.HOUR, NOW);
        for (int minute = 0; minute <= 60; minute++) {
            if (minute < 12 || minute > 53 || (minute >= 27 && minute <= 33)) continue;
            series.add(new HistorySeries.Sample(series.startMs + minute * HistorySeries.MINUTE_MS, 70));
        }
        var marks = HistoryTimeline.marks(series);
        assertEquals(3, marks.size());
        assertEquals(series.startMs + 20 * HistorySeries.MINUTE_MS, marks.get(0).timeMs());
        assertEquals(series.startMs + 40 * HistorySeries.MINUTE_MS, marks.get(1).timeMs());
        assertEquals(series.startMs + 50 * HistorySeries.MINUTE_MS, marks.get(2).timeMs());
        assertTrue(HistoryTimeline.marks(new HistorySeries(HistorySeries.Span.HOUR, NOW)).isEmpty());
    }

    @Test public void sideLabelsUseLocalTimeAndIdentifyDifferentDays() {
        HistorySeries hour = new HistorySeries(HistorySeries.Span.HOUR, NOW);
        ZoneId kolkata = ZoneId.of("Asia/Kolkata");
        assertEquals(new HistoryTimeline.Label("19:00", ""), HistoryTimeline.label(hour, false, kolkata));
        assertEquals(new HistoryTimeline.Label("20:00", ""), HistoryTimeline.label(hour, true, kolkata));
        HistorySeries day = new HistorySeries(HistorySeries.Span.DAY, NOW);
        assertEquals(new HistoryTimeline.Label("14:30", "Tue"), HistoryTimeline.label(day, false, ZoneId.of("UTC")));
        assertEquals(new HistoryTimeline.Label("14:30", "Wed"), HistoryTimeline.label(day, true, ZoneId.of("UTC")));
    }

    @Test public void daylightSavingChangesLabelsWithoutChangingElapsedSpacing() {
        long end = Instant.parse("2026-11-01T07:30:00Z").toEpochMilli();
        HistorySeries day = filled(HistorySeries.Span.DAY, end);
        ZoneId chicago = ZoneId.of("America/Chicago");
        assertEquals(new HistoryTimeline.Label("02:30", "Sat"), HistoryTimeline.label(day, false, chicago));
        assertEquals(new HistoryTimeline.Label("01:30", "Sun"), HistoryTimeline.label(day, true, chicago));
        var marks = HistoryTimeline.marks(day);
        for (int index = 1; index < marks.size(); index++) {
            assertEquals(4 * 60 * HistorySeries.MINUTE_MS, marks.get(index).timeMs() - marks.get(index - 1).timeMs());
        }
    }

    private HistorySeries filled(HistorySeries.Span span, long end) {
        HistorySeries series = new HistorySeries(span, end);
        for (long time = series.startMs; time <= end; time += HistorySeries.MINUTE_MS) {
            series.add(new HistorySeries.Sample(time, 70));
        }
        return series;
    }
}
