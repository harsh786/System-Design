import java.util.*;

public class Problem03_RepeatedDNASequences {
    public List<String> findRepeatedDnaSequences(String s) {
        Set<String> seen = new HashSet<>(), result = new HashSet<>();
        for (int i = 0; i + 10 <= s.length(); i++) {
            String sub = s.substring(i, i + 10);
            if (!seen.add(sub)) result.add(sub);
        }
        return new ArrayList<>(result);
    }

    public static void main(String[] args) {
        Problem03_RepeatedDNASequences sol = new Problem03_RepeatedDNASequences();
        System.out.println(sol.findRepeatedDnaSequences("AAAAACCCCCAAAAACCCCCCAAAAAGGGTTT"));
    }
}
