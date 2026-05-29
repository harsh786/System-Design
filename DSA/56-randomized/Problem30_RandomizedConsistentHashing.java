import java.util.*;

public class Problem30_RandomizedConsistentHashing {
    // Consistent hashing ring with virtual nodes
    TreeMap<Integer, String> ring = new TreeMap<>();
    int virtualNodes;

    public Problem30_RandomizedConsistentHashing(int virtualNodes) { this.virtualNodes = virtualNodes; }

    public void addServer(String server) {
        for (int i = 0; i < virtualNodes; i++) ring.put((server + "#" + i).hashCode(), server);
    }

    public void removeServer(String server) {
        for (int i = 0; i < virtualNodes; i++) ring.remove((server + "#" + i).hashCode());
    }

    public String getServer(String key) {
        if (ring.isEmpty()) return null;
        int hash = key.hashCode();
        Map.Entry<Integer, String> entry = ring.ceilingEntry(hash);
        return entry != null ? entry.getValue() : ring.firstEntry().getValue();
    }

    public static void main(String[] args) {
        Problem30_RandomizedConsistentHashing ch = new Problem30_RandomizedConsistentHashing(100);
        ch.addServer("server1"); ch.addServer("server2"); ch.addServer("server3");
        for (int i = 0; i < 10; i++) System.out.println("key" + i + " -> " + ch.getServer("key" + i));
    }
}
