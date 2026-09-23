package dev.j256.binarywatchface.history;

import android.app.Activity;
import android.os.SystemClock;
import android.view.InputDevice;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.inspector.WindowInspector;
import android.widget.Button;
import android.widget.ListView;
import android.widget.ScrollView;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Predicate;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class HistoryControlsTest {
    private static final long UI_TIMEOUT_MS = 5_000;

    @Test public void crownScrollsSettingsBeforeTouchAndAfterChangingASettingOrRecreating() {
        InstrumentationRegistry.getInstrumentation().setInTouchMode(true);
        try (ActivityScenario<HistoryActivity> scenario = ActivityScenario.launch(HistoryActivity.class)) {
            await(scenario, activity -> button(activity, "Settings") != null);
            scenario.onActivity(activity -> button(activity, "Settings").performClick());
            await(scenario, HistoryControlsTest::scrollReady);
            scenario.onActivity(this::scrollBothWays);
            AtomicReference<ScrollView> previous = new AtomicReference<>();
            scenario.onActivity(activity -> {
                previous.set(scroll(activity));
                button(activity, "6 hours").performClick();
            });
            await(scenario, activity -> scrollReady(activity) && scroll(activity) != previous.get());
            scenario.onActivity(this::scrollBothWays);
            scenario.recreate();
            await(scenario, HistoryControlsTest::scrollReady);
            scenario.onActivity(this::scrollBothWays);
        }
    }

    @Test public void crownScrollsBatterySetupAndResultsAfterNavigation() {
        InstrumentationRegistry.getInstrumentation().setInTouchMode(true);
        try (ActivityScenario<BatteryTestActivity> scenario = ActivityScenario.launch(BatteryTestActivity.class)) {
            await(scenario, HistoryControlsTest::scrollReady);
            scenario.onActivity(activity -> {
                scrollBothWays(activity);
                button(activity, "Results").performClick();
            });
            await(scenario, activity -> scrollReady(activity) && button(activity, "Back to test") != null);
            scenario.onActivity(activity -> {
                scrollBothWays(activity);
                button(activity, "Back to test").performClick();
            });
            await(scenario, activity -> scrollReady(activity) && button(activity, "Results") != null);
            scenario.onActivity(this::scrollBothWays);
        }
    }

    @Test public void crownScrollsTheModeDialogAndReturnsToTheScreenAfterSelection() {
        InstrumentationRegistry.getInstrumentation().setInTouchMode(true);
        try (ActivityScenario<BatteryTestActivity> scenario = ActivityScenario.launch(BatteryTestActivity.class)) {
            await(scenario, HistoryControlsTest::scrollReady);
            scenario.onActivity(activity -> button(activity, "Baseline").performClick());
            await(scenario, activity -> choices() != null && choices().canScrollVertically(1));
            scenario.onActivity(activity -> {
                ListView list = choices();
                int screenOffset = scroll(activity).getScrollY();
                int first = list.getFirstVisiblePosition();
                int top = list.getChildAt(0).getTop();
                rotate(list.getRootView(), -2);
                assertTrue("The crown must scroll the open dialog", list.getFirstVisiblePosition() > first
                        || list.getChildAt(0).getTop() < top);
                assertEquals("The screen behind the dialog must stay still", screenOffset, scroll(activity).getScrollY());
                list.performItemClick(null, BatteryTrial.Mode.GRAPH.ordinal(), BatteryTrial.Mode.GRAPH.ordinal());
            });
            await(scenario, activity -> choices() == null && scrollReady(activity) && button(activity, "Graph only") != null);
            scenario.onActivity(this::scrollBothWays);
        }
    }

    private void scrollBothWays(Activity activity) {
        ScrollView scroll = scroll(activity);
        scroll.scrollTo(0, 0);
        rotate(activity.getWindow().getDecorView(), -3);
        assertTrue("Turning the crown must scroll the displayed screen", scroll.getScrollY() > 0);
        int afterDown = scroll.getScrollY();
        rotate(activity.getWindow().getDecorView(), 1);
        assertTrue("Reversing the crown must scroll back", scroll.getScrollY() < afterDown);
    }

    private static void rotate(View root, float ticks) {
        MotionEvent.PointerProperties pointer = new MotionEvent.PointerProperties();
        pointer.id = 0;
        MotionEvent.PointerCoords coordinates = new MotionEvent.PointerCoords();
        coordinates.setAxisValue(MotionEvent.AXIS_SCROLL, ticks);
        long time = SystemClock.uptimeMillis();
        MotionEvent event = MotionEvent.obtain(time, time, MotionEvent.ACTION_SCROLL, 1,
                new MotionEvent.PointerProperties[]{pointer}, new MotionEvent.PointerCoords[]{coordinates},
                0, 0, 1, 1, 0, 0, InputDevice.SOURCE_ROTARY_ENCODER, 0);
        try { root.dispatchGenericMotionEvent(event); }
        finally { event.recycle(); }
    }

    private static boolean scrollReady(Activity activity) {
        ScrollView scroll = scroll(activity);
        return scroll != null && scroll.isLaidOut() && scroll.getChildAt(0).getHeight() > scroll.getHeight();
    }

    private static ScrollView scroll(Activity activity) {
        return (ScrollView) find(activity.getWindow().getDecorView(), view -> view instanceof ScrollView);
    }

    private static ListView choices() {
        for (View root : WindowInspector.getGlobalWindowViews()) {
            View list = find(root, view -> view instanceof ListView);
            if (list != null && list.isShown()) return (ListView) list;
        }
        return null;
    }

    private static Button button(Activity activity, String label) {
        return (Button) find(activity.getWindow().getDecorView(), view ->
                view instanceof Button button && label.contentEquals(button.getText()));
    }

    private static View find(View view, Predicate<View> match) {
        if (match.test(view)) return view;
        if (view instanceof ViewGroup group) for (int index = 0; index < group.getChildCount(); index++) {
            View found = find(group.getChildAt(index), match);
            if (found != null) return found;
        }
        return null;
    }

    private static <T extends Activity> void await(ActivityScenario<T> scenario, Predicate<T> ready) {
        long deadline = SystemClock.uptimeMillis() + UI_TIMEOUT_MS;
        AtomicBoolean satisfied = new AtomicBoolean();
        do {
            scenario.onActivity(activity -> satisfied.set(ready.test(activity)));
            if (satisfied.get()) return;
            SystemClock.sleep(20);
        } while (SystemClock.uptimeMillis() < deadline);
        fail("Screen did not become ready");
    }
}
