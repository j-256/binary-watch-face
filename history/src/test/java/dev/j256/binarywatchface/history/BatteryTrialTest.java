package dev.j256.binarywatchface.history;

import org.junit.Test;

import java.util.List;

import static dev.j256.binarywatchface.history.BatteryTrial.*;
import static org.junit.Assert.*;

public class BatteryTrialTest {
    @Test public void ratesUseMonotonicElapsedTimeEvenWhenWallClockChanges() {
        Run run = run(Mode.BASELINE).observe(reading(0, 90), false, true)
                .observe(new Reading(-1_000_000, 12 * HOUR_MS, 4, 72, 360_000, false, 2), true, true);
        assertEquals(1.5, run.percentPerHour(), 0.0001);
        assertEquals(7.5, run.mahPerHour(), 0.0001);
        assertTrue(run.comparable());
    }

    @Test public void rebootAndUpdateCannotMasqueradeAsLongRuns() {
        Run run = run(Mode.BASELINE).observe(reading(0, 90), false, true);
        assertEquals(Issue.RESTARTED, run.observe(new Reading(1, 24 * HOUR_MS, 5, 50, UNKNOWN, false, 2), true, true).issue());
        assertEquals(Issue.UPDATED, run.observe(new Reading(1, 24 * HOUR_MS, 4, 50, UNKNOWN, false, 3), true, true).issue());
    }

    @Test public void missingReadingsChargingAndBadElapsedTimesAreExcluded() {
        Run run = run(Mode.BASELINE).observe(reading(1, 90), false, true);
        assertEquals(Issue.UNAVAILABLE, run.observe(new Reading(1, HOUR_MS, 4, UNKNOWN, UNKNOWN, false, 2), true, true).issue());
        assertEquals(Issue.CHARGING, run.observe(new Reading(1, HOUR_MS, 4, 80, UNKNOWN, true, 2), true, true).issue());
        assertEquals(Issue.CLOCK_INVALID, run.observe(reading(0, 80), true, true).issue());
        assertEquals(Issue.CLOCK_INVALID, run.observe(reading(1, 80), true, true).issue());
        assertEquals(Issue.REPORTED_INTERRUPTION, run.observe(reading(24, 80), true, false).issue());
    }

    @Test public void interveningGaugeRiseStaysExcludedEvenIfFinalBatteryIsLower() {
        Run run = run(Mode.BASELINE).observe(reading(0, 90), false, true)
                .observe(reading(2, 85), false, true).observe(reading(3, 87), false, true)
                .observe(reading(24, 60), true, true);
        assertEquals(Issue.GAUGE_ROSE, run.issue());
        assertFalse(run.comparable());
        assertTrue(Double.isNaN(run.percentPerHour()));
    }

    @Test public void optionalCounterDoesNotPreventPercentageMeasurements() {
        Run run = run(Mode.GRAPH)
                .observe(new Reading(1, 0, 4, 90, UNKNOWN, false, 2), false, true)
                .observe(new Reading(2, 12 * HOUR_MS, 4, 78, UNKNOWN, false, 2), true, true);
        assertEquals(1, run.percentPerHour(), 0);
        assertTrue(Double.isNaN(run.mahPerHour()));
        assertTrue(run.comparable());
    }

    @Test public void comparisonWeightsDurationAndExcludesShortInvalidAndDifferentConfigurations() {
        Run first = run(Mode.BASELINE).observe(reading(0, 90), false, true).observe(reading(12, 78), true, true);
        Run second = run(Mode.BASELINE).observe(reading(0, 90), false, true).observe(reading(24, 42), true, true);
        Run shortRun = run(Mode.BASELINE).observe(reading(0, 90), false, true).observe(reading(1, 60), true, true);
        Run other = first.prepared("different window");
        Summary summary = summarize(List.of(first, second, shortRun, other, first.invalidate(Issue.SETTINGS_CHANGED)), Mode.BASELINE, "setup");
        assertEquals(2, summary.runs());
        assertEquals(36, summary.hours(), 0);
        assertEquals(60 / 36.0, summary.rate(), 0.0001);
        assertEquals(1, summary.low(), 0);
        assertEquals(2, summary.high(), 0);
        assertTrue(Double.isNaN(summarize(List.of(first), Mode.BOTH, "setup").rate()));
    }

    @Test public void boundedReadingsAlwaysPreserveStartAndNewestObservation() {
        Run run = run(Mode.BASELINE).observe(reading(0, 90), false, true);
        for (int index = 1; index <= MAX_READINGS + 10; index++) run = run.observe(reading(index, 80), false, true);
        assertEquals(MAX_READINGS, run.readings().size());
        assertEquals(0, run.first().elapsedMs());
        assertEquals((MAX_READINGS + 10) * HOUR_MS, run.last().elapsedMs());
        assertEquals(90, run.first().percent());
    }

    @Test public void zeroLossIsValidButAnUnfinishedRunIsNotAComparison() {
        Run run = run(Mode.BASELINE).observe(reading(0, 90), false, true).observe(reading(12, 90), false, true);
        assertEquals(0, run.percentPerHour(), 0);
        assertFalse(run.comparable());
        assertTrue(run.observe(reading(24, 90), true, true).comparable());
    }

    @Test public void displayedDurationDoesNotRoundUpToTheComparisonThreshold() {
        assertEquals("11h 59m", BatteryText.hours(12 - 1.0 / HOUR_MS));
        assertEquals("12h 00m", BatteryText.hours(12));
    }

    private static Run run(Mode mode) {
        return new Run("test", mode, true, false, 1, "setup", true, List.of(), false, Issue.NONE);
    }

    private static Reading reading(long hours, int percent) {
        return new Reading(hours * HOUR_MS, hours * HOUR_MS, 4, percent, percent * 5_000, false, 2);
    }
}
