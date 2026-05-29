import java.util.*;

/**
 * Problem 9: Radix Sort for IP Addresses
 * 
 * Sort IP addresses (IPv4) using radix sort.
 * Each IP has 4 octets (0-255), perfect for base-256 radix sort.
 * 
 * Approach:
 * - Convert each IP to a 32-bit integer (or treat as 4-digit base-256 number)
 * - LSD radix sort with 4 passes (one per octet, from rightmost to leftmost)
 * 
 * This demonstrates a practical application where radix sort's O(n) 
 * beats comparison-based O(n log n) for large datasets.
 */
public class Problem09_RadixSortIPAddresses {

    public static void sortIPAddresses(String[] ips) {
        int n = ips.length;
        long[] numeric = new long[n];
        
        // Convert to numeric
        for (int i = 0; i < n; i++) {
            numeric[i] = ipToLong(ips[i]);
        }
        
        // Radix sort by each octet (4 passes, base-256)
        long[] aux = new long[n];
        for (int octet = 0; octet < 4; octet++) {
            int shift = octet * 8;
            int[] count = new int[257];
            
            for (long v : numeric) {
                count[(int)((v >> shift) & 0xFF) + 1]++;
            }
            for (int i = 1; i <= 256; i++) count[i] += count[i-1];
            for (long v : numeric) {
                aux[count[(int)((v >> shift) & 0xFF)]++] = v;
            }
            System.arraycopy(aux, 0, numeric, 0, n);
        }
        
        // Convert back to strings
        for (int i = 0; i < n; i++) {
            ips[i] = longToIP(numeric[i]);
        }
    }

    private static long ipToLong(String ip) {
        String[] parts = ip.split("\\.");
        long result = 0;
        for (int i = 0; i < 4; i++) {
            result = (result << 8) | Integer.parseInt(parts[i]);
        }
        return result;
    }

    private static String longToIP(long num) {
        return String.format("%d.%d.%d.%d",
            (num >> 24) & 0xFF, (num >> 16) & 0xFF,
            (num >> 8) & 0xFF, num & 0xFF);
    }

    public static void main(String[] args) {
        String[] ips = {
            "192.168.1.100", "10.0.0.1", "172.16.0.5", "192.168.1.1",
            "10.0.0.255", "8.8.8.8", "255.255.255.255", "0.0.0.0",
            "192.168.0.1", "10.10.10.10", "127.0.0.1", "192.168.1.50"
        };
        
        System.out.println("Radix Sort for IP Addresses");
        System.out.println("Before:");
        for (String ip : ips) System.out.println("  " + ip);
        
        sortIPAddresses(ips);
        
        System.out.println("\nAfter (sorted):");
        for (String ip : ips) System.out.println("  " + ip);
        
        // Verify order
        for (int i = 1; i < ips.length; i++) {
            assert ipToLong(ips[i]) >= ipToLong(ips[i-1]);
        }
        System.out.println("\nPASS - IPs sorted correctly");
    }
}
