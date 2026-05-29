import java.util.*;

/**
 * Problem 51: IP Routing Table (Longest Prefix Match)
 * 
 * Production Relevance:
 * - Core of every router: match destination IP to longest matching CIDR prefix
 * - Used in Linux kernel routing (FIB), BGP route tables, SDN controllers, AWS VPC routing
 * - Must handle millions of routes with nanosecond lookup times
 * - Trie/Patricia tree is standard data structure for IP prefix matching
 * 
 * Architect Considerations:
 * - Binary trie on IP bits: each level = 1 bit of IP address
 * - Compressed tries (LC-trie, Patricia) reduce memory for sparse prefixes
 * - IPv4: max 32 levels, IPv6: max 128 levels
 * - Route updates must be atomic (no inconsistent forwarding during update)
 */
public class Problem51_IPRoutingTableLongestPrefixMatch {

    static class TrieNode {
        TrieNode[] children = new TrieNode[2]; // 0, 1
        String nextHop; // non-null if this is a valid prefix endpoint
        int prefixLength;
    }

    static class IPRoutingTable {
        TrieNode root = new TrieNode();
        int routeCount = 0;

        // Insert CIDR route: e.g., "192.168.1.0/24" -> "eth0"
        void addRoute(String cidr, String nextHop) {
            String[] parts = cidr.split("/");
            int prefixLen = Integer.parseInt(parts[1]);
            int ip = ipToInt(parts[0]);

            TrieNode node = root;
            for (int i = 31; i >= 32 - prefixLen; i--) {
                int bit = (ip >> i) & 1;
                if (node.children[bit] == null) node.children[bit] = new TrieNode();
                node = node.children[bit];
            }
            node.nextHop = nextHop;
            node.prefixLength = prefixLen;
            routeCount++;
        }

        // Longest prefix match lookup
        String lookup(String ipAddress) {
            int ip = ipToInt(ipAddress);
            TrieNode node = root;
            String bestMatch = root.nextHop; // default route if set

            for (int i = 31; i >= 0; i--) {
                int bit = (ip >> i) & 1;
                if (node.children[bit] == null) break;
                node = node.children[bit];
                if (node.nextHop != null) bestMatch = node.nextHop;
            }
            return bestMatch;
        }

        void removeRoute(String cidr) {
            String[] parts = cidr.split("/");
            int prefixLen = Integer.parseInt(parts[1]);
            int ip = ipToInt(parts[0]);

            TrieNode node = root;
            for (int i = 31; i >= 32 - prefixLen; i--) {
                int bit = (ip >> i) & 1;
                if (node.children[bit] == null) return;
                node = node.children[bit];
            }
            if (node.nextHop != null) { node.nextHop = null; routeCount--; }
        }

        private int ipToInt(String ip) {
            String[] octets = ip.split("\\.");
            int result = 0;
            for (String octet : octets) result = (result << 8) | Integer.parseInt(octet);
            return result;
        }
    }

    public static void main(String[] args) {
        System.out.println("=== IP Routing Table (Longest Prefix Match) ===\n");

        IPRoutingTable table = new IPRoutingTable();
        table.addRoute("0.0.0.0/0", "default-gw");          // Default route
        table.addRoute("10.0.0.0/8", "vpc-router");         // Private network
        table.addRoute("10.1.0.0/16", "subnet-a-gw");       // Subnet A
        table.addRoute("10.1.1.0/24", "subnet-a1-gw");      // Subnet A1 (more specific)
        table.addRoute("192.168.0.0/16", "home-router");
        table.addRoute("192.168.1.0/24", "lan-switch");

        System.out.println("Routes installed: " + table.routeCount);

        String[] lookups = {"10.1.1.5", "10.1.2.100", "10.2.0.1", "192.168.1.50", "8.8.8.8"};
        System.out.println("\nLookups:");
        for (String ip : lookups) {
            System.out.printf("  %-15s -> %s%n", ip, table.lookup(ip));
        }

        // Remove specific route, verify fallback
        table.removeRoute("10.1.1.0/24");
        System.out.println("\nAfter removing 10.1.1.0/24:");
        System.out.printf("  %-15s -> %s (falls back to /16)%n", "10.1.1.5", table.lookup("10.1.1.5"));
    }
}
