package cn.local.studyschedule;

import java.time.LocalDate;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

public final class CourseSchedule {
    public static final String[] MODES = {"daily", "odd", "even", "weekdays"};
    public static final String[] LABELS = {"每天", "单数日", "双数日", "指定星期"};
    public static final String[] DAYS = {"周一", "周二", "周三", "周四", "周五", "周六", "周日"};

    public static JSONObject daily() throws JSONException { return new JSONObject().put("mode", "daily"); }
    public static void validate(JSONObject rule) throws JSONException {
        String mode = rule.getString("mode");
        if (mode.equals("weekdays")) {
            JSONArray days = rule.getJSONArray("days");
            if (rule.length() != 2 || days.length() == 0 || days.length() > 7) throw new JSONException("请选择至少一个星期");
            int previous = 0;
            for (int i = 0; i < days.length(); i++) {
                Object value = days.get(i);
                if (!(value instanceof Integer) && !(value instanceof Long)) throw new JSONException("星期格式有误");
                double day = ((Number) value).doubleValue();
                if (day != Math.floor(day) || day <= previous || day > 7) throw new JSONException("星期须为 1 至 7 且升序不重复");
                previous = (int) day;
            }
        } else if ((!mode.equals("daily") && !mode.equals("odd") && !mode.equals("even")) || rule.length() != 1) {
            throw new JSONException("课程安排类型有误");
        }
    }
    public static boolean isDue(JSONObject item, LocalDate day) {
        JSONObject rule = item.optJSONObject("schedule");
        if (rule == null) return true; // Existing local courses default to daily during upgrade.
        switch (rule.optString("mode")) {
            case "daily": return true;
            case "odd": return day.getDayOfMonth() % 2 == 1;
            case "even": return day.getDayOfMonth() % 2 == 0;
            case "weekdays":
                JSONArray days = rule.optJSONArray("days");
                for (int i = 0; i < days.length(); i++) if (days.optInt(i) == day.getDayOfWeek().getValue()) return true;
                return false;
            default: return false;
        }
    }
    public static String label(JSONObject item) {
        JSONObject rule = item.optJSONObject("schedule");
        if (rule == null) return "每天";
        if (rule.optString("mode").equals("weekdays")) {
            StringBuilder text = new StringBuilder(); JSONArray days = rule.optJSONArray("days");
            for (int i = 0; i < days.length(); i++) {
                if (i > 0) text.append("、"); text.append(DAYS[days.optInt(i) - 1]);
            }
            return text.toString();
        }
        for (int i = 0; i < MODES.length; i++) if (MODES[i].equals(rule.optString("mode"))) return LABELS[i];
        return "未知安排";
    }
    public static LocalDate nextDate(JSONObject item, LocalDate start) {
        for (int i = 0; i < 8; i++) if (isDue(item, start.plusDays(i))) return start.plusDays(i);
        throw new IllegalArgumentException("课程安排无效");
    }
}
