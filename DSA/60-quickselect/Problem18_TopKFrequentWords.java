import java.util.*;

public class Problem18_TopKFrequentWords {
    public List<String> topKFrequent(String[] words, int k) {
        Map<String, Integer> freq = new HashMap<>();
        for (String w : words) freq.merge(w, 1, Integer::sum);
        List<String> candidates = new ArrayList<>(freq.keySet());
        candidates.sort((a, b) -> freq.get(a).equals(freq.get(b)) ? a.compareTo(b) : freq.get(b) - freq.get(a));
        return candidates.subList(0, k);
    }

    public static void main(String[] args) {
        Problem18_TopKFrequentWords sol = new Problem18_TopKFrequentWords();
        System.out.println(sol.topKFrequent(new String[]{"i","love","leetcode","i","love","coding"}, 2));
    }
}
