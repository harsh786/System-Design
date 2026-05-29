import java.util.*;
import java.security.*;

public class Problem42_VirtualNodesConsistentHashing {
    private TreeMap<Long, String> ring = new TreeMap<>();
    private int virtualNodes;

    public Problem42_VirtualNodesConsistentHashing(int virtualNodes) { this.virtualNodes = virtualNodes; }

    private long hash(String key) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] d = md.digest(key.getBytes());
            return ((long)(d[0]&0xFF)<<24)|((long)(d[1]&0xFF)<<16)|((long)(d[2]&0xFF)<<8)|(d[3]&0xFF);
        } catch (Exception e) { return key.hashCode() & 0xFFFFFFFFL; }
    }

    public void addNode(String node) {
        for (int i = 0; i < virtualNodes; i++) ring.put(hash(node + "#" + i), node);
    }

    public void removeNode(String node) {
        for (int i = 0; i < virtualNodes; i++) ring.remove(hash(node + "#" + i));
    }

    public String getNode(String key) {
        if (ring.isEmpty()) return null;
        Map.Entry<Long, String> entry = ring.ceilingEntry(hash(key));
        return entry != null ? entry.getValue() : ring.firstEntry().getValue();
    }

    public static void main(String[] args) {
        Problem42_VirtualNodesConsistentHashing sol = new Problem42_VirtualNodesConsistentHashing(150);
        sol.addNode("ServerA"); sol.addNode("ServerB"); sol.addNode("ServerC");
        Map<String, Integer> dist = new HashMap<>();
        for (int i = 0; i < 1000; i++) dist.merge(sol.getNode("key" + i), 1, Integer::sum);
        System.out.println("Distribution: " + dist);
    }
}
