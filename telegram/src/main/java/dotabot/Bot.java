package dotabot;

import org.telegram.api.TLAbsUpdates;
import org.telegram.api.TLConfig;
import org.telegram.api.engine.ApiCallback;
import org.telegram.api.engine.AppInfo;
import org.telegram.api.engine.RpcCallback;
import org.telegram.api.engine.TelegramApi;
import org.telegram.api.requests.TLRequestHelpGetConfig;
import org.telegram.mtproto.pq.Authorizer;
import org.telegram.mtproto.pq.PqAuth;
import org.telegram.mtproto.state.ConnectionInfo;

import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;

public class Bot {
    private static final String PROPERTIES_FILE_LOCATION = "appconfig.properties";

    private TelegramApi api;

    public Bot() {
        AppInfo appInfo;
        try {
            appInfo = readAppInfoConfig();
        } catch (FileNotFoundException fnf) {
            System.out.println("properties file not found.");
            throw new RuntimeException(fnf);
        } catch (IOException ioe) {
            System.out.println("Error reading properties file.");
            throw new RuntimeException(ioe);
        }

        this.api = new TelegramApi(new BotState(), appInfo, new ApiCallback() {
            @Override
            public void onAuthCancelled(TelegramApi api) {
                System.out.println("onAuthCancelled called"); // TODO what?
            }

            @Override
            public void onUpdatesInvalidated(TelegramApi api) {
                System.out.println("onUpdatesInvalidated called"); // TODO what?
            }

            @Override
            public void onUpdate(TLAbsUpdates updates) {
                System.out.println("onUpdate called"); // TODO what?
            }
        });

        // TODO
    }

    public void boop() {
        RpcCallback<TLConfig> callback = new RpcCallback<TLConfig>()
        {
            public void onResult(TLConfig result)
            {
                System.out.println("Result received: " + result.toString());
            }

            public void onError(int errorCode, String message)
            {
                System.out.println("Error occurred: " + message);
                // errorCode == 0 if request timeouted
            }
        };
        api.doRpcCall(new TLRequestHelpGetConfig(), callback);
        try {
            callback.wait();
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        Bot bot = new Bot();
        bot.boop();
    }

    /**
     *
     * @return
     * @throws FileNotFoundException If the properties file does not exist in
     *      PROPERTIES_FILE_LOCATION.
     * @throws IOException If exception occurs while loading properties from the file.
     */
    private static AppInfo readAppInfoConfig() throws FileNotFoundException, IOException {
        Properties properties = new Properties();
        InputStream inputStream =
                Bot.class.getClassLoader().getResourceAsStream(PROPERTIES_FILE_LOCATION);
        if (null == inputStream) {
            throw new FileNotFoundException(
                    "app configuration file not found, please specify it in: " +
                    PROPERTIES_FILE_LOCATION);
        }

        properties.load(inputStream);

        int apiId = Integer.parseInt(properties.getProperty("api_id"));
        String deviceModel = properties.getProperty("device_model");
        String systemVersion = properties.getProperty("system_version");
        String appVersion = properties.getProperty("app_version");
        String langCode = properties.getProperty("lang_code");
        return new AppInfo(apiId, deviceModel, systemVersion, appVersion, langCode);
    }
}
