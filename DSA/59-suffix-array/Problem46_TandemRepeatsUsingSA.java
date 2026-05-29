import java.util.*;

public class Problem46_TandemRepeatsUsingSA {
    // Find all tandem repeats (consecutive repeated substrings)
    public static List<int[]> findTandemRepeats(String s) {
        int n = s.length();
        List<int[]> repeats = new ArrayList<>(); // [start, length_of_period]
        for (int len = 1; len <= n/2; len++) {
            for (int i = 0; i + 2*len <= n; i++) {
                boolean match = true;
                for (int j = 0; j < len; j++)
                    if (s.charAt(i+j) != s.charAt(i+len+j)) { match = false; break; }
                if (match) repeats.add(new int[]{i, len});
            }
        }
        return repeats;
    }

    public static void main(String[] args) {
        String s = "abcabcxyz";
        List<int[]> repeats = findTandemRepeats(s);
        for (int[] r : repeats)
            System.out.println("Tandem at " + r[0] + ", period " + r[1] + ": " + s.substring(r[0], r[0]+2*r[1]));
    }
}
