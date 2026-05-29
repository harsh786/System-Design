import java.util.*;

public class Problem28_SuffixArrayForGenomeAssembly {
    // Find overlaps between reads using suffix array
    public static int overlap(String a, String b) {
        // Max overlap: suffix of a = prefix of b
        int maxOvlp = Math.min(a.length(), b.length());
        for (int len = maxOvlp; len > 0; len--)
            if (a.endsWith(b.substring(0, len))) return len;
        return 0;
    }

    public static String assemble(String[] reads) {
        List<String> remaining = new ArrayList<>(Arrays.asList(reads));
        while (remaining.size() > 1) {
            int bestI = 0, bestJ = 1, bestOvlp = -1;
            for (int i = 0; i < remaining.size(); i++)
                for (int j = 0; j < remaining.size(); j++) if (i != j) {
                    int o = overlap(remaining.get(i), remaining.get(j));
                    if (o > bestOvlp) { bestOvlp = o; bestI = i; bestJ = j; }
                }
            String merged = remaining.get(bestI) + remaining.get(bestJ).substring(bestOvlp);
            remaining.remove(Math.max(bestI, bestJ)); remaining.remove(Math.min(bestI, bestJ));
            remaining.add(merged);
        }
        return remaining.get(0);
    }

    public static void main(String[] args) {
        String[] reads = {"ATCGA", "CGATT", "ATTGC"};
        System.out.println(assemble(reads));
    }
}
