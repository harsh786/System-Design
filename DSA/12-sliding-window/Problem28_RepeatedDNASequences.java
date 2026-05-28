import java.util.*;
/**
 * Problem 28: Repeated DNA Sequences (LeetCode 187)
 * 
 * Approach: Fixed window of size 10, use HashSet to track seen sequences.
 * Window invariant: window size == 10, hash the substring.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Like detecting repeated request patterns in network traffic
 * for DDoS fingerprinting.
 */
public class Problem28_RepeatedDNASequences {
    public static List<String> findRepeatedDnaSequences(String s) {
        Set<String> seen = new HashSet<>(), result = new HashSet<>();
        for (int i = 0; i <= s.length() - 10; i++) {
            String sub = s.substring(i, i + 10);
            if (!seen.add(sub)) result.add(sub);
        }
        return new ArrayList<>(result);
    }

    public static void main(String[] args) {
        System.out.println(findRepeatedDnaSequences("AAAAACCCCCAAAAACCCCCCAAAAAGGGTTT")); // [AAAAACCCCC, CCCCCAAAAA]
        System.out.println(findRepeatedDnaSequences("AAAAAAAAAAAAA")); // [AAAAAAAAAA]
        System.out.println(findRepeatedDnaSequences("ACGT")); // []
    }
}
