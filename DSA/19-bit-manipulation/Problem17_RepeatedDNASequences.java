/**
 * Problem 17: Repeated DNA Sequences
 * Find all 10-letter sequences that occur more than once.
 * 
 * Approach: Encode each char as 2 bits (A=00,C=01,G=10,T=11). Rolling hash with bitmask.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Detecting duplicate log patterns in streaming data.
 */
import java.util.*;

public class Problem17_RepeatedDNASequences {
    public static List<String> findRepeatedDnaSequences(String s) {
        List<String> result = new ArrayList<>();
        if (s.length() < 11) return result;
        Map<Character, Integer> map = Map.of('A',0,'C',1,'G',2,'T',3);
        Set<Integer> seen = new HashSet<>(), added = new HashSet<>();
        int hash = 0, mask = (1 << 20) - 1; // 10 chars * 2 bits = 20 bits
        for (int i = 0; i < s.length(); i++) {
            hash = ((hash << 2) | map.get(s.charAt(i))) & mask;
            if (i >= 9) {
                if (seen.contains(hash) && !added.contains(hash)) {
                    result.add(s.substring(i - 9, i + 1));
                    added.add(hash);
                }
                seen.add(hash);
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(findRepeatedDnaSequences("AAAAACCCCCAAAAACCCCCCAAAAAGGGTTT"));
        // [AAAAACCCCC, CCCCCAAAAA]
        System.out.println(findRepeatedDnaSequences("AAAAAAAAAAAAA"));
        // [AAAAAAAAAA]
    }
}
