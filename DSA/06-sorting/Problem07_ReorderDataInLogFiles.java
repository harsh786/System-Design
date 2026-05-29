import java.util.*;

/**
 * Problem 7: Reorder Data in Log Files
 * 
 * Letter-logs sorted lexicographically by content then identifier. Digit-logs maintain relative order.
 * 
 * Approach: Custom comparator separating letter-logs and digit-logs.
 * Time Complexity: O(n log n * m) where m is log length
 * Space Complexity: O(n)
 * 
 * Production Analogy: Log aggregation systems (like Splunk/ELK) that sort structured logs
 * differently from unstructured ones during ingestion.
 */
public class Problem07_ReorderDataInLogFiles {
    
    public String[] reorderLogFiles(String[] logs) {
        Arrays.sort(logs, (a, b) -> {
            int ai = a.indexOf(' '), bi = b.indexOf(' ');
            char ac = a.charAt(ai + 1), bc = b.charAt(bi + 1);
            
            if (Character.isDigit(ac) && Character.isDigit(bc)) return 0; // maintain order
            if (Character.isDigit(ac)) return 1; // digit-logs go after
            if (Character.isDigit(bc)) return -1;
            
            // Both letter-logs
            String aBody = a.substring(ai + 1), bBody = b.substring(bi + 1);
            int cmp = aBody.compareTo(bBody);
            if (cmp != 0) return cmp;
            return a.substring(0, ai).compareTo(b.substring(0, bi));
        });
        return logs;
    }
    
    public static void main(String[] args) {
        Problem07_ReorderDataInLogFiles sol = new Problem07_ReorderDataInLogFiles();
        
        String[] t1 = {"dig1 8 1 5 1","let1 art can","dig2 3 6","let2 own kit dig","let3 art zero"};
        System.out.println("Test 1: " + Arrays.toString(sol.reorderLogFiles(t1)));
        // [let1 art can, let3 art zero, let2 own kit dig, dig1 8 1 5 1, dig2 3 6]
        
        String[] t2 = {"a1 9 2 3 1","g1 act car","zo4 4 7","ab1 off key dog","a8 act zoo"};
        System.out.println("Test 2: " + Arrays.toString(sol.reorderLogFiles(t2)));
    }
}
