import java.util.*;

public class Problem27_SuffixArrayForRepeatedDNA {
    // Find all repeated DNA sequences of length 10
    public static List<String> findRepeatedDNA(String s) {
        Set<String> seen = new HashSet<>(), repeated = new HashSet<>();
        for (int i = 0; i <= s.length() - 10; i++) {
            String sub = s.substring(i, i + 10);
            if (!seen.add(sub)) repeated.add(sub);
        }
        return new ArrayList<>(repeated);
    }

    public static void main(String[] args) {
        System.out.println(findRepeatedDNA("AAAAACCCCCAAAAACCCCCCAAAAAGGGTTT"));
        // [AAAAACCCCC, CCCCCAAAAA]
    }
}
