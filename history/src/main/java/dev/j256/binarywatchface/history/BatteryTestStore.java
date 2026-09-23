package dev.j256.binarywatchface.history;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** Bounded private trial storage; no heart-rate readings or background measurement work */
final class BatteryTestStore {
    static final String PREFERENCES = "battery-tests";
    static final int MAX_RUNS = 24;
    static final long RETENTION_MS = 30 * 24 * BatteryTrial.HOUR_MS;
    private static final Object LOCK = new Object();
    private static final String ACTIVE = "active";
    private static final String RESULTS = "results";
    private final SharedPreferences preferences;
    private final Context context;

    BatteryTestStore(Context context) {
        this.context = context.getApplicationContext();
        preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
    }

    BatteryTrial.Run active() {
        synchronized (LOCK) {
            String value = preferences.getString(ACTIVE, null);
            try { return value == null ? null : decode(new JSONObject(value)); }
            catch (JSONException | IllegalArgumentException error) { throw new IllegalStateException("Battery run cannot be read", error); }
        }
    }

    void active(BatteryTrial.Run run) {
        synchronized (LOCK) {
            run = preserveIssue(run);
            try {
                SharedPreferences.Editor editor = preferences.edit();
                if (run == null) editor.remove(ACTIVE);
                else editor.putString(ACTIVE, encode(run).toString());
                if (!editor.commit()) throw new IllegalStateException("Battery run could not be saved");
            } catch (JSONException error) { throw new IllegalStateException("Battery run cannot be encoded", error); }
        }
    }

    List<BatteryTrial.Run> results(long now) {
        synchronized (LOCK) {
            try {
                JSONArray values = new JSONArray(preferences.getString(RESULTS, "[]"));
                List<BatteryTrial.Run> runs = new ArrayList<>();
                for (int index = 0; index < values.length(); index++) {
                    BatteryTrial.Run run = decode(values.getJSONObject(index));
                    if (run.createdMs() >= now - RETENTION_MS) runs.add(run);
                }
                if (runs.size() != values.length()) saveResults(runs);
                return List.copyOf(runs);
            } catch (JSONException | IllegalArgumentException error) { throw new IllegalStateException("Battery results cannot be read", error); }
        }
    }

    void finish(BatteryTrial.Run run) {
        synchronized (LOCK) {
            run = preserveIssue(run);
            String runId = run.id();
            List<BatteryTrial.Run> runs = new ArrayList<>(results(System.currentTimeMillis()));
            runs.removeIf(value -> value.id().equals(runId));
            runs.add(0, run);
            if (runs.size() > MAX_RUNS) runs = new ArrayList<>(runs.subList(0, MAX_RUNS));
            try {
                if (!preferences.edit().putString(ACTIVE, encode(run).toString())
                        .putString(RESULTS, encodeRuns(runs).toString()).commit()) {
                    throw new IllegalStateException("Battery result could not be saved");
                }
            } catch (JSONException error) { throw new IllegalStateException("Battery result cannot be encoded", error); }
        }
    }

    void clearResults() {
        synchronized (LOCK) { saveResults(List.of()); }
    }

    void reset() {
        synchronized (LOCK) {
            if (!preferences.edit().clear().commit()) throw new IllegalStateException("Battery test data could not be reset");
            BatteryReport.clear(context);
        }
    }

    private BatteryTrial.Run preserveIssue(BatteryTrial.Run run) {
        if (run == null) return null;
        BatteryTrial.Run current = active();
        return run != null && current != null && current.id().equals(run.id())
                ? run.invalidate(current.issue()) : run;
    }

    static void invalidate(Context context, BatteryTrial.Issue issue) {
        if (issue == BatteryTrial.Issue.NONE) return;
        synchronized (LOCK) {
            try {
                BatteryTestStore store = new BatteryTestStore(context);
                BatteryTrial.Run run = store.active();
                if (run != null && run.started() && !run.finished() && run.issue() == BatteryTrial.Issue.NONE) {
                    store.active(run.invalidate(issue));
                    Log.i(HistoryRuntime.LOG_TAG, "event=battery_test operation=" + run.id() + " result=excluded issue=" + issue);
                }
            } catch (RuntimeException error) {
                Log.w(HistoryRuntime.LOG_TAG, "event=battery_test result=invalidation_failed detail=" + error.getClass().getSimpleName());
            }
        }
    }

    String report(long now) {
        synchronized (LOCK) {
            try {
                return new JSONObject().put("schemaVersion", 1).put("exportedAtMs", now)
                        .put("measurement", "explicit battery checkpoints; whole-watch drain; graph setup confirmed by wearer")
                        .put("units", new JSONObject().put("time", "milliseconds").put("charge", "microampere-hours")
                                .put("drain", "battery percentage points per hour"))
                        .put("runs", encodeRuns(results(now))).toString(2);
            } catch (JSONException error) { throw new IllegalStateException("Battery report cannot be encoded", error); }
        }
    }

    private void saveResults(List<BatteryTrial.Run> runs) {
        try {
            if (!preferences.edit().putString(RESULTS, encodeRuns(runs).toString()).commit()) {
                throw new IllegalStateException("Battery results could not be saved");
            }
            BatteryReport.clear(context);
        } catch (JSONException error) { throw new IllegalStateException("Battery results cannot be encoded", error); }
    }

    private static JSONArray encodeRuns(List<BatteryTrial.Run> runs) throws JSONException {
        JSONArray values = new JSONArray();
        for (BatteryTrial.Run run : runs) values.put(encode(run));
        return values;
    }

    private static JSONObject encode(BatteryTrial.Run run) throws JSONException {
        JSONArray readings = new JSONArray();
        for (BatteryTrial.Reading point : run.readings()) {
            readings.put(new JSONObject().put("wallMs", point.wallMs()).put("elapsedMs", point.elapsedMs())
                    .put("bootCount", point.bootCount()).put("percent", point.percent()).put("chargeUah", point.chargeUah())
                    .put("plugged", point.plugged()).put("versionCode", point.versionCode()));
        }
        return new JSONObject().put("id", run.id()).put("mode", run.mode().name())
                .put("previousRecording", run.previousRecording()).put("previousDemo", run.previousDemo())
                .put("createdMs", run.createdMs()).put("configuration", run.configuration()).put("ready", run.ready())
                .put("readings", readings).put("finished", run.finished()).put("issue", run.issue().name());
    }

    private static BatteryTrial.Run decode(JSONObject value) throws JSONException {
        List<BatteryTrial.Reading> readings = new ArrayList<>();
        JSONArray points = value.getJSONArray("readings");
        for (int index = 0; index < points.length(); index++) {
            JSONObject point = points.getJSONObject(index);
            readings.add(new BatteryTrial.Reading(point.getLong("wallMs"), point.getLong("elapsedMs"),
                    point.getInt("bootCount"), point.getInt("percent"), point.getInt("chargeUah"),
                    point.getBoolean("plugged"), point.getLong("versionCode")));
        }
        return new BatteryTrial.Run(value.getString("id"), BatteryTrial.Mode.valueOf(value.getString("mode")),
                value.getBoolean("previousRecording"), value.getBoolean("previousDemo"), value.getLong("createdMs"),
                value.getString("configuration"), value.getBoolean("ready"), readings,
                value.getBoolean("finished"), BatteryTrial.Issue.valueOf(value.getString("issue")));
    }
}
