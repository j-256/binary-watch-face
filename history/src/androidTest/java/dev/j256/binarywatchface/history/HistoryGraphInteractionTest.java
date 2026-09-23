package dev.j256.binarywatchface.history;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.os.SystemClock;
import android.view.MotionEvent;
import android.view.View;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Test;
import org.junit.runner.RunWith;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class HistoryGraphInteractionTest {
    @Test public void cursorFollowsTheTouchAndDisappearsOnReleaseCancellationOrFocusLoss() {
        try (ActivityScenario<HistoryActivity> scenario = ActivityScenario.launch(HistoryActivity.class)) {
            scenario.onActivity(activity -> {
                HistoryGraphView graph = new HistoryGraphView(activity,
                        HistorySeries.demo(HistorySeries.Span.HOUR, System.currentTimeMillis()), true);
                activity.setContentView(graph);
                int width = 454;
                int height = 314;
                graph.measure(View.MeasureSpec.makeMeasureSpec(width, View.MeasureSpec.EXACTLY),
                        View.MeasureSpec.makeMeasureSpec(height, View.MeasureSpec.EXACTLY));
                graph.layout(0, 0, width, height);
                Bitmap resting = draw(graph);
                touch(graph, MotionEvent.ACTION_DOWN, 140, 160);
                Bitmap held = draw(graph);
                assertFalse(resting.sameAs(held));
                touch(graph, MotionEvent.ACTION_MOVE, 310, 160);
                assertFalse(held.sameAs(draw(graph)));
                touch(graph, MotionEvent.ACTION_UP, 310, 160);
                assertTrue(resting.sameAs(draw(graph)));
                touch(graph, MotionEvent.ACTION_DOWN, 140, 160);
                touch(graph, MotionEvent.ACTION_CANCEL, 140, 160);
                assertTrue(resting.sameAs(draw(graph)));
                touch(graph, MotionEvent.ACTION_DOWN, 140, 160);
                graph.onWindowFocusChanged(false);
                assertTrue(resting.sameAs(draw(graph)));
                touch(graph, MotionEvent.ACTION_DOWN, 140, 160);
                graph.setVisibility(View.INVISIBLE);
                graph.setVisibility(View.VISIBLE);
                assertTrue(resting.sameAs(draw(graph)));
            });
        }
    }

    private Bitmap draw(View view) {
        Bitmap bitmap = Bitmap.createBitmap(view.getWidth(), view.getHeight(), Bitmap.Config.ARGB_8888);
        view.draw(new Canvas(bitmap));
        return bitmap;
    }

    private void touch(View view, int action, float x, float y) {
        long time = SystemClock.uptimeMillis();
        MotionEvent event = MotionEvent.obtain(time, time, action, x, y, 0);
        assertTrue(view.dispatchTouchEvent(event));
        event.recycle();
    }
}
