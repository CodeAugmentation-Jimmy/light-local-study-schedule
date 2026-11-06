import cn.local.studyschedule.StudyStore;
import cn.local.studyschedule.SyncClient;
import java.nio.file.Files;
import java.nio.file.Path;
import org.json.JSONObject;

public class ProtocolCheck {
    public static void main(String[] args) throws Exception {
        JSONObject left = new JSONObject(Files.readString(Path.of(args[1])));
        JSONObject result;
        if (args[0].equals("http")) result = SyncClient.exchange(args[2], args[3], left);
        else result = StudyStore.mergeDocuments(left, new JSONObject(Files.readString(Path.of(args[2]))));
        System.out.println(result.toString());
    }
}
