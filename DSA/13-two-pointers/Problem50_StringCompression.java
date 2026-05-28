/**
 * Problem 50: String Compression
 * 
 * Compress string in-place: ["a","a","b","b","c","c","c"] -> ["a","2","b","2","c","3"]
 * 
 * Approach: Read pointer scans groups, write pointer writes char + count.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like run-length encoding log entries before transmitting
 * to reduce bandwidth - consecutive identical events become event+count.
 */
public class Problem50_StringCompression {
    public static int compress(char[] chars) {
        int write = 0, read = 0;
        while (read < chars.length) {
            char current = chars[read];
            int count = 0;
            while (read < chars.length && chars[read] == current) { read++; count++; }
            chars[write++] = current;
            if (count > 1) {
                for (char c : String.valueOf(count).toCharArray()) chars[write++] = c;
            }
        }
        return write;
    }

    public static void main(String[] args) {
        char[] a = {'a','a','b','b','c','c','c'};
        int len = compress(a);
        System.out.println(len + " " + new String(a, 0, len)); // 6 a2b2c3

        char[] b = {'a'};
        len = compress(b);
        System.out.println(len + " " + new String(b, 0, len)); // 1 a

        char[] c = {'a','b','b','b','b','b','b','b','b','b','b','b','b'};
        len = compress(c);
        System.out.println(len + " " + new String(c, 0, len)); // 4 ab12
    }
}
