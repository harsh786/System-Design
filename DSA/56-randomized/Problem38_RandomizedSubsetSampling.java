import java.util.*;

public class Problem38_RandomizedSubsetSampling {
    // Select k elements from n without replacement
    public static List<Integer> sampleSubset(int n, int k) {
        Random rand = new Random();
        Map<Integer, Integer> swapped = new HashMap<>();
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < k; i++) {
            int j = i + rand.nextInt(n - i);
            int vi = swapped.getOrDefault(i, i);
            int vj = swapped.getOrDefault(j, j);
            result.add(vj);
            swapped.put(j, vi);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(sampleSubset(100, 5));
        System.out.println(sampleSubset(10, 10));
    }
}
