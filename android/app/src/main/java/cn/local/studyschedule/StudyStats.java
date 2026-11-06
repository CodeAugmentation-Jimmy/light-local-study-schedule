package cn.local.studyschedule;

import org.json.JSONObject;
import java.time.LocalDate;
import java.util.List;

/** Statistics are derived from the same merged counters shown on the desktop. */
public final class StudyStats {
    public final double[] days = new double[7];
    public double total;
    public int studiedDays, streak;

    public StudyStats(List<JSONObject> items, LocalDate today) {
        for (int i = 0; i < 7; i++) {
            days[i] = dayTotal(items, today.minusDays(6 - i));
            total += days[i];
            if (days[i] > 0) studiedDays++;
        }
        LocalDate cursor = dayTotal(items, today) > 0 ? today : today.minusDays(1);
        while (dayTotal(items, cursor) > 0) { streak++; cursor = cursor.minusDays(1); }
    }

    private static double dayTotal(List<JSONObject> items, LocalDate day) {
        double total = 0;
        for (JSONObject item : items) total += StudyStore.seconds(item, day.toString());
        return total;
    }
}
