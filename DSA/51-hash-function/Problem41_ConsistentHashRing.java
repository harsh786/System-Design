import java.util.*;
import java.security.*;

public class Problem41_ConsistentHashRing {
    private TreeMap<Long, String> ring = new TreeMap<>();

    private long hash(String key) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] digest = md.digest(key.getBytes());
            return ((long)(digest[0] & 0xFF) << 24) | ((long)(digest[1] & 0xFF) << 16) |
                   ((long)(digest[2] & 0xFF) << 8) | (digest[3] & 0xFF);
        } catch (Exception e) { return key.hashCode() & 0xFFFFFFFFL; }
    }

    public void addNode(String node) { ring.put(hash(node), node); }
    public void removeNode(String node) { ring.remove(hash(node)); }

    public String getNode(String key) {
        if (ring.isEmpty()) return null;
        long h = hash(key);
        Map.Entry<Long, String> entry = ring.ceilingEntry(h);
        return entry != null ? entry.getValue() : ring.firstEntry().getValue();
    }

    public static void main(String[] args) {
        Problem41_ConsistentHashRing sol = new Problem41_ConsistentHashRing();
        sol.addNode("node1"); sol.addNode("node2"); sol.addNode("node3");
        System.out.println("key_abc -> " + sol.getNode("key_abc"));
        System.out.println("key_xyz -> " + sol.getNode("key_xyz"));
    }
}
