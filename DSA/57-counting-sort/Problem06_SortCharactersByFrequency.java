import java.util.*;

public class Problem06_SortCharactersByFrequency {
    public static String frequencySort(String s) {
        int[] freq = new int[128];
        for (char c : s.toCharArray()) freq[c]++;
        List<Character>[] buckets = new List[s.length() + 1];
        for (int i = 0; i < 128; i++) if (freq[i] > 0) {
            if (buckets[freq[i]] == null) buckets[freq[i]] = new ArrayList<>();
            buckets[freq[i]].add((char) i);
        }
        StringBuilder sb = new StringBuilder();
        for (int i = buckets.length - 1; i >= 0; i--)
            if (buckets[i] != null) for (char c : buckets[i]) for (int j = 0; j < i; j++) sb.append(c);
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(frequencySort("tree"));   // eert
        System.out.println(frequencySort("cccaaa")); // cccaaa or aaaccc
    }
}
