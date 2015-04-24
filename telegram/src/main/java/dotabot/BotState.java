package dotabot;

import org.telegram.api.TLConfig;
import org.telegram.api.engine.storage.AbsApiState;
import org.telegram.mtproto.pq.Authorizer;
import org.telegram.mtproto.pq.PqAuth;
import org.telegram.mtproto.state.AbsMTProtoState;
import org.telegram.mtproto.state.ConnectionInfo;

// TODO: I don't know what these methods all do yet.
public class BotState implements AbsApiState {
    private PqAuth pqAuth;

    public BotState() {
        Authorizer authorizer = new Authorizer();
        ConnectionInfo connectionInfo = new ConnectionInfo(0, 0, "149.154.167.40", 443);
        ConnectionInfo[] connections = new ConnectionInfo[1];
        connections[0] = connectionInfo;
        this.pqAuth = authorizer.doAuth(connections);
    }

    @Override
    public int getPrimaryDc() {
        return 0;
    }

    @Override
    public void setPrimaryDc(int dc) {

    }

    @Override
    public boolean isAuthenticated(int dcId) {
        return true;
    }

    @Override
    public void setAuthenticated(int dcId, boolean auth) {

    }

    @Override
    public void updateSettings(TLConfig config) {

    }

    @Override
    public byte[] getAuthKey(int dcId) {
        return this.pqAuth.getAuthKey();
    }

    @Override
    public void putAuthKey(int dcId, byte[] key) {

    }

    @Override
    public ConnectionInfo[] getAvailableConnections(int dcId) {
        return new ConnectionInfo[0];
    }

    @Override
    public AbsMTProtoState getMtProtoState(int dcId) {
        return null;
    }

    @Override
    public void resetAuth() {

    }

    @Override
    public void reset() {

    }
}
