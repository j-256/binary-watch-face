package dev.j256.binarywatchface.history;

import android.content.ClipData;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.util.AtomicFile;

import androidx.core.content.FileProvider;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

final class BatteryReport {
    private static final String DIRECTORY = "battery-reports";
    private static final String FILENAME_PREFIX = "binary-battery-tests-";

    static Intent intent(Context context) {
        String report = new BatteryTestStore(context).report(System.currentTimeMillis());
        clear(context);
        File directory = new File(context.getCacheDir(), DIRECTORY);
        if (!directory.isDirectory() && !directory.mkdirs()) throw new IllegalStateException("Battery report folder could not be created");
        File file = new File(directory, FILENAME_PREFIX + UUID.randomUUID() + ".json");
        AtomicFile output = new AtomicFile(file);
        FileOutputStream stream = null;
        try {
            stream = output.startWrite();
            stream.write(report.getBytes(StandardCharsets.UTF_8));
            output.finishWrite(stream);
        } catch (IOException error) {
            output.failWrite(stream);
            throw new IllegalStateException("Battery report could not be saved", error);
        }
        Uri uri = FileProvider.getUriForFile(context, context.getPackageName() + ".battery-reports", file);
        Intent share = new Intent(Intent.ACTION_SEND).setType("application/json")
                .putExtra(Intent.EXTRA_SUBJECT, "Binary battery test results")
                .putExtra(Intent.EXTRA_STREAM, uri)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        share.setClipData(ClipData.newRawUri("Battery test results", uri));
        return share;
    }

    static void clear(Context context) {
        File directory = new File(context.getCacheDir(), DIRECTORY);
        File[] files = directory.listFiles();
        if (files == null) return;
        for (File file : files) if (file.getName().startsWith(FILENAME_PREFIX)) new AtomicFile(file).delete();
    }

    private BatteryReport() {}
}
