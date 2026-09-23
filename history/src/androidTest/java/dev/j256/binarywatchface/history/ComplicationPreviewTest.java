package dev.j256.binarywatchface.history;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.wear.watchface.complications.data.ComplicationType;
import androidx.wear.watchface.complications.data.TimeRange;

import org.junit.Test;
import org.junit.runner.RunWith;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class ComplicationPreviewTest {
    @Test public void pickerPreviewHasTheRequiredUnrestrictedValidity() {
        HeartHistoryComplication provider = new HeartHistoryComplication();
        var preview = provider.getPreviewData(ComplicationType.PHOTO_IMAGE);
        assertNotNull(preview);
        assertEquals(TimeRange.ALWAYS, preview.getValidTimeRange());
        assertNull(preview.getTapAction());
        assertNull(provider.getPreviewData(ComplicationType.SHORT_TEXT));
    }
}
