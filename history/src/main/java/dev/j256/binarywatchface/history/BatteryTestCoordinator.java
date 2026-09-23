package dev.j256.binarywatchface.history;

import android.content.Context;
import android.util.Log;

import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.function.Consumer;

/** Persists a recoverable session before changing the recorder */
final class BatteryTestCoordinator {
    private static final AtomicBoolean BUSY = new AtomicBoolean();
    private static final CopyOnWriteArrayList<Consumer<String>> OBSERVERS = new CopyOnWriteArrayList<>();

    static boolean busy() { return BUSY.get(); }
    static void observe(Consumer<String> observer) { OBSERVERS.addIfAbsent(observer); }
    static void stopObserving(Consumer<String> observer) { OBSERVERS.remove(observer); }

    static void prepare(Context context, BatteryTrial.Mode mode, Consumer<String> complete) {
        operate(context, complete, (app, store, done) -> {
            BatteryTrial.Run run = store.active();
            if (run == null) {
                HistorySettings settings = new HistorySettings(app);
                run = new BatteryTrial.Run(UUID.randomUUID().toString(), mode, settings.recording(), settings.demo(),
                        System.currentTimeMillis(), BatteryReader.configuration(app), false, List.of(), false, BatteryTrial.Issue.NONE);
                store.active(run);
            }
            if (run.started() || run.finished()) throw new IllegalStateException("Finish the existing run first");
            BatteryTrial.Run pending = run;
            changeMode(app, run.mode().recording, run.mode().demo(), () -> HistoryRuntime.IO.execute(() -> {
                try {
                    if (!matches(app, pending.mode().recording, pending.mode().demo())) {
                        throw new IllegalStateException("Recording mode could not be applied. Check permissions or retry setup.");
                    }
                    store.active(pending.prepared(BatteryReader.configuration(app)));
                    log("ready", pending);
                    done.accept(null);
                } catch (RuntimeException error) { done.accept(error.getMessage()); }
            }));
        });
    }

    static void start(Context context, Consumer<String> complete) {
        operate(context, complete, (app, store, done) -> {
            BatteryTrial.Run run = requireActive(store);
            if (run.started() || !run.ready()) throw new IllegalStateException("Apply the recording mode before starting");
            if (!matches(app, run.mode().recording, run.mode().demo())) throw new IllegalStateException("Recording mode changed. Cancel and set up again.");
            if (run.mode() == BatteryTrial.Mode.BOTH) {
                try (HistoryStore history = new HistoryStore(app)) {
                    HistorySeries series = history.read(new HistorySettings(app).span(), System.currentTimeMillis());
                    if (series.sampleCount < 2 || series.isStale()) {
                        throw new IllegalStateException("Wait for recent readings to populate the graph before starting this mode");
                    }
                }
            }
            BatteryTrial.Reading reading = BatteryReader.read(app);
            if (!reading.available()) throw new IllegalStateException("Battery level or restart information is unavailable on this watch");
            if (reading.plugged()) throw new IllegalStateException("Unplug the watch before starting");
            BatteryTrial.Run started = run.prepared(BatteryReader.configuration(app)).observe(reading, false, true);
            store.active(started);
            log("started", started);
            done.accept(null);
        });
    }

    static void checkpoint(Context context, Consumer<String> complete) {
        operate(context, complete, (app, store, done) -> {
            BatteryTrial.Run run = requireActive(store);
            if (!run.started() || run.finished()) throw new IllegalStateException("There is no running test");
            store.active(observe(app, run, false, true));
            done.accept(null);
        });
    }

    static void finish(Context context, boolean uninterrupted, Consumer<String> complete) {
        operate(context, complete, (app, store, done) -> {
            BatteryTrial.Run run = requireActive(store);
            if (!run.started()) throw new IllegalStateException("There is no running test");
            if (!run.finished()) {
                run = observe(app, run, true, uninterrupted);
                store.finish(run);
                log("finished", run);
            }
            restore(app, store, run, done);
        });
    }

    static void cancel(Context context, Consumer<String> complete) {
        operate(context, complete, (app, store, done) -> {
            BatteryTrial.Run run = requireActive(store);
            if (run.started() && !run.finished()) {
                run = observe(app, run, true, false);
                store.finish(run);
            }
            restore(app, store, run, done);
        });
    }

    private static BatteryTrial.Run observe(Context context, BatteryTrial.Run run, boolean finish, boolean uninterrupted) {
        if (!run.configuration().equals(BatteryReader.configuration(context))) run = run.invalidate(BatteryTrial.Issue.SETTINGS_CHANGED);
        if (!matches(context, run.mode().recording, run.mode().demo())) run = run.invalidate(BatteryTrial.Issue.RECORDING_FAILED);
        return run.observe(BatteryReader.read(context), finish, uninterrupted);
    }

    private static void restore(Context app, BatteryTestStore store, BatteryTrial.Run run, Consumer<String> done) {
        changeMode(app, run.previousRecording(), run.previousDemo(), () -> HistoryRuntime.IO.execute(() -> {
            try {
                if (!matches(app, run.previousRecording(), run.previousDemo())) {
                    throw new IllegalStateException("Your previous recording mode could not be restored. Retry restore after checking permissions.");
                }
                store.active(null);
                log("restored", run);
                done.accept(null);
            } catch (RuntimeException error) { done.accept(error.getMessage()); }
        }));
    }

    private static void changeMode(Context context, boolean recording, boolean demo, Runnable complete) {
        if (recording) HistoryRuntime.start(context, complete);
        else if (demo) HistoryRuntime.stop(context, true, complete);
        else HistoryRuntime.pause(context, complete);
    }

    static boolean matches(Context context, boolean recording, boolean demo) {
        HistorySettings settings = new HistorySettings(context);
        return settings.recording() == recording && settings.demo() == demo
                && (recording ? HistorySettings.hasPermissions(context) && HistorySettings.STATUS_RECORDING.equals(settings.status())
                : HistorySettings.STATUS_PAUSED.equals(settings.status()));
    }

    private static BatteryTrial.Run requireActive(BatteryTestStore store) {
        BatteryTrial.Run run = store.active();
        if (run == null) throw new IllegalStateException("There is no battery test to update");
        return run;
    }

    private interface Operation {
        void run(Context app, BatteryTestStore store, Consumer<String> complete);
    }

    private static void operate(Context context, Consumer<String> complete, Operation operation) {
        if (!BUSY.compareAndSet(false, true)) { complete.accept("A recording change is still in progress"); return; }
        Context app = context.getApplicationContext();
        Consumer<String> done = error -> {
            BUSY.set(false);
            if (error != null) Log.w(HistoryRuntime.LOG_TAG, "event=battery_test result=failed detail=" + error);
            complete.accept(error);
            for (Consumer<String> observer : OBSERVERS) if (observer != complete) observer.accept(error);
        };
        HistoryRuntime.IO.execute(() -> {
            try { operation.run(app, new BatteryTestStore(app), done); }
            catch (RuntimeException error) { done.accept(error.getMessage()); }
        });
    }

    private static void log(String event, BatteryTrial.Run run) {
        Log.i(HistoryRuntime.LOG_TAG, "event=battery_test operation=" + run.id() + " result=" + event
                + " mode=" + run.mode() + " issue=" + run.issue());
    }

    private BatteryTestCoordinator() {}
}
