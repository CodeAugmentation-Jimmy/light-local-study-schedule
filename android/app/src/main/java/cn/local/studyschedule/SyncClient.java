package cn.local.studyschedule;

import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public final class SyncClient {
    public static String normalizeAddress(String input) {
        String address = input.trim();
        if (!address.startsWith("http://")) address = "http://" + address;
        try {
            URL url = new URL(address);
            String host = url.getHost();
            String[] parts = host.split("\\.");
            if (parts.length != 4) throw new IllegalArgumentException();
            int[] ip = new int[4];
            for (int i = 0; i < 4; i++) {
                if (!parts[i].matches("[0-9]{1,3}")) throw new IllegalArgumentException();
                ip[i] = Integer.parseInt(parts[i]);
                if (ip[i] > 255) throw new IllegalArgumentException();
            }
            boolean local = ip[0] == 10 || ip[0] == 127 || (ip[0] == 192 && ip[1] == 168) || (ip[0] == 172 && ip[1] >= 16 && ip[1] <= 31) || (ip[0] == 169 && ip[1] == 254);
            if (!local || !url.getProtocol().equals("http") || url.getUserInfo() != null || url.getQuery() != null || url.getRef() != null || (!url.getPath().isEmpty() && !url.getPath().equals("/"))) throw new IllegalArgumentException();
            int port = url.getPort() == -1 ? 8765 : url.getPort();
            if (port < 1 || port > 65535) throw new IllegalArgumentException();
            return "http://" + host + ":" + port;
        } catch (Exception e) { throw new IllegalArgumentException("请输入电脑的局域网 IPv4 地址，例如 http://192.168.1.5:8765"); }
    }
    public static JSONObject exchange(String address, String token, JSONObject document) throws Exception {
        token = token.trim().toUpperCase(java.util.Locale.ROOT);
        if (!token.matches("[A-F0-9]{12}")) throw new IllegalArgumentException("请输入电脑显示的 12 位配对码");
        HttpURLConnection connection = (HttpURLConnection) new URL(normalizeAddress(address) + "/sync").openConnection();
        try {
            connection.setConnectTimeout(8000);
            connection.setReadTimeout(20000);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestMethod("POST");
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setRequestProperty("X-Study-Token", token);
            connection.setDoOutput(true);
            byte[] body = document.toString().getBytes(StandardCharsets.UTF_8);
            if (body.length > 8 * 1024 * 1024) throw new IllegalArgumentException("学习数据过大");
            connection.setFixedLengthStreamingMode(body.length);
            try (java.io.OutputStream output = connection.getOutputStream()) { output.write(body); }
            int status = connection.getResponseCode();
            if (status != 200) throw new IllegalStateException(status == 401 ? "配对码不正确" : status == 400 ? "同步数据或版本不匹配，请确认电脑和手机均升级至 1.2" : "电脑拒绝同步（" + status + "），请检查电脑版的保存状态");
            ByteArrayOutputStream response = new ByteArrayOutputStream();
            try (InputStream stream = connection.getInputStream()) {
                byte[] buffer = new byte[8192];
                int read;
                while ((read = stream.read(buffer)) != -1) {
                    if (response.size() + read > 8 * 1024 * 1024) throw new IllegalStateException("电脑返回的数据过大");
                    response.write(buffer, 0, read);
                }
            }
            JSONObject merged = new JSONObject(response.toString(StandardCharsets.UTF_8.name()));
            StudyStore.validate(merged);
            return merged;
        } finally { connection.disconnect(); }
    }
}
