package dev.j256.binarywatchface.history;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.database.sqlite.SQLiteStatement;

import java.util.List;

/** Private history with at most one value per second and a one-day lifetime */
public final class HistoryStore extends SQLiteOpenHelper {
    private static final String DATABASE = "heart-history.db";
    private static final int VERSION = 1;

    public HistoryStore(Context context) {
        super(context.getApplicationContext(), DATABASE, null, VERSION);
    }

    @Override public void onCreate(SQLiteDatabase database) {
        database.execSQL("CREATE TABLE samples (time INTEGER PRIMARY KEY, sample_time INTEGER NOT NULL, bpm REAL NOT NULL)");
    }

    @Override public void onUpgrade(SQLiteDatabase database, int oldVersion, int newVersion) {
        throw new IllegalStateException("Unsupported history database version");
    }

    public int append(List<HistorySeries.Sample> samples, long nowMs) {
        SQLiteDatabase database = getWritableDatabase();
        int accepted = 0;
        database.beginTransaction();
        try (SQLiteStatement insert = database.compileStatement(
                "INSERT INTO samples(time, sample_time, bpm) VALUES (?, ?, ?) "
                + "ON CONFLICT(time) DO UPDATE SET sample_time=excluded.sample_time, bpm=excluded.bpm "
                + "WHERE excluded.sample_time >= samples.sample_time")) {
            for (HistorySeries.Sample sample : samples) {
                if (!HistorySeries.valid(sample, nowMs)) continue;
                insert.bindLong(1, sample.timeMs() / HistorySeries.SECOND_MS * HistorySeries.SECOND_MS);
                insert.bindLong(2, sample.timeMs());
                insert.bindDouble(3, sample.bpm());
                insert.execute();
                accepted++;
            }
            prune(database, nowMs);
            database.setTransactionSuccessful();
        } finally {
            database.endTransaction();
        }
        return accepted;
    }

    public HistorySeries read(HistorySeries.Span span, long nowMs) {
        SQLiteDatabase database = getWritableDatabase();
        prune(database, nowMs);
        HistorySeries result = new HistorySeries(span, nowMs);
        try (Cursor cursor = database.query("samples", new String[]{"sample_time", "bpm"},
                "sample_time >= ? AND sample_time <= ?", new String[]{Long.toString(result.startMs), Long.toString(nowMs)},
                null, null, "time ASC")) {
            while (cursor.moveToNext()) result.add(new HistorySeries.Sample(cursor.getLong(0), cursor.getDouble(1)));
        }
        return result;
    }

    public void clear() {
        getWritableDatabase().delete("samples", null, null);
    }

    public void prune(long nowMs) {
        prune(getWritableDatabase(), nowMs);
    }

    private void prune(SQLiteDatabase database, long nowMs) {
        database.delete("samples", "sample_time < ? OR sample_time > ?",
                new String[]{Long.toString(nowMs - HistorySeries.RETENTION_MS), Long.toString(nowMs)});
    }
}
