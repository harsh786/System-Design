import java.util.*;

public class Problem12_ConsistentHashing {
    private TreeMap<Integer, String> ring = new TreeMap<>();

    public void addNode(String node) {
        int hash = node.hashCode() & Integer.MAX_VALUE;
        ring.put(hash, node);
    }

    public void removeNode(String node) {
        int hash = node.hashCode() & Integer.MAX_VALUE;
        ring.remove(hash);
    }

    public String getNode(String key) {
        if (ring.isEmpty()) return null;
        int hash = key.hashCode() & Integer.MAX_VALUE;
        Map.Entry<Integer, String> entry = ring.ceilingEntry(hash);
        return entry != null ? entry.getValue() : ring.firstEntry().getValue();
    }

    public static void main(String[] args) {
        Problem12_ConsistentHashing sol = new Problem12_ConsistentHashing();
        sol.addNode("ServerA"); sol.addNode("ServerB"); sol.addNode("ServerC");
        System.out.println("key1 -> " + sol.getNode("key1"));
        System.out.println("key2 -> " + sol.getNode("key2"));
        sol.removeNode("ServerB");
        System.out.println("After removing ServerB, key2 -> " + sol.getNode("key2"));
    }
}
