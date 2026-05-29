import java.util.*;

public class Problem40_SuffixArrayForBiologicalSequences {
    // Find tandem repeats in DNA
    public static List<String> findTandemRepeats(String dna) {
        Set<String> repeats = new TreeSet<>();
        for (int len = 1; len <= dna.length()/2; len++) {
            for (int i = 0; i + 2*len <= dna.length(); i++) {
                if (dna.substring(i, i+len).equals(dna.substring(i+len, i+2*len)))
                    repeats.add(dna.substring(i, i+2*len));
            }
        }
        return new ArrayList<>(repeats);
    }

    public static void main(String[] args) {
        System.out.println(findTandemRepeats("ATCGATCGATCG"));
        System.out.println(findTandemRepeats("AAAGGGAAAGGG"));
    }
}
