package cn.local.studyschedule;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Insets;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import android.widget.Switch;
import android.widget.CheckBox;
import android.widget.Spinner;
import android.widget.ArrayAdapter;
import android.widget.AdapterView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.time.LocalDateTime;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private final int BLUE = Color.rgb(37, 99, 235), MUTED = Color.rgb(100, 116, 139);
    private StudyStore store;
    private LinearLayout content, categories;
    private TextView focus, timer, remaining, summary, empty, timerOptions;
    private ProgressBar overall;
    private Button start, pause, stop;
    private String selected = "", rendered = "";
    private final Map<String, TextView> details = new HashMap<>();
    private final Map<String, LinearLayout> cards = new HashMap<>();
    private final Map<String, ProgressBar> bars = new HashMap<>();
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private boolean syncing;
    private boolean showAllCourses;
    private final Runnable ticker = new Runnable() {
        @Override public void run() {
            refresh(); handler.postDelayed(this, 1000);
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        try { store = StudyStore.get(this); }
        catch (Exception e) {
            new AlertDialog.Builder(this).setTitle("无法读取记录").setMessage(e.getMessage()).setPositiveButton("关闭", (d, w) -> finish()).setCancelable(false).show();
            return;
        }
        if (state != null) { selected = state.getString("selected", ""); showAllCourses = state.getBoolean("showAllCourses", false); }
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(243, 246, 252));
        content = column(); content.setPadding(dp(18), dp(18), dp(18), dp(24));
        scroll.addView(content);
        setContentView(scroll);
        if (Build.VERSION.SDK_INT >= 30) getWindow().setDecorFitsSystemWindows(false);
        scroll.setOnApplyWindowInsetsListener((v, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                Insets safe = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                scroll.setPadding(safe.left, safe.top, safe.right, safe.bottom);
            } else scroll.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(), insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });
        TextView title = text("学习日程", 28, Color.rgb(15, 23, 42)); title.setTypeface(null, Typeface.BOLD);
        content.addView(title);
        content.addView(text("把时间留给今天想学的事", 14, MUTED));

        LinearLayout hero = card(); content.addView(hero, spaced());
        focus = text("准备开始", 16, MUTED); hero.addView(focus);
        timer = text("00:00:00", 40, BLUE); timer.setTypeface(Typeface.MONOSPACE, Typeface.BOLD); hero.addView(timer);
        remaining = text("选择类目后开始计时", 14, MUTED); hero.addView(remaining);
        LinearLayout controls = row(); hero.addView(controls);
        start = button("开始", () -> {
            if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 10);
            sendTimer("START", selected);
        });
        pause = button("暂停", () -> sendTimer("PAUSE", ""));
        stop = button("停止", () -> sendTimer("STOP", ""));
        addWeighted(controls, start); addWeighted(controls, pause); addWeighted(controls, stop);
        Switch background = new Switch(this);
        background.setText("后台继续计时"); background.setTextSize(15);
        background.setPadding(0, dp(12), 0, dp(8));
        background.setChecked(store.backgroundEnabled()); hero.addView(background);
        background.setOnCheckedChangeListener((view, checked) -> {
            try { store.setBackgroundEnabled(checked); refresh(); }
            catch (Exception e) { error(e); }
        });
        timerOptions = text("", 12, MUTED); hero.addView(timerOptions);
        hero.addView(button("专注与屏幕设置", this::timerSettings));

        LinearLayout totals = card(); content.addView(totals, spaced());
        totals.addView(text("今日总览", 17, Color.rgb(15, 23, 42)));
        summary = text("", 14, MUTED); totals.addView(summary);
        overall = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal); overall.setMax(1000); totals.addView(overall);

        LinearLayout actions = row(); content.addView(actions, spaced());
        addWeighted(actions, button("添加类目", () -> editItem(null)));
        addWeighted(actions, button("历史记录", this::history));
        addWeighted(actions, button("局域网同步", this::syncDialog));
        content.addView(button("近 7 天统计与连续学习", this::statistics));
        LinearLayout calendarActions = row(); content.addView(calendarActions);
        addWeighted(calendarActions, button("未来 14 天课程表", this::calendar));
        Switch allCourses = new Switch(this); allCourses.setText("全部课程"); allCourses.setChecked(showAllCourses);
        addWeighted(calendarActions, allCourses);
        allCourses.setOnCheckedChangeListener((view, checked) -> { showAllCourses = checked; refresh(); });
        content.addView(text("今日课程 · 按系统日历自动切换", 17, Color.rgb(15, 23, 42)));
        categories = column(); content.addView(categories);
        empty = text("还没有学习类目，点击“添加类目”设置每日目标。", 15, MUTED); categories.addView(empty);
        LinearLayout editActions = row(); content.addView(editActions, spaced());
        addWeighted(editActions, button("修改选中类目", () -> {
            JSONObject item = selectedItem(); if (item != null) editItem(item);
        }));
        addWeighted(editActions, button("删除选中类目", this::deleteSelected));
        content.addView(text("离线可用 · 暂停不计时 · 两端分别计时，同步时合并记录", 12, MUTED));
        refresh();
    }

    private int dp(int value) { return (int) (getResources().getDisplayMetrics().density * value + .5f); }
    private LinearLayout column() { LinearLayout v = new LinearLayout(this); v.setOrientation(LinearLayout.VERTICAL); return v; }
    private LinearLayout row() { LinearLayout v = new LinearLayout(this); v.setOrientation(LinearLayout.HORIZONTAL); return v; }
    private TextView text(String value, int size, int color) {
        TextView v = new TextView(this); v.setText(value); v.setTextSize(size); v.setTextColor(color); v.setPadding(0, dp(4), 0, dp(4)); return v;
    }
    private GradientDrawable background(int fill, int border) {
        GradientDrawable drawable = new GradientDrawable(); drawable.setColor(fill); drawable.setCornerRadius(dp(16)); drawable.setStroke(dp(1), border); return drawable;
    }
    private LinearLayout card() {
        LinearLayout view = column(); view.setPadding(dp(16), dp(12), dp(16), dp(12));
        view.setBackground(background(Color.WHITE, Color.rgb(226, 232, 240))); return view;
    }
    private LinearLayout.LayoutParams spaced() {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, -2); p.topMargin = dp(14); p.bottomMargin = dp(4); return p;
    }
    private Button button(String title, Runnable action) {
        Button button = new Button(this); button.setText(title); button.setTextSize(13); button.setAllCaps(false); button.setMinWidth(0); button.setMinimumWidth(0);
        button.setOnClickListener(v -> action.run()); return button;
    }
    private void addWeighted(LinearLayout row, View view) { row.addView(view, new LinearLayout.LayoutParams(0, -2, 1)); }
    private void error(Exception e) { Toast.makeText(this, e.getMessage() == null ? "操作失败" : e.getMessage(), Toast.LENGTH_LONG).show(); }
    private JSONObject selectedItem() {
        for (JSONObject item : store.items()) if (item.optString("id").equals(selected)) return item;
        Toast.makeText(this, "请先点击一个学习类目", Toast.LENGTH_SHORT).show(); return null;
    }
    private void sendTimer(String action, String id) {
        try {
            if (action.equals("START") && selectedItem() == null) return;
            // A recovered paused session may not have a live service yet.
            Intent intent = new Intent(this, TimerService.class).setAction(action).putExtra("id", id);
            startForegroundService(intent);
            handler.postDelayed(this::refresh, 150);
        } catch (Exception e) { error(e); }
    }

    private void refresh() {
        if (store == null || categories == null) return;
        LocalDate today = StudyStore.currentDate();
        List<JSONObject> allItems = store.items();
        List<JSONObject> items = new ArrayList<>();
        for (JSONObject item : allItems) if (showAllCourses || CourseSchedule.isDue(item, today)) items.add(item);
        if (items.stream().noneMatch(item -> item.optString("id").equals(selected))) selected = items.isEmpty() ? "" : items.get(0).optString("id");
        StringBuilder signature = new StringBuilder(today.toString() + showAllCourses);
        for (JSONObject item : items) signature.append(item.optString("id")).append(':').append(item.optString("name")).append(':').append(item.optInt("goal")).append(':').append(item.optJSONObject("schedule")).append('\n');
        if (!signature.toString().equals(rendered)) {
            categories.removeAllViews(); details.clear(); cards.clear(); bars.clear();
            rendered = signature.toString();
            for (JSONObject item : items) {
                String id = item.optString("id");
                LinearLayout card = card();
                TextView name = text(item.optString("name"), 18, Color.rgb(15, 23, 42)); name.setTypeface(null, Typeface.BOLD); card.addView(name);
                TextView detail = text("", 13, MUTED); card.addView(detail);
                ProgressBar bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal); bar.setMax(1000); card.addView(bar);
                card.setOnClickListener(v -> { selected = id; refresh(); });
                card.setContentDescription("学习类目 " + item.optString("name"));
                categories.addView(card, spaced()); details.put(id, detail); cards.put(id, card); bars.put(id, bar);
            }
            if (items.isEmpty()) {
                empty.setText(allItems.isEmpty() ? "还没有课程，点击“添加类目”设置课程与目标。" : "今天没有课程安排，可以休息。打开“全部课程”可管理其他日期的课程。");
                categories.addView(empty);
            }
        }
        double total = 0, goalTotal = 0, credited = 0;
        int completed = 0, dueCount = 0;
        JSONObject current = null;
        for (JSONObject item : allItems) {
            String id = item.optString("id");
            double done = StudyStore.seconds(item, StudyStore.today()), goal = item.optInt("goal") * 60.0;
            boolean due = CourseSchedule.isDue(item, today);
            total += done;
            if (due) { dueCount++; goalTotal += goal; credited += Math.min(done, goal); if (done >= goal) completed++; }
            if (id.equals(store.activeId())) current = item;
            if (!details.containsKey(id)) continue;
            String status = done >= goal ? "已完成" : "未完成";
            if (!due) status = "今天未安排 · 下次 " + CourseSchedule.nextDate(item, today);
            if (id.equals(store.activeId())) status += store.isPaused() ? " · 已暂停" : " · 计时中";
            details.get(id).setText(CourseSchedule.label(item) + " · 目标 " + item.optInt("goal") + " 分钟\n今日已学 " + StudyStore.duration(done) + " · " + status);
            bars.get(id).setProgress((int) (Math.min(done / goal, 1) * 1000));
            cards.get(id).setAlpha(due ? 1f : .65f);
            cards.get(id).setBackground(background(id.equals(selected) ? Color.rgb(239, 246, 255) : Color.WHITE, id.equals(selected) ? BLUE : Color.rgb(226, 232, 240)));
        }
        double ratio = goalTotal == 0 ? 0 : credited / goalTotal;
        summary.setText(today + " " + CourseSchedule.DAYS[today.getDayOfWeek().getValue() - 1] + (today.getDayOfMonth() % 2 == 1 ? " · 单数日" : " · 双数日")
                + "\n累计 " + StudyStore.duration(total) + " · 完成 " + completed + "/" + dueCount + " 门今日课程 · " + Math.round(ratio * 100) + "%");
        overall.setProgress((int) (ratio * 1000));
        timer.setText(StudyStore.duration(store.sessionSeconds()));
        timerOptions.setText((store.backgroundEnabled() ? "开启：切换应用或锁屏后继续计时" : "关闭：离开应用自动暂停，回来手动继续")
                + "\n" + (store.focusMinutes() == 0 ? "自由计时 · 手动启停" : "每轮专注 " + store.focusMinutes() + " 分钟 · 到时自动暂停"));
        if (store.setting("keepScreen").equals("true") && !store.activeId().isEmpty() && !store.isPaused())
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        if (current == null) {
            focus.setText("准备开始 · 本次专注"); remaining.setText("选中一个学习类目，然后点击开始。");
        } else {
            focus.setText((store.isPaused() ? "已暂停 · " : "正在学习 · ") + current.optString("name"));
            double left = Math.max(0, current.optInt("goal") * 60.0 - StudyStore.seconds(current, StudyStore.today()));
            remaining.setText(left == 0 ? "今日目标已完成，由你手动停止计时。" : "距离今日目标还需 " + StudyStore.duration(Math.ceil(left)));
            if (!CourseSchedule.isDue(current, today)) remaining.setText("今天未安排此课程，请停止后选择今日课程。");
            if (store.isPaused()) remaining.append("\n" + store.pauseReason());
            else if (store.focusMinutes() > 0) remaining.append("\n本轮剩余 " + StudyStore.duration(Math.ceil(store.focusRemaining())));
        }
        start.setEnabled(store.activeId().isEmpty() && items.stream().anyMatch(item -> item.optString("id").equals(selected) && CourseSchedule.isDue(item, today)));
        pause.setEnabled(current != null && (!store.isPaused() || CourseSchedule.isDue(current, today)));
        stop.setEnabled(!store.activeId().isEmpty()); pause.setText(store.isPaused() ? "继续" : "暂停");
    }

    private void timerSettings() {
        LinearLayout form = column(); form.setPadding(dp(20), dp(8), dp(20), 0);
        form.addView(text("专注时长：达到后自动暂停，休息不计入学习；继续后开启下一轮。0 表示自由计时。修改后从当前时刻重新计算一轮。", 14, MUTED));
        EditText minutes = new EditText(this); minutes.setInputType(InputType.TYPE_CLASS_NUMBER);
        minutes.setHint("0 至 180 分钟"); minutes.setText(String.valueOf(store.focusMinutes())); form.addView(minutes);
        LinearLayout presets = row(); form.addView(presets);
        for (int value : new int[]{0, 25, 45, 60}) addWeighted(presets, button(value == 0 ? "自由" : value + "分", () -> minutes.setText(String.valueOf(value))));
        Switch screen = new Switch(this); screen.setText("计时时保持屏幕亮起");
        screen.setChecked(store.setting("keepScreen").equals("true")); form.addView(screen);
        form.addView(text("仅在应用可见且计时进行时保持亮屏。后台开关、专注时长和亮屏设置只作用于本手机。", 12, MUTED));
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("专注与屏幕设置").setView(form)
                .setPositiveButton("保存", null).setNegativeButton("取消", null).create();
        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            try {
                int value;
                try { value = Integer.parseInt(minutes.getText().toString().trim()); }
                catch (NumberFormatException e) { throw new IllegalArgumentException("请输入 0 至 180 的整数分钟数"); }
                if (value != store.focusMinutes()) store.setFocusMinutes(value);
                store.setting("keepScreen", String.valueOf(screen.isChecked()));
                refresh(); dialog.dismiss();
            } catch (Exception e) { error(e); }
        })); dialog.show();
    }

    private void statistics() {
        List<JSONObject> items = store.items();
        LocalDate today = LocalDate.now(); StudyStats stats = new StudyStats(items, today);
        ScrollView scroll = new ScrollView(this); LinearLayout rows = column();
        rows.setPadding(dp(20), dp(8), dp(20), dp(12)); scroll.addView(rows);
        rows.addView(text("近 7 天共 " + StudyStore.duration(stats.total), 20, BLUE));
        rows.addView(text("学习 " + stats.studiedDays + "/7 天 · 连续学习 " + stats.streak + " 天", 15, MUTED));
        rows.addView(text("有学习时长即计为学习日；今天尚未学习时，连续天数统计截至昨天。", 12, MUTED));
        double maximum = 1; for (double value : stats.days) maximum = Math.max(maximum, value);
        for (int i = 0; i < 7; i++) {
            rows.addView(text(today.minusDays(6 - i).toString() + "    " + StudyStore.duration(stats.days[i]), 14, MUTED));
            ProgressBar bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
            bar.setMax(1000); bar.setProgress((int) (stats.days[i] / maximum * 1000)); rows.addView(bar);
        }
        rows.addView(text("各类目 · 近 7 天", 17, BLUE));
        for (JSONObject item : items) {
            double total = 0;
            for (int i = 0; i < 7; i++) total += StudyStore.seconds(item, today.minusDays(i).toString());
            rows.addView(text(item.optString("name") + "    " + StudyStore.duration(total), 14, MUTED));
        }
        if (items.isEmpty()) rows.addView(text("添加类目并开始学习后，这里会显示统计。", 14, MUTED));
        new AlertDialog.Builder(this).setTitle("学习统计").setView(scroll).setPositiveButton("关闭", null).show();
    }

    private void editItem(JSONObject item) {
        LinearLayout form = column(); form.setPadding(dp(20), dp(8), dp(20), 0);
        EditText name = new EditText(this); name.setSingleLine(true); name.setHint("学习类目，如英语");
        EditText goal = new EditText(this); goal.setHint("每日目标（分钟）"); goal.setInputType(InputType.TYPE_CLASS_NUMBER);
        form.addView(name); form.addView(goal);
        if (item != null) { name.setText(item.optString("name")); goal.setText(String.valueOf(item.optInt("goal"))); }
        form.addView(text("上课安排", 16, BLUE));
        Spinner mode = new Spinner(this);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, CourseSchedule.LABELS);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item); mode.setAdapter(adapter); form.addView(mode);
        JSONObject rule = item == null ? null : item.optJSONObject("schedule");
        int modeIndex = 0;
        if (rule != null) for (int i = 0; i < CourseSchedule.MODES.length; i++) if (CourseSchedule.MODES[i].equals(rule.optString("mode"))) modeIndex = i;
        mode.setSelection(modeIndex);
        LinearLayout dayGroup = column(); form.addView(dayGroup);
        CheckBox[] days = new CheckBox[7];
        LinearLayout dayRow = null;
        for (int i = 0; i < 7; i++) {
            if (i == 0 || i == 4) { dayRow = row(); dayGroup.addView(dayRow); }
            days[i] = new CheckBox(this); days[i].setText(CourseSchedule.DAYS[i]); days[i].setTextSize(12);
            boolean checked = i < 5;
            if (rule != null && rule.optJSONArray("days") != null) {
                checked = false;
                for (int j = 0; j < rule.optJSONArray("days").length(); j++) if (rule.optJSONArray("days").optInt(j) == i + 1) checked = true;
            }
            days[i].setChecked(checked); addWeighted(dayRow, days[i]);
        }
        dayGroup.setVisibility(modeIndex == 3 ? View.VISIBLE : View.GONE);
        mode.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) { dayGroup.setVisibility(position == 3 ? View.VISIBLE : View.GONE); }
            public void onNothingSelected(AdapterView<?> parent) { }
        });
        form.addView(text("单双日按每月日期判断：1、3、5…为单数日。31 日和下月 1 日都是单数日。修改安排不删除历史记录。", 12, MUTED));
        ScrollView scroll = new ScrollView(this); scroll.addView(form);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle(item == null ? "添加课程" : "修改课程与安排").setView(scroll).setPositiveButton("保存", null).setNegativeButton("取消", null).create();
        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            try {
                int minutes;
                try { minutes = Integer.parseInt(goal.getText().toString()); } catch (NumberFormatException e) { throw new IllegalArgumentException("请输入有效的整数分钟数"); }
                JSONObject schedule = new JSONObject().put("mode", CourseSchedule.MODES[mode.getSelectedItemPosition()]);
                if (mode.getSelectedItemPosition() == 3) {
                    JSONArray selectedDays = new JSONArray();
                    for (int i = 0; i < 7; i++) if (days[i].isChecked()) selectedDays.put(i + 1);
                    schedule.put("days", selectedDays);
                }
                store.edit(item == null ? "" : item.optString("id"), name.getText().toString(), minutes, schedule);
                refresh(); dialog.dismiss();
            } catch (Exception e) { error(e); }
        })); dialog.show();
    }
    private void calendar() {
        ScrollView scroll = new ScrollView(this); LinearLayout rows = column();
        rows.setPadding(dp(20), dp(8), dp(20), dp(12)); scroll.addView(rows);
        List<JSONObject> items = store.items(); LocalDate today = StudyStore.currentDate();
        rows.addView(text("按当前课程规则预览；系统日期改变后首页自动更新。", 13, MUTED));
        for (int i = 0; i < 14; i++) {
            LocalDate day = today.plusDays(i);
            rows.addView(text(day + " " + CourseSchedule.DAYS[day.getDayOfWeek().getValue() - 1], 17, BLUE));
            boolean any = false;
            for (JSONObject item : items) if (CourseSchedule.isDue(item, day)) {
                any = true; rows.addView(text(item.optString("name") + " · " + item.optInt("goal") + " 分钟", 14, MUTED));
            }
            if (!any) rows.addView(text("休息日 · 无课程安排", 14, MUTED));
        }
        new AlertDialog.Builder(this).setTitle("未来 14 天课程表").setView(scroll).setPositiveButton("关闭", null).show();
    }
    private void deleteSelected() {
        JSONObject item = selectedItem(); if (item == null) return;
        new AlertDialog.Builder(this).setTitle("删除类目？").setMessage("将删除“" + item.optString("name") + "”及其学习记录，下一次同步也会删除另一端的同一类目。")
                .setNegativeButton("取消", null).setPositiveButton("删除", (d, w) -> {
                    try { store.delete(item.optString("id")); refresh(); } catch (Exception e) { error(e); }
                }).show();
    }
    private void history() {
        ScrollView scroll = new ScrollView(this); LinearLayout rows = column(); rows.setPadding(dp(20), 0, dp(20), 0); scroll.addView(rows);
        List<String[]> entries = new ArrayList<>(); double total = 0;
        for (JSONObject item : store.items()) {
            Iterator<String> dates = item.optJSONObject("counters").keys();
            while (dates.hasNext()) {
                String day = dates.next(); double seconds = StudyStore.seconds(item, day);
                if (seconds > 0) { total += seconds; entries.add(new String[]{day, item.optString("name"), StudyStore.duration(seconds)}); }
            }
        }
        entries.sort(Comparator.comparing((String[] entry) -> entry[0]).reversed());
        rows.addView(text("累计学习 " + StudyStore.duration(total), 18, BLUE));
        for (String[] entry : entries) rows.addView(text(entry[0] + " · " + entry[1] + "\n" + entry[2], 15, MUTED));
        if (entries.isEmpty()) rows.addView(text("还没有学习记录。", 15, MUTED));
        new AlertDialog.Builder(this).setTitle("历史学习记录").setView(scroll).setPositiveButton("关闭", null).show();
    }
    private void syncDialog() {
        LinearLayout form = column(); form.setPadding(dp(20), dp(8), dp(20), 0);
        form.addView(text("先在电脑版点击“局域网同步 → 开启同步”，手机和电脑需连接同一局域网。", 14, MUTED));
        EditText address = new EditText(this); address.setSingleLine(true); address.setHint("http://192.168.1.5:8765"); address.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI); address.setText(store.setting("address")); form.addView(address);
        EditText code = new EditText(this); code.setSingleLine(true); code.setHint("电脑显示的 12 位配对码"); code.setText(store.setting("token")); form.addView(code);
        TextView status = text(store.setting("lastSync").isEmpty() ? "首次同步会合并两端的数据。" : store.setting("lastSync"), 13, MUTED); form.addView(status);
        form.addView(text("只通过可信局域网传输，不经过云端；同步类目、目标与记录，计时启停各自独立。", 12, MUTED));
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("与电脑同步").setView(form).setPositiveButton("立即同步", null).setNegativeButton("关闭", null).create();
        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            if (syncing) return;
            try {
                String url = SyncClient.normalizeAddress(address.getText().toString());
                String token = code.getText().toString().trim().toUpperCase(java.util.Locale.ROOT);
                if (!token.matches("[A-F0-9]{12}")) throw new IllegalArgumentException("请输入 12 位配对码");
                store.setting("address", url); store.setting("token", token);
                JSONObject snapshot = store.snapshot(); store.save();
                syncing = true; status.setText("正在连接电脑并合并记录…"); dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
                network.execute(() -> {
                    String result;
                    try {
                        JSONObject merged = SyncClient.exchange(url, token, snapshot);
                        store.merge(merged);
                        result = "同步成功 · " + LocalDateTime.now().format(DateTimeFormatter.ofPattern("MM-dd HH:mm:ss"));
                        store.setting("lastSync", result);
                    } catch (Exception e) {
                        result = "同步失败：" + (e.getMessage() == null ? "无法连接" : e.getMessage()) + "\n请确认电脑已开启同步、地址正确，并在 Windows 防火墙允许 Python 的专用网络连接。";
                    }
                    String message = result;
                    runOnUiThread(() -> {
                        syncing = false;
                        if (!isDestroyed() && !isFinishing()) {
                            status.setText(message); dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true); refresh();
                        }
                    });
                });
            } catch (Exception e) { error(e); }
        })); dialog.show();
    }
    @Override protected void onStart() {
        super.onStart();
        if (store != null) { try { store.setVisible(true); } catch (Exception e) { error(e); } }
    }
    @Override protected void onResume() { super.onResume(); if (store != null) handler.post(ticker); }
    @Override protected void onPause() {
        handler.removeCallbacks(ticker);
        if (store != null) { try { store.tick(); store.save(); } catch (Exception e) { error(e); } }
        super.onPause();
    }
    @Override protected void onStop() {
        if (store != null && !isChangingConfigurations()) {
            try {
                store.setVisible(false); store.save();
                if (!store.backgroundEnabled()) stopService(new Intent(this, TimerService.class));
            } catch (Exception e) { error(e); }
        }
        super.onStop();
    }
    @Override protected void onSaveInstanceState(Bundle state) { state.putString("selected", selected); state.putBoolean("showAllCourses", showAllCourses); super.onSaveInstanceState(state); }
    @Override protected void onDestroy() { handler.removeCallbacksAndMessages(null); network.shutdown(); super.onDestroy(); }
}
