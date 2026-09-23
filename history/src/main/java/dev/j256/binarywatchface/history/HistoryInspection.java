package dev.j256.binarywatchface.history;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Select recorded values without inventing readings in the gaps */
public final class HistoryInspection {
    private static final long SNAP_DISTANCE_MS = HistorySeries.MAX_GAP_MS / 2;
    private final HistorySeries series;
    private final List<HistorySeries.Sample> readings;

    public record Selection(long timeMs, HistorySeries.Sample reading) {}

    public HistoryInspection(HistorySeries series) {
        this.series = series;
        readings = new ArrayList<>(series.readings());
        readings.sort(Comparator.comparingLong(HistorySeries.Sample::timeMs));
    }

    public Selection select(double fraction) {
        long time = series.startMs + Math.round(Math.max(0, Math.min(1, fraction)) * series.span.durationMs);
        int left = 0;
        int right = readings.size();
        while (left < right) {
            int middle = (left + right) / 2;
            if (readings.get(middle).timeMs() < time) left = middle + 1;
            else right = middle;
        }
        HistorySeries.Sample nearest = left < readings.size() ? readings.get(left) : null;
        if (left > 0) {
            HistorySeries.Sample before = readings.get(left - 1);
            if (nearest == null || time - before.timeMs() <= nearest.timeMs() - time) nearest = before;
        }
        if (nearest == null || Math.abs(nearest.timeMs() - time) > SNAP_DISTANCE_MS) {
            return new Selection(time, null);
        }
        return new Selection(nearest.timeMs(), nearest);
    }
}
