import java.util.*;

/**
 * Problem 34: IP Routing Longest Prefix Match
 * 
 * Given routing table entries (IP/mask -> next hop), find the longest prefix match for a given IP.
 * Uses binary trie on IP bits.
 * 
 * Time Complexity: O(32) per lookup
 * Space Complexity: O(n * 32) for n routes
 * 
 * Production Analogy: Core internet routers (BGP routing tables), firewall rule matching,
 * CDN edge server selection, load balancer routing decisions.
 */
public class Problem34_IPRoutingLongestPrefixMatch {

    static class TrieNode {
        TrieNode[] children = new TrieNode[2];
        String nextHop = null; // non-null means a valid route ends here
    }

    static class IPRouter {
        TrieNode root = new TrieNode();

        // Add route: ip/prefixLen -> nextHop
        void addRoute(String ip, int prefixLen, String nextHop) {
            long ipLong = ipToLong(ip);
            TrieNode node = root;
            for (int i = 31; i >= 32 - prefixLen; i--) {
                int bit = (int) ((ipLong >> i) & 1);
                if (node.children[bit] == null) node.children[bit] = new TrieNode();
                node = node.children[bit];
            }
            node.nextHop = nextHop;
        }

        // Longest prefix match lookup
        String lookup(String ip) {
            long ipLong = ipToLong(ip);
            TrieNode node = root;
            String bestMatch = null;
            for (int i = 31; i >= 0; i--) {
                int bit = (int) ((ipLong >> i) & 1);
                if (node.children[bit] == null) break;
                node = node.children[bit];
                if (node.nextHop != null) bestMatch = node.nextHop;
            }
            return bestMatch;
        }

        long ipToLong(String ip) {
            String[] parts = ip.split("\\.");
            long result = 0;
            for (String p : parts) result = (result << 8) | Integer.parseInt(p);
            return result;
        }
    }

    public static void main(String[] args) {
        IPRouter router = new IPRouter();
        router.addRoute("192.168.0.0", 16, "eth0");
        router.addRoute("192.168.1.0", 24, "eth1");
        router.addRoute("10.0.0.0", 8, "eth2");
        router.addRoute("0.0.0.0", 0, "default");

        System.out.println(router.lookup("192.168.1.100")); // eth1 (longest /24)
        System.out.println(router.lookup("192.168.2.100")); // eth0 (/16 match)
        System.out.println(router.lookup("10.1.2.3"));      // eth2
        System.out.println(router.lookup("8.8.8.8"));       // default
    }
}
